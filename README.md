# 🏚️ DamageSense AI

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0.0-black?style=flat-square&logo=flask)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.15.0-orange?style=flat-square&logo=tensorflow)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

> AI-powered humanitarian dashboard for rapid structural damage assessment in disaster zones. Built with Flask, TensorFlow (MobileNetV2), and SQLAlchemy to support field-based disaster response.

---

## 📌 What It Does

DamageSense AI allows humanitarian field offices to upload images of structures and instantly receive:

- ✅ **AI Classification** — identifies what the image contains using MobileNetV2
- ✅ **Severity Rating** — automatically flags as `CRITICAL` or `STABLE`
- ✅ **Heuristic Override** — catches dangerous misclassifications (e.g. "Seashore" bug fix)
- ✅ **Assessment History** — all results saved to a local SQLite database
- ✅ **REST API** — JSON endpoints for integration with other systems

---

## 🖥️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask 3.0 |
| AI / ML | TensorFlow 2.15, MobileNetV2, Keras |
| Database | SQLAlchemy, SQLite |
| Frontend | Bootstrap 5, HTML5 |
| Testing | Pytest |
| Deployment | Gunicorn, Render.com |

---

## 📁 Project Structure
```
DamageSense-AI/
├── app/
│   ├── __init__.py       # App factory & database setup
│   ├── routes.py         # All Flask routes & API endpoints
│   ├── models.py         # SQLAlchemy database models
│   ├── ai_engine.py      # TensorFlow model & classification logic
│   └── static/
│       ├── css/          # Stylesheets
│       └── uploads/      # Uploaded images
├── templates/
│   └── upload.html       # Main dashboard UI
├── tests/
│   └── test_app.py       # Pytest test suite
├── .env.example          # Environment variable template
├── requirements.txt      # Python dependencies
├── run.py                # Application entry point
└── README.md
```

---

## ⚙️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/WIZZ249/DamageSense-AI.git
cd DamageSense-AI
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```

### 5. Run the application
```bash
python run.py
```

Visit **http://localhost:5000** in your browser.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main dashboard UI |
| `POST` | `/assess` | Upload image for AI assessment |
| `GET` | `/history` | Retrieve last 50 assessments |
| `GET` | `/health` | Health check for deployment |

### Example — POST `/assess`
```bash
curl -X POST http://localhost:5000/assess \
  -F "image=@/path/to/image.jpg"
```

### Example Response
```json
{
  "id": 1,
  "filename": "building.jpg",
  "label": "rubble",
  "confidence": 94.32,
  "severity": "CRITICAL",
  "timestamp": "2026-03-12 22:00:00"
}
```

---

## 🧪 Running Tests
```bash
pytest tests/
```

---

## 🐛 Known Issues Fixed

| Bug | Fix |
|---|---|
| MobileNetV2 classifying damaged buildings as "Seashore" | Implemented keyword-based heuristic override layer |
| Session persistence between requests | Implemented SQLAlchemy scoped_session pattern |

---

## 🚀 Deployment

This app is configured for deployment on **Render.com**:

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your `DamageSense-AI` repo
4. Set start command: `gunicorn run:app`
5. Click Deploy

---

## 👨‍💻 Author

**Ahmed Salaheldeen Alamin Sulieman**
IT Engineer | AWS Certified Cloud Practitioner | Developer

- 📧 ahmednoooors@gmail.com
- 🌐 [Portfolio](https://WIZZ249.github.io/yannis-portfolio)
- 💻 [GitHub](https://github.com/WIZZ249)

---

## 📄 License

This project is licensed under the MIT License.

---

*Built with purpose — for the people who need it most.*