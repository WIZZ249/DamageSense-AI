import base64
import io
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from ultralytics import YOLO

# Optional local TensorFlow Lite model. Set DAMAGE_TFLITE_MODEL_PATH to enable it.
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
        import tensorflow as tf

        _tflite_interpreter = tf.lite.Interpreter(model_path=str(TFLITE_MODEL_PATH), num_threads=2)
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

    # Quantized models need uint8/int8 input. Float models use normalized pixels.
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
        # Most float damage classifiers expect [0, 1]. Allow configurable mode.
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
        image = Image.open(io.BytesIO(file_bytes)).convert('RGB')
        input_detail = _tflite_input_details[0]
        input_tensor = _tflite_preprocess(image, input_detail)
        _tflite_interpreter.set_tensor(input_detail['index'], input_tensor)
        _tflite_interpreter.invoke()

        # Classification models normally expose one [1, classes] tensor.
        output = _tflite_interpreter.get_tensor(_tflite_output_details[0]['index'])
        scores = np.asarray(output).squeeze()
        if scores.ndim != 1:
            return None

        # Dequantize output when necessary.
        output_detail = _tflite_output_details[0]
        if np.issubdtype(scores.dtype, np.integer):
            scale, zero_point = output_detail.get('quantization', (0.0, 0))
            if scale:
                scores = (scores.astype(np.float32) - zero_point) * scale

        # Handle logits as well as probability outputs.
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


# Initialize YOLOv8 model lazily for fallback operation.
try:
    model = YOLO('yolov8n.pt')
except Exception:
    model = None

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
        request = urllib.request.Request(
            url,
            data=encoded_image.encode('utf-8'),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )

        with urllib.request.urlopen(request, timeout=20) as response:
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


def classify_with_yolo(file_bytes):
    """Fallback object detection using the existing YOLOv8 model."""
    if model is None:
        return None

    try:
        img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
        results = model(img, conf=0.25, verbose=False)
        if not results:
            return None

        detected_classes = []
        confidences = []
        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue
            for box in result.boxes:
                class_id = int(box.cls)
                detected_classes.append(result.names.get(class_id, 'unknown').lower())
                confidences.append(float(box.conf))

        if not detected_classes:
            return {'label': 'no_visible_damage', 'confidence': 0.0, 'severity': 'STABLE', 'model': 'yolov8_vision'}

        damage_indicators = ['debris', 'rubble', 'broken', 'damaged', 'collapsed', 'destroyed']
        damage_count = sum(1 for cls in detected_classes if any(ind in cls for ind in damage_indicators))
        avg_confidence = float(np.mean(confidences)) if confidences else 0.0

        if damage_count > len(detected_classes) * 0.5:
            label, severity = 'major_structural_damage', 'CRITICAL'
            confidence = min(95.0, 60 + (damage_count / len(detected_classes)) * 35)
        elif damage_count > 0:
            label, severity, confidence = 'minor_structural_damage', 'STABLE', avg_confidence * 100
        else:
            label, severity, confidence = 'no_visible_damage', 'STABLE', avg_confidence * 100

        return {
            'label': label,
            'confidence': round(confidence, 2),
            'severity': severity,
            'model': 'yolov8_vision',
            'detected_objects': detected_classes[:5]
        }
    except Exception as exc:
        print(f'YOLOv8 inference error: {exc}')
        return None


def classify_image(file_bytes: bytes) -> dict:
    """Assess damage with this priority: local TFLite -> Roboflow -> YOLOv8."""
    tflite_result = classify_with_tflite(file_bytes)
    if tflite_result and tflite_result.get('confidence', 0) >= TFLITE_CONFIDENCE_THRESHOLD * 100:
        return tflite_result

    professional_result = classify_with_roboflow(file_bytes)
    if professional_result:
        return professional_result

    yolo_result = classify_with_yolo(file_bytes)
    if yolo_result:
        return yolo_result

    return {
        'label': 'analysis_error', 'confidence': 0.0,
        'severity': 'UNKNOWN', 'model': 'unavailable'
    }
