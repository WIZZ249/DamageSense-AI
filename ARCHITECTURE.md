# DamageSense AI — Architecture

## System overview

DamageSense AI is a server-rendered Flask application with a relational persistence layer, server-side image inference, transactional email delivery, and a browser workspace for assessment capture and review.

```text
Browser
  │ HTTPS, CSRF-protected forms, JSON assessment requests
  ▼
Flask application
  ├── Public routes: landing, legal pages, robots, sitemap, verification
  ├── Auth routes: register, verify email, login, logout, password reset
  ├── Workspace routes: upload, assessment, history, exports
  ├── Admin routes: user controls, metrics, audit logs, CSV/PDF exports
  ├── Assessment adapter: professional multimodal provider → safe fallback chain
  ├── Email adapter: SendGrid transactional delivery
  └── Compatibility migrations: additive schema updates at startup
  │
  ├── PostgreSQL in production / SQLite for local development
  ├── Object/filesystem upload storage
  └── External providers configured only through environment variables
```

## Runtime boundaries

The browser owns presentation, camera capture, previews, tab state, and result rendering. It never receives model-provider credentials, database credentials, or SendGrid credentials. Flask owns authentication, authorization, validation, file handling, inference orchestration, persistence, and exports.

The professional vision model is accessed through an OpenAI-compatible server-side API. The application accepts structured JSON when available and normalizes provider output into the internal analysis contract. If the provider is not configured or fails, the classifier falls back to the configured local model, Roboflow integration, or a clearly labeled heuristic result.

## Domain model

| Entity | Responsibility |
|---|---|
| `User` | Identity, password hash, role, active state, email verification, reset token state |
| `Assessment` | User-owned image reference, classification, confidence, severity, recommendation, structured analysis JSON, timestamp |
| `AuditLog` | Actor, target, action, metadata, IP address, and timestamp for operational traceability |

Sensitive token values are stored only as hashes. Verification and reset tokens are time-limited and invalidated after use.

## Request flows

### Registration and verification

A new registration validates credentials, creates a pending user, generates a random token, stores only its hash, and sends a verification link through SendGrid. The verification endpoint hashes the presented token, checks expiry, marks the user verified, clears the token, records an audit event, and redirects to login. Existing accounts are trusted during the additive migration to avoid locking out current users.

### Assessment

An authenticated user submits an image. Flask validates the file, stores it in the configured upload folder, invokes the assessment adapter, normalizes the response, stores the structured analysis, records an audit event, and returns JSON. The workspace renders the result card immediately and updates history without a second request.

### Administration

Admin access is role-based and guarded server-side. Admin provisioning is environment-driven at startup. State-changing user-management requests use CSRF protection. The last active administrator cannot be removed or disabled through the console.

## Deployment

Render runs the web service from the `main` branch. Production requires `DATABASE_URL` pointing at the internal Render PostgreSQL URL, a stable `FLASK_SECRET_KEY`, and explicit provider configuration. Deployments use additive startup migrations because the project is intentionally lightweight and does not yet ship a full migration runner.

## Failure behavior

Provider failures produce a safe fallback result rather than a fabricated professional conclusion. Missing SendGrid configuration logs a controlled warning and does not expose credentials or provider details to users. Invalid authentication, disabled accounts, expired tokens, and unauthorized admin access return explicit but non-disclosing responses.

## Security posture

Passwords are hashed with Werkzeug. Sessions are HTTP-only and SameSite-limited. CSRF protection is enabled by default. Admin and export routes require active authenticated administrators. Public SEO routes exclude private workspaces from crawling. Production credentials belong in Render environment variables only.

## Observability

Audit events capture registrations, login success/failure, assessments, password resets, verification, role/status changes, and exports. The admin dashboard aggregates counts and recent activity for operational review. Provider and email delivery failures are logged server-side without logging secrets or full tokens.
