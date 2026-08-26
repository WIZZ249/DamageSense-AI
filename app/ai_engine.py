import base64
import io
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# ---------------------------------------------------------------------------
# Local TFLite model (optional). Set DAMAGE_TFLITE_MODEL_PATH to enable it.
# Uses the lightweight `tflite-runtime` package instead of full TensorFlow
# (a few MB instead of several hundred MB) so this stays deployable on
# Render's free tier.
# ---------------------------------------------------------------------------
TFLITE_MODEL_PATH = Path(os.getenv('DAMAGE_TFLITE_MODEL_PATH', '')).expanduser() if os.getenv('DAMAGE_TFLITE_MODEL_PATH') else None
TFLITE_LABELS_PATH = Path(os.getenv('DAMAGE_TFLITE_LABELS_PATH', 'models/labels.txt')).expanduser()
TFLITE_CONFIDENCE_THRESHOLD = float(os.getenv('DAMAGE_TFLITE_CONFIDENCE', '0.35'))

_tflite_interpreter = None
_tflite_input_details = None
_tflite_output_details = None
_tflite_labels = None


def _load_tflite():
    """Load a real TensorFlow Lite damage model lazily and keep it in RAM."""
    global _tflite_interpreter, _tflite_input_details, _tflite_output_details, _tflite_labels

    if _tflite_interpreter is not None:
        return True
    if not TFLITE_MODEL_PATH or not TFLITE_MODEL_PATH.is_file():
        return False

    try:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            # Falls back to full tensorflow only if it happens to be installed;
            # tflite-runtime is the supported/expected path in requirements.txt.
            from tensorflow.lite import Interpreter

        _tflite_interpreter = Interpreter(model_path=str(TFLITE_MODEL_PATH), num_threads=2)
        _tflite_interpreter.allocate_tensors()
        _tflite_input_details = _tflite_interpreter.get_input_details()
        _tflite_output_details = _tflite_interpreter.get_output_details()

        if TFLITE_LABELS_PATH.is_file():
            _tflite_labels = [line.strip() for line in TFLITE_LABELS_PATH.read_text(encoding='utf-8').splitlines() if line.strip()]
        else:
            _tflite_labels = []
        return True
    except Exception as exc:
        print(f'TFLite initialization error: {exc}')
        _tflite_interpreter = None
        return False


def _tflite_preprocess(image, input_detail):
    shape = input_detail['shape']
    if len(shape) != 4:
        raise ValueError(f'Unsupported TFLite input shape: {shape}')

    height, width = int(shape[1]), int(shape[2])
    image = image.resize((width, height), Image.Resampling.BILINEAR)
    array = np.asarray(image, dtype=np.float32)

    dtype = input_detail['dtype']
    if dtype == np.uint8:
        scale, zero_point = input_detail.get('quantization', (0.0, 0))
        if scale:
            array = np.round(array / scale + zero_point)
        array = np.clip(array, 0, 255).astype(np.uint8)
    elif dtype == np.int8:
        scale, zero_point = input_detail.get('quantization', (0.0, 0))
        if scale:
            array = np.round(array / scale + zero_point)
        else:
            array = array - 128
        array = np.clip(array, -128, 127).astype(np.int8)
    else:
        if os.getenv('DAMAGE_TFLITE_NORMALIZE', '0_1') == 'minus1_1':
            array = array / 127.5 - 1.0
        else:
            array = array / 255.0
        array = array.astype(dtype)

    return np.expand_dims(array, axis=0)


def _tflite_label(index):
    if _tflite_labels and 0 <= index < len(_tflite_labels):
        return _tflite_labels[index]
    return f'class_{index}'


def classify_with_tflite(file_bytes):
    """Run a configured TensorFlow Lite image classifier locally."""
    if not _load_tflite():
        return None

    try:
        image = _open_image(file_bytes)
        input_detail = _tflite_input_details[0]
        input_tensor = _tflite_preprocess(image, input_detail)
        _tflite_interpreter.set_tensor(input_detail['index'], input_tensor)
        _tflite_interpreter.invoke()

        output = _tflite_interpreter.get_tensor(_tflite_output_details[0]['index'])
        scores = np.asarray(output).squeeze()
        if scores.ndim != 1:
            return None

        output_detail = _tflite_output_details[0]
        if np.issubdtype(scores.dtype, np.integer):
            scale, zero_point = output_detail.get('quantization', (0.0, 0))
            if scale:
                scores = (scores.astype(np.float32) - zero_point) * scale

        scores = scores.astype(np.float32)
        if np.any(scores < 0) or float(scores.sum()) > 1.01:
            scores = np.exp(scores - np.max(scores))
            scores = scores / max(float(scores.sum()), 1e-8)

        index = int(np.argmax(scores))
        confidence = float(scores[index])
        raw_label = _tflite_label(index)
        result = normalize_damage_prediction(raw_label, confidence * 100)
        result['model'] = 'tflite_damage_model'
        result['raw_label'] = raw_label
        return result
    except Exception as exc:
        print(f'TFLite inference error: {exc}')
        return None


