# Architecture Essentials

## One-sentence summary

DamageSense AI is a server-rendered Flask field-inspection application that accepts authenticated images and optional GPS coordinates, runs server-side damage triage, persists structured results, and visualizes scoped damage clusters on a protected Leaflet map.

## Must-know boundaries

1. The browser is untrusted; validate authorization, CSRF, uploads, and coordinates on the server.
2. Provider keys stay server-side. Never place vision, email, database, or session secrets in templates, JavaScript, logs, or commits.
3. PostgreSQL is the production source of truth. SQLite is for local development unless deliberately mounted on persistent storage.
4. Assessment output is decision support. It is not an engineering certification, emergency determination, or substitute for on-site inspection.
5. Migrations are additive. Existing Render data must not be dropped or rewritten during startup.
6. Admin map scope is enforced by the API, not by hiding a link.
7. GPS is optional. Legacy records without coordinates must remain visibly estimated on the map.

## Key paths

| Path | Purpose |
|---|---|
| `app/routes.py` | HTTP routes, authentication, authorization, assessment upload, map API, exports, SEO |
| `app/models.py` | SQLAlchemy entities, location fields, serialization |
| `app/ai_engine.py` | Model adapter and fallback analysis chain |
| `app/__init__.py` | Flask factory, configuration, additive migrations, admin provisioning |
| `templates/upload.html` | Authenticated assessment workspace, GPS capture, immediate result rendering |
| `templates/map.html` | Leaflet global damage cluster map and filters |
| `static/theme.css` | Shared Watermelon UI token and component overrides |
| `tests/test_app.py` | Regression suite |

## Required validation

Run `python3 -m compileall -q app run.py && pytest -q && git diff --check`. Manually confirm anonymous requests cannot access `/map` or `/api/map-data`, ordinary users cannot receive other users’ points, and admin users receive the global scope.
