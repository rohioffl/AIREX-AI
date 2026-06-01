# Changelog

All notable changes to AIREX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.0.0] - 2026-04-03

### Added
- Autonomous incident resolution engine with 11-state lifecycle
- FastAPI backend with 23 API routers and 525 tests passing
- React 19 + Vite 7 frontend with 165 tests and 19 pages
- pgvector-powered RAG for incident knowledge retrieval
- LiteLLM routing with Langfuse observability
- Deterministic ACTION_REGISTRY (12 whitelisted remediation actions)
- Confidence-based auto-approval with senior approval gates
- ArgoCD GitOps deployment pipeline to ECS
- Multi-tenant architecture with RLS row-level security
- Prometheus + Grafana + Alertmanager observability stack
- Site24x7 and generic webhook alert ingestion
- AI-assisted remediation with prompt-injection safeguards
- Zero-trust cloud: no stored credentials, IAM roles only

### Live Environments
- Frontend/API: https://airex.ankercloud.com/
- Langfuse: https://airex-langfuse.ankercloud.com/
- LiteLLM: https://airex-litellm.ankercloud.com/
