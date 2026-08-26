# DamageSense AI

DamageSense AI is a Flask dashboard for rapid structural damage assessment. Users can register, log in, upload or capture building images, and keep assessment history private to their own account.

## What It Does

- User registration and login
- Secure administrator console with user directory, role management, and account activation controls
- SendGrid registration and password-reset notifications
- Administrator CSV/PDF exports, activity metrics, and audit logs
- Public SEO landing page with canonical metadata, Open Graph tags, JSON-LD, robots.txt, sitemap.xml, and Search Console verification support
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
│   ├── upload.html
│   ├── admin.html
│   └── error.html
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
| `GET/POST` | `/forgot-password` | Request a password reset email |
| `GET/POST` | `/reset-password/<token>` | Complete a one-time password reset |
| `GET` | `/logout` | Log out |
| `GET` | `/home` | User dashboard |
| `GET` | `/admin` | Administrator user-management console |
| `POST` | `/admin/users/<id>/toggle-active` | Enable or disable a user (administrator only) |
| `POST` | `/admin/users/<id>/toggle-role` | Promote or demote a user (administrator only) |
| `GET` | `/admin/exports/assessments.csv` | Download all assessments as CSV (administrator only) |
| `GET` | `/admin/exports/assessments.pdf` | Download all assessments as PDF (administrator only) |
| `POST` | `/assess` | Upload or camera-captured image assessment |
| `GET` | `/history` | Current user's latest 50 assessments |
| `GET` | `/health` | Health check |
| `GET` | `/robots.txt` | Crawler directives and sitemap location |
| `GET` | `/sitemap.xml` | Dynamic public URL sitemap |

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

## Administrator Access

The app provisions an administrator from Render environment variables at startup. Credentials are never stored in GitHub and there is intentionally no public “make me admin” action. The administrator account is created or promoted when the service starts.

### Exact Render setup

1. Open the [Render service dashboard](https://dashboard.render.com/web/srv-d6q63ehj16oc73d21ilg) and select **Environment**.
2. Add or update these variables. Use your own values; do not copy this example literally:

```text
ADMIN_USERNAME=admin
ADMIN_EMAIL=your-real-admin-email@example.com
ADMIN_PASSWORD=use-a-long-unique-password-at-least-8-characters
ADMIN_RESET_PASSWORD=false
```

3. Click **Save Changes**. Render normally starts a new deploy; if it does not, open **Manual Deploy** and deploy the latest commit from `main`.
4. Wait for the deploy to finish successfully. Provisioning occurs during application startup, so saving variables without a restart does not create the account.
5. Open `https://damagesense-ai-1.onrender.com/login` and enter either the exact admin username or email plus the configured password. A successful admin login redirects to `/admin`.

The account is created if it does not exist, or promoted to administrator if the configured email or username already exists. The password is not changed on later restarts unless `ADMIN_RESET_PASSWORD=true` is explicitly set. Use that flag only for an intentional password rotation, redeploy once, then set it back to `false` and redeploy again.

### If the admin login still fails

First confirm that all four variables are spelled exactly as shown and that there are no surrounding quotation marks or trailing spaces. Confirm that `ADMIN_PASSWORD` is at least eight characters. Then check **Render → Logs** for `Provisioned configured admin account` or `Verified configured admin access`. If those messages are absent, the variables were not available to the running service or the deploy did not restart the application.

The application must use a persistent database in Render. If `DATABASE_URL` is missing, the app falls back to SQLite, and accounts can disappear when the service restarts or a new instance is created. In Render, create a PostgreSQL database, copy its **Internal Database URL**, and add it to the web service as:

```text
DATABASE_URL=postgresql://...internal-render-database-url...
```

Then redeploy. Do not use an ephemeral local SQLite file for production user accounts. If you intentionally use SQLite, attach a Render persistent disk and configure the database and upload paths on that disk.

After the first successful login, store the credentials in a password manager. Do not commit them to `.env`, source code, or GitHub.

## Public SEO and Google Search Console

The anonymous root route is a public, crawlable landing page. It includes a descriptive title and meta description, canonical URL, Open Graph metadata, JSON-LD for the organization, website, and web application, accessible content sections, internal links, and a public FAQ. Authenticated routes remain disallowed in `robots.txt`, while `/robots.txt` and `/sitemap.xml` are generated from `PUBLIC_SITE_URL`.

Set `PUBLIC_SITE_URL` to the canonical Render URL. For the simplest Search Console ownership verification, copy the HTML-tag token Google gives you into `GOOGLE_SITE_VERIFICATION` and redeploy. The landing page will emit the required `<meta name="google-site-verification">` tag. Alternatively, set `GOOGLE_SITE_VERIFICATION_FILE` to Google's exact HTML filename and `GOOGLE_SITE_VERIFICATION_TOKEN` to its token; the application will serve the verification file from the site root.

After deployment, open [Google Search Console](https://search.google.com/search-console), add a **URL-prefix property** for `https://damagesense-ai-1.onrender.com/`, complete ownership verification, open **Sitemaps**, submit `sitemap.xml`, then use **URL inspection** to request indexing for the homepage. Search Console submission requires the site owner's authenticated Google account and cannot be automated from the application.

## Email Notifications

Set the following variables in Render to enable registration and password-reset emails through SendGrid's v3 Mail Send API. Use a verified sender/domain and a key with Mail Send permission.

```text
SENDGRID_API_KEY=your_sendgrid_api_key
SENDGRID_FROM_EMAIL=verified-sender@example.com
SENDGRID_FROM_NAME=DamageSense AI
```

If email is not configured, registration and reset requests still complete safely, while the admin console shows the delivery status as not configured. Password reset responses do not reveal whether an email is registered.

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
4. Add the administrator variables from the section above, using a unique password stored in a password manager.
5. Deploy from `main`.

For production, use a Render PostgreSQL database. This is required for reliable account, assessment, reset-token, and audit-log persistence across deploys and restarts. If you already have a persistent Render disk attached, SQLite can be used only when `DATABASE_URL` and `UPLOAD_FOLDER` point to that mounted disk.

## License

MIT
