# DamageSense AI — Product Requirements Document

## Product vision

DamageSense AI is a field-oriented visual triage workspace for roads, vehicles, buildings, bridges, utilities, and other visible structures. It converts an uploaded or captured image into a fast, explainable first-pass assessment while keeping qualified human review in the loop.

The product should feel like a calm, high-trust operations instrument rather than a generic AI chat interface. The visual language is based on dark forest-green field surfaces, navy instrument panels, dark-red risk signals, and light-blue evidence/action accents.

## Primary users

The primary users are inspectors, facilities teams, municipal operations staff, fleet managers, property owners, and administrators who need to document visible damage quickly. The product is not a structural certification tool and must communicate that distinction clearly.

## Core user outcomes

A user should be able to open the public site, understand the product within seconds, register or sign in, capture or upload an image, receive a detailed result immediately, and revisit prior assessments without losing context. An administrator should be able to monitor activity, manage accounts, inspect audit events, and export cross-user reports.

## Functional requirements

| Area | Requirement | Acceptance criterion |
|---|---|---|
| Assessment input | Support upload and camera capture | User can select, validate, preview, remove, or capture an image before submission |
| Multi-domain analysis | Assess roads, vehicles, buildings, bridges, utilities, and other visible structures | Result identifies an asset type or clearly labels uncertainty |
| Immediate results | Present results in the active assessment view | Result panel appears after the assessment response without requiring navigation to History |
| Explainability | Show findings, hazards, confidence rationale, and recommended actions | Every successful assessment includes actionable structured fields or safe fallback copy |
| Persistence | Save results to the authenticated user history | Refreshing the workspace preserves previously saved assessments |
| Account verification | Verify new accounts by email | New production registrations receive a one-time, expiring verification link |
| Administration | Provide protected user and audit controls | Only active admins can access admin routes or cross-user exports |
| Privacy | Keep optional analytics consent-based | Analytics does not load before explicit acceptance |
| Accessibility | Support keyboard, reduced motion, semantic labels, and mobile layouts | Core actions are usable without a mouse and on narrow screens |

## Visual and interaction direction

The experience uses a compact instrument-panel layout with asymmetric information density: a high-signal hero, a clear evidence capture surface, a result brief that behaves like an incident card, and a history table for deeper review. Motion is purposeful: loading states communicate progress, results rise into view, and hover states indicate affordances without excessive decoration.

The interface must avoid default gradients, oversized chatbot metaphors, purple-first palettes, and indistinguishable dashboard cards. Risk must be visually distinct from information: dark red is reserved for hazards and critical states, light blue marks evidence and actions, and forest green carries the operational shell.

## Non-functional requirements

The application must keep provider credentials server-side, use a persistent production database, avoid destructive migrations, protect state-changing requests with CSRF controls, and degrade safely when the professional model or email provider is unavailable. AI outputs must be described as decision support and not as engineering certification.

## Success measures

Success is measured by assessment completion rate, time from upload to visible result, repeat login success after logout, verification completion rate, percentage of assessments with structured findings, administrator export usage, and mobile form completion without layout errors.

## Release checklist

Before release, verify the Render service uses PostgreSQL, the secret key is stable, SendGrid sender/domain is verified, email verification is enabled only when email delivery is configured, the vision model variables are valid, public SEO routes return 200, private routes reject anonymous access, and the test suite passes.

## Future opportunities

Future iterations may add comparison timelines, offline capture queues, map-linked inspection locations, team workspaces, annotated image markup, calibrated confidence review, and a formal human-review workflow for safety-critical cases.
