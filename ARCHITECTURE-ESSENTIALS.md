# Architecture Essentials

## One-sentence summary

DamageSense AI is a server-rendered Flask field-inspection application that accepts authenticated image submissions, runs server-side damage triage, persists structured results, and exposes protected administration tools.

## Must-know boundaries

1. **The browser is untrusted.** Validate authorization and request state on the server.
2. **Provider keys stay server-side.** Never place `VISION_API_KEY`, `SENDGRID_API_KEY`, `DATABASE_URL`, or `FLASK_SECRET_KEY` in templates, JavaScript, logs, or commits.
3. **PostgreSQL is the production source of truth.** SQLite is for local development unless deliberately mounted on persistent storage.
4. **Assessment output is decision support.** It is not an engineering certification, emergency determination, or substitute for an on-site inspection.
5. **Migrations are additive.** Existing Render data must not be dropped or rewritten during startup.
6. **Admin operations are server-guarded.** Hiding a link in the UI is not authorization.
7. **Email tokens are one-time secrets.** Store hashes, enforce expiry, and clear them after use.

## Key paths

| Path | Purpose |
|---|---|
| `app/routes.py` | HTTP routes, authentication, authorization, exports, public SEO endpoints |
| `app/models.py` | SQLAlchemy entities and serialization |
| `app/ai_engine.py` | Model adapter and fallback analysis chain |
| `app/email_service.py` | SendGrid-compatible email delivery |
| `app/__init__.py` | Flask factory, configuration, additive migrations, admin provisioning |
| `templates/upload.html` | Authenticated assessment workspace and immediate result rendering |
| `static/theme.css` | Shared visual system overrides |
| `tests/test_app.py` | Regression suite for public, auth, assessment, admin, and verification flows |

## Production variables

Required production variables are `FLASK_SECRET_KEY` and `DATABASE_URL`. Add `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` to provision the first administrator. Add `SENDGRID_*` variables before enabling `REQUIRE_EMAIL_VERIFICATION=true`. Add `VISION_*` variables to activate the professional multimodal provider.

## Change discipline

Prefer small, additive changes. Keep response contracts backwards-compatible. Add a regression test for every authentication, migration, provider, export, or public-route change. Run `python3 -m compileall -q app run.py && pytest -q && git diff --check` before pushing.
