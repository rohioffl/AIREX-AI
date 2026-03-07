# Draft: Backend Restructure to Professional Layout

## Requirements (confirmed)
- "Both — reorganize AND split": Reorganize modules AND improve service boundaries
- Pain points: core/ overloaded, hard to navigate, services coupled, missing standard dirs, flat doesn't scale
- User wants "professional level structure" for the whole application

## Research Findings

### Codebase Stats
- ~100+ Python files in backend/app/
- 7 main modules: actions (12), api (14), cloud (16), core (15), investigations (14), llm (3), models (8+), rag (2), schemas (?), services (16)
- Two entry points: main.py (FastAPI), core/worker.py (ARQ)
- Import flow: api → services → models/core, worker → services → core

### Best Practices (from librarian)
- Netflix Dispatch & KeepHQ use Domain-Driven Design for similar incident platforms
- Professional standard: group by business domain, not technical layer
- Pure service functions (no FastAPI Depends in business logic)
- Two thin entry points (main.py, worker.py) wrapping shared domain logic

## Technical Decisions
- (pending) Domain-driven vs hybrid approach
- (pending) Target directory structure
- (pending) Incremental vs big-bang migration
- (pending) Test migration strategy

## Open Questions
- Cloud module: split by provider (aws/, gcp/) or keep flat?
- State machine: stays in core/ or moves to incident domain?
- Worker tasks: extracted into per-domain tasks.py files or kept centralized?
- Schemas: colocated with domains or separate?

## Scope Boundaries
- INCLUDE: All backend/app/ restructuring (domain-driven)
- INCLUDE: Frontend restructuring (feature-based)
- INCLUDE: Deployment config path updates
- INCLUDE: Import path updates across all files
- INCLUDE: Test file reorganization
- INCLUDE: Dockerfile/entry point updates if paths change
- EXCLUDE: Database schema changes (no new migrations)
- EXCLUDE: Feature changes (pure refactor — behavior stays identical)
- EXCLUDE: Terraform IaC modifications
- EXCLUDE: Library version upgrades
- EXCLUDE: Bug fixes found during move
