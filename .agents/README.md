# .agents/

Codex CLI agent and skill definitions for AIREX.

## skills/

Skills are auto-discovered by Codex from `.agents/skills/`. Each symlink points
to the corresponding ECC (Everything Claude Code) skill directory.

Skills available:
- `api-design` — REST API design patterns
- `backend-patterns` — API, DB, caching architecture
- `coding-standards` — Universal coding standards
- `database-migrations` — Schema changes and migration patterns
- `deployment-patterns` — CI/CD, Docker, container patterns
- `e2e-testing` — Playwright E2E testing patterns
- `frontend-patterns` — React, state management, hooks
- `python-patterns` — Pythonic idioms, PEP 8, type hints
- `python-testing` — pytest, TDD, fixtures, mocks
- `security-review` — Auth, input validation, OWASP Top 10
- `tdd-workflow` — Test-driven development workflow
- `verification-loop` — Build, test, lint, typecheck, security
- `deep-research` — Multi-source research patterns
- `django-patterns` — Django REST API patterns (reference only, AIREX uses FastAPI)

## Source

Skills are symlinked from ECC plugin:
`~/.claude/plugins/cache/everything-claude-code/everything-claude-code/1.8.0/skills/`
