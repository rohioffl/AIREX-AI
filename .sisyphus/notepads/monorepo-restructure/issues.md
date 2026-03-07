# Issues — monorepo-restructure

## [2026-03-07] Session ses_337dab47bffeuFoesH2qlm1kfg

### Known Pre-existing Issues (NOT to fix during structural move)
- LSP errors in backend files (redis, structlog, fastapi, sqlalchemy, arq) — caused by missing virtualenv on host, not code errors
- Type errors in `worker.py` `_send_to_dlq` (Exception passed as str) — will be fixed in Task 11 (quality phase)
- Type expression errors in `incidents.py` lines 51, 151, 307, 308, 445, 510, 565, 629 — will be fixed in Task 16 (quality phase)
