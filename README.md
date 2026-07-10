# DamageSense AI

DamageSense AI is a Flask dashboard for rapid structural damage assessment. Users can register, log in, upload or capture building images, and keep assessment history private to their own account.

## What It Does

- User registration and login
- Private per-user assessment dashboards
- Image upload assessment
- Live camera capture assessment on HTTPS deployments
- Server-backed assessment history
- Optional professional hosted model integration through Roboflow
- Local lightweight image-analysis fallback when no hosted model is configured

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask 3 |
| Database | SQLAlchemy, SQLite |
| Image Processing | Pillow, NumPy |
| Optional Hosted AI | Roboflow hosted detection/segmentation model |
| Frontend | HTML, Bootstrap, browser camera APIs |
| Testing | Pytest |
| Deployment | Gunicorn, Render.com |

## Project Structure

```text
DamageSense-AI/
├── app/
│   ├── __init__.py
│   ├── routes.py
│   ├── models.py
│   ├── ai_engine.py
│   └── static/uploads/
├── templates/
│   ├── login.html
│   ├── register.html
│   └── upload.html
├── tests/test_app.py
├── .env.example
├── requirements.txt
├── run.py
└── README.md
```

## Local Setup

```bash
git clone https://github.com/WIZZ249/DamageSense-AI.git
cd DamageSense-AI
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Open `http://localhost:5000`.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Redirects to login or user home |
| `GET/POST` | `/register` | Create a user account |
| `GET/POST` | `/login` | Log in |
| `GET` | `/logout` | Log out |
| `GET` | `/home` | User dashboard |
| `POST` | `/assess` | Upload or camera-captured image assessment |
| `GET` | `/history` | Current user's latest 50 assessments |
| `GET` | `/health` | Health check |

## Professional Model Setup

The app works immediately with a local Pillow/NumPy fallback, but professional damage assessment should use a trained damage model.

Recommended path:

1. Train or choose a Roboflow hosted model for structural/building damage detection.
2. Use damage classes such as `no_damage`, `minor_damage`, `major_damage`, and `destroyed`.
3. In Render, add these environment variables:

```text
ROBOFLOW_API_KEY=your_api_key
ROBOFLOW_MODEL_ID=your-project/version
ROBOFLOW_CONFIDENCE=35
ROBOFLOW_OVERLAP=30
```

When these are present, `app/ai_engine.py` calls the hosted model first. If the hosted call fails or is not configured, the app falls back to local image analysis so uploads still work.

Recommended datasets and model families:

- RescueNet for high-resolution UAV disaster imagery
- xBD/xView2 for satellite before/after disaster damage assessment
- YOLO segmentation for fast object-level field use
- SegFormer for stronger semantic segmentation quality

## Camera Capture

The dashboard includes a `Take Picture` mode. Browser camera access requires HTTPS, which Render provides on deployed services. On phones, the upload field also hints to open the device camera.

## Running Tests

```bash
pytest tests/
```

## Deployment on Render

1. Connect this repository to Render.
2. Use start command:

```bash
gunicorn run:app --timeout 120 --workers 1
```

3. Add environment variables from `.env.example`.
4. Deploy from `main`.

For serious production use, replace SQLite with PostgreSQL so user accounts and assessment history persist reliably across restarts.

## License

MIT
