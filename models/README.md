# DamageSense TensorFlow Lite model

Place the **trained damage-specific TensorFlow Lite classifier** in this directory as `damage_model.tflite` and the matching class list as `labels.txt`.

Recommended environment variables:

- `DAMAGE_TFLITE_MODEL_PATH=models/damage_model.tflite`
- `DAMAGE_TFLITE_LABELS_PATH=models/labels.txt`
- `DAMAGE_TFLITE_CONFIDENCE=0.35`
- `DAMAGE_TFLITE_NORMALIZE=0_1` (use `minus1_1` when the model was trained with [-1, 1] normalization)

The model must be compatible with the input/output handling in `app/ai_engine.py`. The current integration supports float, uint8 and int8 image inputs and dequantizes quantized classification outputs.

Do not commit private API keys. Configure `ROBOFLOW_API_KEY` and `ROBOFLOW_MODEL_ID` through environment variables when using the hosted fallback.
