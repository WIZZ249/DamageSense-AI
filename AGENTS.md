# AGENTS.md

## Mission

Build DamageSense AI as a high-trust visual field-inspection tool. Prefer evidence, operational usefulness, privacy, and explicit uncertainty over generic AI-product patterns.

## Working rules

- Read the relevant route, model, template, and test before editing.
- Preserve existing Flask endpoints and response compatibility unless the task explicitly changes the contract.
- Keep secrets in environment variables and use additive database migrations.
- Treat AI output and estimated map coordinates as decision-support data, not ground truth.
- Enforce admin and user data scope server-side.
- Use the shared Watermelon UI tokens before adding one-off colors.
- Keep motion purposeful and honor `prefers-reduced-motion`.
- Avoid default purple gradients, chatbot layouts, and decorative map effects that obscure severity.

## Watermelon visual direction

Use zinc-950/900 canvases, emerald operational states, coral-crimson critical states, amber attention states, and sky evidence/action accents. Prefer asymmetric bento-grid composition, compact status labels, editorial spacing, strong focus outlines, and mobile-first layouts.

## Validation

Run:

```bash
python3 -m compileall -q app run.py
pytest -q
git diff --check
```

For map changes, test `/map`, `/api/map-data`, severity filters, cluster popups, GPS permission denial, invalid coordinates, legacy estimated points, anonymous rejection, ordinary-user scoping, and admin global scope.

## Deployment

Render deploys from `main`. Confirm persistent PostgreSQL, stable `FLASK_SECRET_KEY`, model variables, and email configuration. After pushing, check Render logs, `/health`, authenticated assessment, map rendering, and the browser console for CDN or tile failures.

## Commit style

Use concise imperative commits such as `Add global damage cluster map` or `Refresh interface with Watermelon UI tokens`.
