# AGENTS.md

## Mission

Build DamageSense AI as a high-trust visual field-inspection tool. Prefer clarity, evidence, and operational usefulness over generic AI-product patterns.

## Working rules

- Read the relevant route, model, template, and test before editing.
- Preserve existing Flask endpoints and response compatibility unless the task explicitly changes the contract.
- Keep secrets in environment variables. Never commit real API keys, database URLs, passwords, or tokens.
- Use additive database migrations and preserve existing production data.
- Treat all AI output as first-pass decision support. Keep human-review language visible for safety-critical cases.
- Protect admin actions server-side and retain audit events for consequential changes.
- Keep optional analytics consent-based and avoid unnecessary third-party payloads.
- Use the shared `static/theme.css` design system before adding one-off colors.
- Avoid default purple gradients, chatbot layouts, excessive rounded cards, and decorative motion without purpose.

## Visual direction

The interface is a field instrument, not a conventional AI dashboard. Use forest green for operational surfaces, navy for depth and evidence panels, dark red for hazards and critical states, and light blue for actions, confidence, and focus. Prefer asymmetric layouts, strong labels, compact status chips, editorial spacing, and subtle grid/scanline textures.

## Validation

Run:

```bash
python3 -m compileall -q app run.py
pytest -q
git diff --check
```

For public-site changes, check `/`, `/privacy`, `/terms`, `/robots.txt`, `/sitemap.xml`, `/static/favicon.svg`, and a representative 404 path. For auth changes, test registration, verification, logout, repeat login, password reset, disabled users, and admin access. For assessment changes, test upload validation, immediate JSON output, structured rendering, fallback behavior, and history persistence.

## Deployment

Render deploys from `main`. Confirm `DATABASE_URL` points to persistent PostgreSQL, `FLASK_SECRET_KEY` is stable, and provider variables are configured in Render rather than the repository. After pushing, check Render logs and health endpoint before declaring the release complete.

## Commit style

Use concise imperative commits such as `Improve assessment result clarity` or `Add verified registration flow`. Keep documentation changes close to the implementation they describe.
