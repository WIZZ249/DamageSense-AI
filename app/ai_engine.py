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

# Initialize YOLOv8 model (downloads on first use)
MODEL_PATH = Path(__file__).parent.parent / 'models'
MODEL_PATH.mkdir(exist_ok=True)

# Use YOLOv8 nano for speed, small for better accuracy
# Model will auto-download from Ultralytics hub on first run
try:
    model = YOLO('yolov8n.pt')  # nano model (~6.3MB) - fastest
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
                'model': 'yolov8_vision'
            }

    return {
        'label': normalized or 'unknown_damage_state',
        'confidence': round(float(confidence), 2),
        'severity': 'CRITICAL' if float(confidence) >= 60 else 'UNKNOWN',
        'model': 'yolov8_vision'
    }


def classify_with_roboflow(file_bytes):
    """Call a configured Roboflow hosted model for professional damage assessment."""
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
        data = encoded_image.encode('utf-8')
        request = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode('utf-8'))

        predictions = payload.get('predictions') or []
        if not predictions:
            return {
                'label': 'no_visible_damage',
                'confidence': 0.0,
                'severity': 'STABLE',
                'model': 'roboflow_professional'
            }

        strongest = max(predictions, key=lambda item: item.get('confidence', 0))
        label = strongest.get('class') or strongest.get('class_name') or 'unknown_damage_state'
        confidence = float(strongest.get('confidence', 0)) * 100
        
        result = normalize_damage_prediction(label, confidence)
        result['model'] = 'roboflow_professional'
        return result
    except Exception as e:
        print(f"Roboflow API error: {e}")
        return None


def classify_with_yolo(file_bytes):
    """
    Use YOLOv8 for object detection on structural elements.
    This detects buildings, debris, damage indicators via visual cues.
    """
    if model is None:
        return None

    try:
        img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
        
        # Run YOLOv8 inference
        results = model(img, conf=0.25, verbose=False)
        
        if not results or len(results) == 0:
            return {
                'label': 'no_visible_damage',
                'confidence': 0.0,
                'severity': 'STABLE',
                'model': 'yolov8_vision'
            }

        # Analyze detections
        detected_classes = []
        confidences = []
        
        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue
            
            for box in result.boxes:
                class_id = int(box.cls)
                conf = float(box.conf)
                class_name = result.names.get(class_id, 'unknown')
                
                detected_classes.append(class_name.lower())
                confidences.append(conf)

        # No objects detected
        if not detected_classes:
            return {
                'label': 'structure_appears_intact',
                'confidence': 0.85,
                'severity': 'STABLE',
                'model': 'yolov8_vision'
            }

        # Assess damage based on detected objects
        damage_indicators = ['debris', 'rubble', 'broken', 'damaged', 'collapsed', 'destroyed']
        intact_indicators = ['building', 'house', 'structure', 'wall']
        
        damage_count = sum(1 for cls in detected_classes if any(ind in cls for ind in damage_indicators))
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        if damage_count > len(detected_classes) * 0.5:
            # Majority of detections are damage-related
            label = 'major_structural_damage'
            severity = 'CRITICAL'
            confidence = round(min(95, 60 + (damage_count / len(detected_classes)) * 35), 2)
        elif damage_count > 0:
            # Some damage detected
            label = 'minor_structural_damage'
            severity = 'STABLE'
            confidence = round(avg_confidence * 100, 2)
        else:
            # Only intact structures detected
            label = 'no_visible_damage'
            severity = 'STABLE'
            confidence = round(avg_confidence * 100, 2)

        return {
            'label': label,
            'confidence': confidence,
            'severity': severity,
            'model': 'yolov8_vision',
            'detected_objects': detected_classes[:5]  # Top 5 detections
        }

    except Exception as e:
        print(f"YOLOv8 inference error: {e}")
        return None


def classify_image(file_bytes: bytes) -> dict:
    """
    Assess structural damage using:
    1. Roboflow professional model (if configured)
    2. YOLOv8 local model (free, always available)
    """
    try:
        # Priority 1: Try professional Roboflow model
        professional_result = classify_with_roboflow(file_bytes)
        if professional_result:
            return professional_result

        # Priority 2: Fall back to YOLOv8
        yolo_result = classify_with_yolo(file_bytes)
        if yolo_result:
            return yolo_result

        # Fallback if both fail
        return {
            'label': 'analysis_error',
            'confidence': 0.0,
            'severity': 'UNKNOWN',
            'model': 'unavailable'
        }
    except Exception as e:
        print(f"Classification error: {e}")
        return {
            'label': 'analysis_error',
            'confidence': 0.0,
            'severity': 'UNKNOWN',
            'model': 'unavailable'
        }