DAMAGE_LABELS = {
    'destroyed': ('destroyed_structure', 'CRITICAL'),
    'major': ('major_structural_damage', 'CRITICAL'),
    'severe': ('major_structural_damage', 'CRITICAL'),
    'collapsed': ('collapsed_structure', 'CRITICAL'),
    'collapse': ('collapsed_structure', 'CRITICAL'),
    'rubble': ('collapsed_structure', 'CRITICAL'),
    'broken': ('major_structural_damage', 'CRITICAL'),
    'damaged': ('major_structural_damage', 'CRITICAL'),
    'crack': ('minor_structural_damage', 'STABLE'),
    'crack_s': ('minor_structural_damage', 'STABLE'),
    'cracked': ('minor_structural_damage', 'STABLE'),
    'hole': ('minor_structural_damage', 'STABLE'),
    'minor': ('minor_structural_damage', 'STABLE'),
    'no_damage': ('no_visible_damage', 'STABLE'),
    'undamaged': ('no_visible_damage', 'STABLE'),
    'intact': ('no_visible_damage', 'STABLE'),
}

# ---------------------------------------------------------------------------
# Repair recommendations — surfaced alongside every assessment result so the
# app carries the user from "here's the damage" to "here's what to do about
# it," not just a bare label.
# ---------------------------------------------------------------------------
REPAIR_RECOMMENDATIONS = {
    'no_visible_damage': {
        'urgency': 'NONE',
        'repair_category': 'none',
        'summary': 'No visible structural damage detected.',
        'next_step': 'No action required. Re-assess after any future incident (storm, quake, flood) that may affect this structure.',
    },
    'minor_structural_damage': {
        'urgency': 'LOW',
        'repair_category': 'cosmetic_or_minor_structural',
        'summary': 'Minor damage detected — small cracks, holes, or surface-level issues.',
        'next_step': 'Monitor the affected area. Schedule a routine inspection by a local contractor within the next few weeks; not an emergency.',
    },
    'major_structural_damage': {
        'urgency': 'HIGH',
        'repair_category': 'structural',
        'summary': 'Significant structural damage detected — likely affecting load-bearing elements.',
        'next_step': 'Restrict access to the affected area. Arrange a professional structural inspection as soon as possible before the space is reoccupied.',
    },
    'collapsed_structure': {
        'urgency': 'CRITICAL',
        'repair_category': 'structural_severe',
        'summary': 'Partial or full structural collapse detected.',
        'next_step': 'Do not enter the structure. Contact local emergency services and a structural engineer immediately.',
    },
    'destroyed_structure': {
        'urgency': 'CRITICAL',
        'repair_category': 'total_loss',
        'summary': 'The structure appears destroyed or unsalvageable.',
        'next_step': 'Treat as a total loss for safety purposes. Contact emergency services, document for insurance/aid purposes, and await professional clearance before any access.',
    },
    'unknown_damage_state': {
        'urgency': 'UNKNOWN',
        'repair_category': 'unknown',
        'summary': 'Damage state could not be confidently determined from this image.',
        'next_step': 'Retake the photo with better lighting and a clearer view of the structure, or request a manual/professional inspection.',
    },
    'analysis_error': {
        'urgency': 'UNKNOWN',
        'repair_category': 'unknown',
        'summary': 'Automated analysis failed for this image.',
        'next_step': 'Try re-uploading the image. If this keeps happening, request a manual inspection.',
    },
}


def get_repair_recommendation(label: str) -> dict:
    """Look up repair guidance for a normalized damage label, with a safe default."""
    return REPAIR_RECOMMENDATIONS.get(label, REPAIR_RECOMMENDATIONS['unknown_damage_state'])


def normalize_damage_prediction(label, confidence):
    """Map raw model predictions to standardized damage categories."""
    normalized = label.lower().replace('-', '_').replace(' ', '_')
    for key, mapped in DAMAGE_LABELS.items():
        if key in normalized:
            mapped_label, severity = mapped
            return {
                'label': mapped_label,
                'confidence': round(float(confidence), 2),
                'severity': severity,
                'model': 'vision'
            }

    return {
        'label': normalized or 'unknown_damage_state',
        'confidence': round(float(confidence), 2),
        'severity': 'CRITICAL' if float(confidence) >= 60 else 'UNKNOWN',
        'model': 'vision'
    }


def _image_media_type(file_bytes):
    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            return Image.MIME.get(image.format, 'image/jpeg')
    except Exception:
        return 'image/jpeg'


