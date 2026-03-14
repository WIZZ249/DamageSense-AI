import numpy as np
from PIL import Image, ImageStat
import io

# -- Keywords for severity classification ------------------------------------
CRITICAL_KEYWORDS = [
    'rubble', 'ruin', 'wreckage', 'debris', 'collapse',
    'destruction', 'damage', 'broken', 'flood', 'fire',
    'earthquake', 'disaster', 'crack', 'demolition'
]

def classify_image(file_bytes: bytes) -> dict:
    """
    Lightweight image analysis using Pillow.
    Analyses colour, brightness, contrast and entropy to assess damage.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
        img_resized = img.resize((224, 224))

        # Get image statistics
        stat = ImageStat.Stat(img_resized)
        r_mean, g_mean, b_mean = stat.mean[0], stat.mean[1], stat.mean[2]
        r_std, g_std, b_std = stat.stddev[0], stat.stddev[1], stat.stddev[2]

        brightness = (r_mean + g_mean + b_mean) / 3
        contrast = (r_std + g_std + b_std) / 3

        # Convert to greyscale for entropy
        grey = img_resized.convert('L')
        grey_arr = np.array(grey)
        hist = np.histogram(grey_arr, bins=256, range=(0, 255))[0]
        hist_norm = hist / hist.sum()
        hist_norm = hist_norm[hist_norm > 0]
        entropy = float(-np.sum(hist_norm * np.log2(hist_norm)))

        # Damage heuristics
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
            'severity': severity
        }

    except Exception as e:
        return {
            'label': f'analysis_error',
            'confidence': 0.0,
            'severity': 'UNKNOWN'
        }
