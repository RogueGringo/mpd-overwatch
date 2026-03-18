---
layout: default
title: Production Deployment Architecture
---

# Production Deployment Architecture

## Current State (v1.0.0-beta)

The platform runs as a local Dash application. All computation is verified
(28/28 V&V benchmarks A+). The package installs via `pip install -e .` and
serves at `http://127.0.0.1:8050`.

## Immediate Deployment (Render.com)

The existing Dash app deploys to Render.com free tier using:

- `render.yaml` - service configuration
- `src/mpd_overwatch/wsgi.py` - WSGI entry point for gunicorn
- `Dockerfile` - container build for any cloud provider

No architecture changes needed. The existing app serves as-is.

## Production Architecture (Future)

For multi-user, authenticated, real-time deployment:

```
Browser (HTTPS)
    |
  Nginx (TLS termination)
    |
    ├── /api/*  → FastAPI (auth, REST endpoints, pipeline orchestration)
    ├── /dash/* → Dash app (mounted as sub-app, JWT-protected)
    └── /       → Landing page + login
```

### Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI + uvicorn | Auth, REST endpoints, task orchestration |
| Dashboard | Existing Dash app | Interactive visualization (7 pages) |
| Database | PostgreSQL | Users, wells, files, cached pipeline results |
| Task Queue | Celery + Redis | Async topology computation (L2 pipeline) |
| File Storage | S3 or local disk | LAS/EDR file uploads |
| Auth | JWT (python-jose) | Role-based access: admin/supervisor/operator/viewer |

### User Roles

| Role | Dashboard | Upload | Tune Thresholds | Generate Proposals |
|------|-----------|--------|-----------------|-------------------|
| viewer | Read-only | No | No | No |
| operator | HMU + Supervisory | Own wells | No | No |
| supervisor | All panels | Org wells | Yes | Yes |
| admin | Everything | Yes | Yes | Yes |

### Database Schema

Wells and analysis results stored in PostgreSQL with row-level security
by organization. Pipeline results cached as JSONB for fast retrieval.
The existing `PipelineResult.to_dict()` serializer feeds directly into
the database layer.

### Key Principle

The production architecture wraps the existing physics engines.
No equations change. No V&V results change. The computation layer
is verified. The operationalization layer (auth, database, async tasks)
is infrastructure built around it.