def _normalize_professional_result(payload):
    """Normalize a structured multimodal response into the app's stable contract."""
    analysis = payload.get('analysis') or {}
    label = str(payload.get('classification') or 'unknown_damage_state').lower().replace('-', '_').replace(' ', '_')
    normalized = normalize_damage_prediction(label, float(payload.get('confidence', 0)))
    normalized['model'] = os.getenv('VISION_MODEL', 'gpt-5')
    normalized['asset_type'] = str(payload.get('asset_type') or 'unknown')
    normalized['analysis'] = {
        'asset_type': normalized['asset_type'],
        'executive_summary': str(analysis.get('executive_summary') or 'Professional image analysis completed.'),
        'findings': [str(item) for item in (analysis.get('findings') or [])][:8],
        'hazards': [str(item) for item in (analysis.get('hazards') or [])][:8],
        'recommendations': [str(item) for item in (analysis.get('recommendations') or [])][:8],
        'immediate_actions': [str(item) for item in (analysis.get('immediate_actions') or [])][:8],
        'confidence_rationale': str(analysis.get('confidence_rationale') or 'Confidence reflects the visible evidence and image quality.'),
        'review_priority': str(analysis.get('review_priority') or normalized.get('severity', 'UNKNOWN')),
    }
    rec = get_repair_recommendation(normalized['label']).copy()
    if normalized['analysis']['recommendations']:
        rec['summary'] = normalized['analysis']['recommendations'][0]
    if normalized['analysis']['immediate_actions']:
        rec['next_step'] = normalized['analysis']['immediate_actions'][0]
    normalized['recommendation'] = rec
    return normalized


def classify_with_vision_llm(file_bytes):
    """Use a configured professional multimodal model for broad asset assessment."""
    api_key = os.getenv('VISION_API_KEY') or os.getenv('OPENAI_API_KEY')
    api_base = (os.getenv('VISION_API_BASE') or os.getenv('OPENAI_API_BASE') or '').rstrip('/')
    model = os.getenv('VISION_MODEL', 'gpt-5')
    if not api_key or not api_base:
        return None

    schema = {
        'type': 'object',
        'properties': {
            'asset_type': {'type': 'string'},
            'classification': {'type': 'string', 'enum': ['no_visible_damage', 'minor_structural_damage', 'major_structural_damage', 'collapsed_structure', 'destroyed_structure', 'unknown_damage_state']},
            'confidence': {'type': 'number'},
            'analysis': {'type': 'object', 'properties': {
                'executive_summary': {'type': 'string'},
                'findings': {'type': 'array', 'items': {'type': 'string'}},
                'hazards': {'type': 'array', 'items': {'type': 'string'}},
                'recommendations': {'type': 'array', 'items': {'type': 'string'}},
                'immediate_actions': {'type': 'array', 'items': {'type': 'string'}},
                'confidence_rationale': {'type': 'string'},
                'review_priority': {'type': 'string'},
            }, 'required': ['executive_summary', 'findings', 'hazards', 'recommendations', 'immediate_actions', 'confidence_rationale', 'review_priority'], 'additionalProperties': False},
        },
        'required': ['asset_type', 'classification', 'confidence', 'analysis'],
        'additionalProperties': False,
    }
    prompt = """You are a professional visual damage-assessment analyst supporting humanitarian response and infrastructure inspection. Analyze the image conservatively. It may show a road, bridge, vehicle, building, utility asset, retaining wall, tunnel, or another structure. Identify the asset type and only describe evidence visible in the image. Do not invent measurements, hidden damage, or engineering certification. Use confidence from 0 to 100. Classification must describe the visible condition using the supplied categories. Give practical safety-first actions, clearly flag uncertainty, and state that qualified professionals must make safety-critical decisions. Return JSON matching the schema exactly."""
    image_url = f"data:{_image_media_type(file_bytes)};base64,{base64.b64encode(file_bytes).decode('ascii')}"
    request_body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Assess this image for triage and inspection planning.'}, {'type': 'image_url', 'image_url': {'url': image_url, 'detail': 'auto'}}]},
        ],
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'damage_assessment', 'strict': True, 'schema': schema}},
        'max_completion_tokens': 1800,
    }
    try:
        request = urllib.request.Request(
            f'{api_base}/chat/completions',
            data=json.dumps(request_body).encode('utf-8'),
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode('utf-8'))
        content = response_payload['choices'][0]['message'].get('content') or '{}'
        if isinstance(content, list):
            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
        parsed = json.loads(content)
        return _normalize_professional_result(parsed)
    except Exception as exc:
        print(f'Professional vision API error: {exc}')
        return None


