# Backend Service Images

This directory defines the deployable backend container targets for AIREX.

- `api` target: FastAPI application runtime
- `worker` target: ARQ background worker runtime

Both targets intentionally package the shared Python application source from `backend/`.
The deployable services are separate containers, but they run from the same backend codebase.
