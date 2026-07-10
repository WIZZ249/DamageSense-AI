import base64
import io
import json
import os
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image, ImageStat


DAMAGE_LABELS = {
    'destroyed': ('destroyed_structure', 'CRITICAL'),
    'major': ('major_structural_damage', 'CRITICAL'),
    'severe': ('major_structural_damage', 'CRITICAL'),
    'collapsed': ('collapsed_structure', 'CRITICAL'),
    'collapse': ('collapsed_structure', 'CRITICAL'),
    'rubble': ('collapsed_structure', 'CRITICAL'),
    'minor': ('minor_structural_damage', 'STABLE'),
    'no_damage': ('no_visible_damage', 'STABLE'),
    'undamaged': ('no_visible_damage', 'STABLE'),
    'intact': ('no_visible_damage', 'STABLE'),
}


def normalize_damage_prediction(label, confidence):
    normalized = label.lower().replace('-', '_').replace(' ', '_')
    for key, mapped in DAMAGE_LABELS.items():
        if key in normalized:
            mapped_label, severity = mapped
            return {
                'label': mapped_label,
                'confidence': round(float(confidence), 2),
                'severity': severity,
                'model': 'professional'
            }

    return {
        'label': normalized or 'unknown_damage_state',
        'confidence': round(float(confidence), 2),
        'severity': 'CRITICAL' if float(confidence) >= 70 else 'UNKNOWN',
        'model': 'professional'
    }


def classify_with_roboflow(file_bytes):
    """Call a configured Roboflow hosted model for professional damage assessment."""
    api_key = os.getenv('ROBOFLOW_API_KEY')
    model_id = os.getenv('ROBOFLOW_MODEL_ID')
    if not api_key or not model_id:
        return None

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
            'model': 'professional'
        }

    strongest = max(predictions, key=lambda item: item.get('confidence', 0))
    label = strongest.get('class') or strongest.get('class_name') or 'unknown_damage_state'
    confidence = float(strongest.get('confidence', 0)) * 100
    return normalize_damage_prediction(label, confidence)


def classify_with_local_heuristics(file_bytes):
    """
    Lightweight image analysis using Pillow.
    This is the offline fallback when no hosted damage model is configured.
    """
    img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
    img_resized = img.resize((224, 224))

    stat = ImageStat.Stat(img_resized)
    r_mean, g_mean, b_mean = stat.mean[0], stat.mean[1], stat.mean[2]
    r_std, g_std, b_std = stat.stddev[0], stat.stddev[1], stat.stddev[2]

    brightness = (r_mean + g_mean + b_mean) / 3
    contrast = (r_std + g_std + b_std) / 3

    grey = img_resized.convert('L')
    grey_arr = np.array(grey)
    hist = np.histogram(grey_arr, bins=256, range=(0, 255))[0]
    hist_norm = hist / hist.sum()
    hist_norm = hist_norm[hist_norm > 0]
    entropy = float(-np.sum(hist_norm * np.log2(hist_norm)))

    dark = brightness < 80
    high_contrast = contrast > 60
    chaotic = entropy > 6.5
    reddish = r_mean > g_mean * 1.2 and r_mean > b_mean * 1.2

    damage_score = sum([dark, high_contrast, chaotic, reddish])

    if damage_score >= 3:
        label = 'severe_structural_damage'
        severity = 'CRITICAL'
        confidence = round(min(95, 70 + damage_score * 8), 2)
    elif damage_score == 2:
        label = 'moderate_damage_detected'
        severity = 'CRITICAL'
        confidence = round(min(80, 55 + damage_score * 8), 2)
    elif damage_score == 1:
        label = 'minor_irregularities'
        severity = 'STABLE'
        confidence = round(60 + contrast / 10, 2)
    else:
        label = 'structure_appears_intact'
        severity = 'STABLE'
        confidence = round(min(95, 75 + brightness / 10), 2)

    return {
        'label': label,
        'confidence': confidence,
        'severity': severity,
        'model': 'local_fallback'
    }


def classify_image(file_bytes: bytes) -> dict:
    """Assess structural damage using a configured professional model or local fallback."""
    try:
        professional_result = classify_with_roboflow(file_bytes)
        if professional_result:
            return professional_result
        return classify_with_local_heuristics(file_bytes)
    except Exception:
        try:
            return classify_with_local_heuristics(file_bytes)
        except Exception:
            return {
                'label': 'analysis_error',
                'confidence': 0.0,
                'severity': 'UNKNOWN',
                'model': 'unavailable'
            }