def classify_with_roboflow(file_bytes):
    """Call the configured Roboflow hosted damage model."""
    api_key = os.getenv('ROBOFLOW_API_KEY')
    model_id = os.getenv('ROBOFLOW_MODEL_ID')
    if not api_key or not model_id:
        return None

    try:
        encoded_image = base64.b64encode(file_bytes).decode('utf-8')
        params = urllib.parse.urlencode({
            'api_key': api_key,
            'confidence': os.getenv('ROBOFLOW_CONFIDENCE', '35'),
            'overlap': os.getenv('ROBOFLOW_OVERLAP', '30'),
        })
        url = f'https://detect.roboflow.com/{model_id}?{params}'
        req = urllib.request.Request(
            url,
            data=encoded_image.encode('utf-8'),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode('utf-8'))

        predictions = payload.get('predictions') or []
        if not predictions:
            return {
                'label': 'no_visible_damage', 'confidence': 0.0,
                'severity': 'STABLE', 'model': 'roboflow_professional',
                'predictions': []
            }

        strongest = max(predictions, key=lambda item: item.get('confidence', 0))
        label = strongest.get('class') or strongest.get('class_name') or 'unknown_damage_state'
        confidence = float(strongest.get('confidence', 0)) * 100
        result = normalize_damage_prediction(label, confidence)
        result['model'] = 'roboflow_professional'
        result['predictions'] = predictions
        return result
    except Exception as exc:
        print(f'Roboflow API error: {exc}')
        return None


def _open_image(file_bytes):
    """Open an image and correct for EXIF rotation (common on phone photos)."""
    image = Image.open(io.BytesIO(file_bytes)).convert('RGB')
    return ImageOps.exif_transpose(image)


def classify_with_heuristic(file_bytes):
    """
    Lightweight, dependency-free fallback used when neither a local TFLite
    model nor Roboflow is configured. This replaces the previous YOLOv8/COCO
    fallback, which could never detect damage because COCO's generic object
    classes (person, car, dog, ...) never match damage keywords.

    Uses simple, explainable image statistics as a rough proxy for damage
    severity: edge density (cracks/debris create high-frequency edges),
    dark-region ratio (shadowed rubble/voids), and color variance (uniform,
    intact surfaces are more color-consistent than debris fields). This is
    intentionally conservative and clearly labeled as a fallback in its
    'model' field — it is NOT a substitute for a trained damage classifier
    or a Roboflow model, and should be treated as a rough triage signal only.
    """
    try:
        image = _open_image(file_bytes)
        image = image.resize((256, 256), Image.Resampling.BILINEAR)
        gray = np.asarray(image.convert('L'), dtype=np.float32)
        rgb = np.asarray(image, dtype=np.float32)

        gx = np.abs(np.diff(gray, axis=1))
        gy = np.abs(np.diff(gray, axis=0))
        edge_density = (np.mean(gx) + np.mean(gy)) / 2.0

        dark_ratio = float(np.mean(gray < 60))
        color_std = float(np.mean(np.std(rgb, axis=(0, 1))))

        score = (
            min(edge_density / 40.0, 1.0) * 45
            + min(dark_ratio * 2.0, 1.0) * 30
            + min(color_std / 70.0, 1.0) * 25
        )

        if score >= 65:
            label, severity = 'major_structural_damage', 'CRITICAL'
        elif score >= 35:
            label, severity = 'minor_structural_damage', 'STABLE'
        else:
            label, severity = 'no_visible_damage', 'STABLE'

        confidence = min(60.0, 30.0 + abs(score - 50) * 0.6)

        return {
            'label': label,
            'confidence': round(confidence, 2),
            'severity': severity,
            'model': 'heuristic_fallback',
            'note': 'Local heuristic estimate only — configure Roboflow or a trained TFLite model for reliable results.',
        }
    except Exception as exc:
        print(f'Heuristic fallback error: {exc}')
        return None


def classify_image(file_bytes: bytes) -> dict:
    """Assess with professional vision first, then local/hosted classifiers and a labeled fallback."""
    professional_result = classify_with_vision_llm(file_bytes)
    if professional_result:
        return professional_result

    tflite_result = classify_with_tflite(file_bytes)
    if tflite_result and tflite_result.get('confidence', 0) >= TFLITE_CONFIDENCE_THRESHOLD * 100:
        result = tflite_result
    else:
        hosted_result = classify_with_roboflow(file_bytes)
        if hosted_result:
            result = hosted_result
        else:
            heuristic_result = classify_with_heuristic(file_bytes)
            result = heuristic_result or {
                'label': 'analysis_error', 'confidence': 0.0,
                'severity': 'UNKNOWN', 'model': 'unavailable'
            }

    result.setdefault('recommendation', get_repair_recommendation(result['label']))
    return result
