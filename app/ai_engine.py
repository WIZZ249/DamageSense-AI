import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image as keras_image
from PIL import Image
import io

# ── Load model once at startup ──────────────────────────────────────────────
model = MobileNetV2(weights='imagenet')

# ── Keywords that trigger CRITICAL severity ──────────────────────────────────
CRITICAL_KEYWORDS = [
    'rubble', 'ruin', 'wreckage', 'debris', 'collapse',
    'destruction', 'damage', 'broken', 'flood', 'fire',
    'earthquake', 'disaster', 'crack', 'demolition'
]

def preprocess_image(file_bytes: bytes) -> np.ndarray:
    """Convert raw image bytes into a model-ready tensor."""
    img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
    img = img.resize((224, 224))
    arr = keras_image.img_to_array(img)
    arr = np.expand_dims(arr, axis=0)
    return preprocess_input(arr)

def classify_image(file_bytes: bytes) -> dict:
    """
    Run MobileNetV2 classification and apply heuristic severity override.

    Returns:
        dict with keys: label, confidence, severity
    """
    tensor = preprocess_image(file_bytes)
    predictions = model.predict(tensor)
    decoded = decode_predictions(predictions, top=3)[0]

    top_label      = decoded[0][1].lower().replace('_', ' ')
    top_confidence = float(decoded[0][2])

    # Heuristic override: check all top-3 labels for critical keywords
    all_labels = ' '.join([d[1].lower() for d in decoded])
    severity = 'CRITICAL' if any(kw in all_labels for kw in CRITICAL_KEYWORDS) else 'STABLE'

    return {
        'label':      top_label,
        'confidence': top_confidence,
        'severity':   severity
    }