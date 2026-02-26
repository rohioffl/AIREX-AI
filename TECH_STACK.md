# AIREX Technology Stack & Architecture

> **Complete guide to all technologies, their connections, and design rationale**

**Last Updated:** 2026-02-24  
**Project:** AIREX (Autonomous Incident Resolution Engine Xecution)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Backend Stack](#backend-stack)
3. [Frontend Stack](#frontend-stack)
4. [Database Stack](#database-stack)
5. [Infrastructure Stack](#infrastructure-stack)
6. [AI/LLM Stack](#aillm-stack)
7. [Cloud Integration Stack](#cloud-integration-stack)
8. [Monitoring & Observability](#monitoring--observability)
9. [Data Flow & Connections](#data-flow--connections)
10. [Why These Choices?](#why-these-choices)

---

## System Overview

AIREX is a **multi-tenant, autonomous SRE platform** that automates incident investigation, AI-powered analysis, and safe remediation execution. The architecture is designed for:

- **High Reliability**: Async-first, distributed locks, idempotency
- **Security**: Zero-trust, RLS, no stored credentials
- **Scalability**: Horizontal scaling, task queues, pub/sub
- **Observability**: Structured logging, metrics, tracing

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  React 19 + Vite 7 + Tailwind CSS + SSE (EventSource)       │
│  Port: 5173 (dev) / 80 (prod via Nginx)                     │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/HTTPS
                     │ REST API + SSE
┌────────────────────▼────────────────────────────────────────┐
│                      BACKEND API                             │
│  FastAPI + Uvicorn (ASGI) + Pydantic                        │
│  Port: 8000                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Middleware: CORS, CSRF, Prometheus, Correlation ID  │  │
│  │ Routes: auth, webhooks, incidents, users, metrics    │  │
│  └──────────────────────────────────────────────────────┘  │
└──────┬──────────────────┬──────────────────┬───────────────┘
       │                  │                  │
       │ SQLAlchemy 2.0     │ Redis            │ HTTP
       │ (asyncpg)        │ (aioredis)        │ (httpx)
       │                  │                   │
┌──────▼──────────┐ ┌────▼──────────┐ ┌──────▼──────────────┐
│  PostgreSQL 15  │ │  Redis 7      │ │  LiteLLM Proxy      │
│  + pgvector     │ │  (ARQ Queue)  │ │  (AI Platform)      │
│  Port: 5432     │ │  Port: 6379   │ │  Port: 4000         │
│                 │ │               │ │                      │
│  • RLS Enabled  │ │  • Task Queue │ │  • Gemini 2.0 Flash │
│  • Composite PKs│ │  • Pub/Sub    │ │  • Embeddings        │
│  • Hash Chains  │ │  • Rate Limit │ │  • Circuit Breaker   │
│  • Vector DB    │ │  • DLQ        │ │  • Langfuse Tracing  │
└─────────────────┘ └───────────────┘ └──────────────────────┘
       │                  │
       │                  │
┌──────▼──────────────────▼──────────────────────────────────┐
│              ARQ BACKGROUND WORKER                          │
│  Async task processor (investigation, AI, execution)       │
│  • 4 task types: investigate, recommend, execute, verify   │
│  • Cron scheduler for retries                               │
│  • Dead Letter Queue (DLQ) for failures                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend Stack

### Core Framework

#### **FastAPI** (`fastapi>=0.115.0`)
- **What**: Modern, fast web framework for building APIs
- **Why**: 
  - Built-in async/await support (perfect for I/O-bound operations)
  - Automatic OpenAPI/Swagger documentation
  - Type hints with Pydantic validation
  - High performance (comparable to Node.js)
- **Usage**: Main API server, all route handlers, request/response validation
- **Connection**: Runs on Uvicorn ASGI server, connects to PostgreSQL via SQLAlchemy, Redis via aioredis

#### **Uvicorn** (`uvicorn[standard]>=0.34.0`)
- **What**: ASGI server implementation
- **Why**: 
  - High-performance async server (built on uvloop)
  - Supports WebSockets and SSE
  - Hot reload for development
- **Usage**: Runs FastAPI app, handles HTTP requests, manages async event loop
- **Connection**: Serves FastAPI app, receives HTTP requests from frontend/load balancer

#### **Pydantic** (`pydantic>=2.10.0`)
- **What**: Data validation using Python type annotations
- **Why**: 
  - Runtime type checking and validation
  - Automatic JSON schema generation
  - Fast validation (written in Rust)
- **Usage**: All API request/response models, settings validation, data serialization
- **Connection**: Used by FastAPI for request validation, SQLAlchemy for model definitions

### Database Layer

#### **SQLAlchemy 2.0** (`sqlalchemy[asyncio]>=2.0.37`)
- **What**: Python SQL toolkit and ORM
- **Why**: 
  - Async-first design (SQLAlchemy 2.0)
  - Type-safe queries
  - Multi-tenancy support via composite keys
  - RLS integration
- **Usage**: ORM models, async queries, transaction management
- **Connection**: Connects to PostgreSQL via asyncpg driver, manages connection pooling

#### **asyncpg** (`asyncpg>=0.30.0`)
- **What**: Fast PostgreSQL database driver
- **Why**: 
  - Pure async (no blocking I/O)
  - 3x faster than psycopg2
  - Direct PostgreSQL protocol (no libpq dependency)
- **Usage**: Low-level database connection, query execution
- **Connection**: Direct connection to PostgreSQL, used by SQLAlchemy

#### **Alembic** (`alembic>=1.14.0`)
- **What**: Database migration tool
- **Why**: 
  - Version control for database schema
  - Automatic migration generation
  - Supports complex migrations (RLS, triggers, functions)
- **Usage**: Schema migrations, database versioning
- **Connection**: Connects to PostgreSQL to apply migrations

#### **pgvector** (`pgvector>=0.3.5`)
- **What**: PostgreSQL extension for vector similarity search
- **Why**: 
  - Enables RAG (Retrieval-Augmented Generation)
  - Fast similarity search for embeddings
  - Native PostgreSQL integration
- **Usage**: Vector embeddings storage, similarity search for runbooks/incidents
- **Connection**: PostgreSQL extension, used by SQLAlchemy models

### Task Queue & Caching

#### **Redis** (`redis[hiredis]>=5.2.0`)
- **What**: In-memory data structure store
- **Why**: 
  - Fast pub/sub for SSE events
  - Task queue backend for ARQ
  - Rate limiting counters
  - Distributed locks
  - Circuit breaker state
- **Usage**: 
  - Pub/Sub: Real-time event broadcasting to frontend
  - Task Queue: Background job processing
  - Rate Limiting: Sliding window counters
  - Distributed Locks: Prevent race conditions
  - DLQ: Failed task storage
- **Connection**: Connected via aioredis, used by FastAPI (pub/sub), ARQ (task queue)

#### **ARQ** (`arq>=0.26.1`)
- **What**: Fast async task queue for Python
- **Why**: 
  - Built on asyncio (no threading overhead)
  - Redis-backed (reliable, scalable)
  - Built-in retry and DLQ support
  - Cron scheduling
- **Usage**: Background task processing (investigation, AI analysis, execution, verification)
- **Connection**: Connects to Redis for task queue, PostgreSQL for data access

### AI/LLM Integration

#### **LiteLLM** (`litellm>=1.60.0`)
- **What**: Unified interface for multiple LLM providers
- **Why**: 
  - Model-agnostic (switch providers easily)
  - Built-in fallback support
  - Circuit breaker integration
  - Cost tracking
- **Usage**: LLM client wrapper, handles provider switching, fallback logic
- **Connection**: HTTP requests to LiteLLM proxy (port 4000), which routes to Gemini/OpenAI

### Authentication & Security

#### **python-jose** (`python-jose[cryptography]>=3.3.0`)
- **What**: JWT implementation for Python
- **Why**: 
  - Industry-standard token format
  - Stateless authentication
  - Supports HS256 (symmetric) and RS256 (asymmetric)
- **Usage**: JWT token creation, validation, decoding
- **Connection**: Used by FastAPI auth routes, validates tokens on every request

#### **passlib** (`passlib[bcrypt]>=1.7.4`)
- **What**: Password hashing library
- **Why**: 
  - Secure bcrypt hashing
  - Automatic salt generation
  - Future-proof (supports multiple algorithms)
- **Usage**: Password hashing for user accounts
- **Connection**: Used in user registration/login flows

### Cloud Integration

#### **boto3** (`boto3>=1.34.0`)
- **What**: AWS SDK for Python
- **Why**: 
  - Official AWS SDK
  - Supports all AWS services
  - Automatic credential chain (IAM roles, profiles, keys)
- **Usage**: 
  - AWS SSM: Run commands on EC2 instances
  - EC2 Instance Connect: Ephemeral SSH keys
  - CloudWatch Logs: Log querying
  - EC2 API: Instance discovery
- **Connection**: HTTP requests to AWS APIs, uses IAM roles/credentials

#### **google-cloud-logging** (`google-cloud-logging>=3.10.0`)
- **What**: GCP Cloud Logging client
- **Why**: 
  - Official GCP SDK
  - Fast log queries
  - Structured log support
- **Usage**: Query GCP Cloud Logging for incident investigation
- **Connection**: HTTP requests to GCP APIs, uses service account credentials

#### **google-cloud-compute** (`google-cloud-compute>=1.15.0`)
- **What**: GCP Compute Engine client
- **Why**: 
  - Official GCP SDK
  - Instance management
  - MIG (Managed Instance Group) scaling
- **Usage**: GCP instance discovery, MIG scaling operations
- **Connection**: HTTP requests to GCP APIs

#### **asyncssh** (`asyncssh>=2.14.0`)
- **What**: Async SSH client/server library
- **Why**: 
  - Pure async (no blocking)
  - Supports GCP OS Login
  - Key-based and certificate authentication
- **Usage**: SSH connections to GCP instances (fallback when OS Login unavailable)
- **Connection**: Direct SSH connections to instances

### Observability

#### **structlog** (`structlog>=24.4.0`)
- **What**: Structured logging library
- **Why**: 
  - JSON-formatted logs (machine-readable)
  - Context binding (correlation IDs)
  - Performance logging
- **Usage**: All application logging, structured with correlation IDs
- **Connection**: Logs to stdout, can be forwarded to log aggregation systems

#### **prometheus-client** (`prometheus-client>=0.21.0`)
- **What**: Prometheus metrics client
- **Why**: 
  - Industry-standard metrics format
  - Rich metric types (counter, gauge, histogram)
  - Easy integration with Prometheus
- **Usage**: Exposes `/metrics` endpoint, tracks HTTP latency, incident counts, AI failures
- **Connection**: Exposes metrics endpoint, scraped by Prometheus

### HTTP Client

#### **httpx** (`httpx>=0.28.0`)
- **What**: Async HTTP client
- **Why**: 
  - Pure async (no blocking)
  - HTTP/2 support
  - Connection pooling
  - Better than requests for async code
- **Usage**: HTTP requests to LiteLLM proxy, external APIs, webhooks
- **Connection**: HTTP requests to various services

### Server-Sent Events

#### **sse-starlette** (`sse-starlette>=2.2.0`)
- **What**: SSE support for Starlette/FastAPI
- **Why**: 
  - Real-time event streaming
  - Simpler than WebSockets for one-way communication
  - Automatic reconnection support
- **Usage**: Real-time incident updates to frontend
- **Connection**: FastAPI route handler, streams events from Redis pub/sub

---

## Frontend Stack

### Core Framework

#### **React 19** (`react>=19.2.0`)
- **What**: UI library for building user interfaces
- **Why**: 
  - Component-based architecture
  - Virtual DOM for performance
  - Large ecosystem
  - Server Components support (React 19)
- **Usage**: All UI components, pages, hooks
- **Connection**: Renders to DOM, makes HTTP requests to backend API

#### **Vite 7** (`vite>=7.3.1`)
- **What**: Next-generation frontend build tool
- **Why**: 
  - Extremely fast HMR (Hot Module Replacement)
  - Native ES modules
  - Optimized production builds
  - Better than Webpack for modern projects
- **Usage**: Development server, production build tool
- **Connection**: Serves frontend assets, proxies API requests in dev mode

### Routing

#### **react-router-dom** (`react-router-dom>=7.13.0`)
- **What**: Declarative routing for React
- **Why**: 
  - Industry standard
  - Client-side routing
  - Route guards support
  - Code splitting
- **Usage**: Page routing, route protection, navigation
- **Connection**: Manages URL routing, integrates with React components

### HTTP Client

#### **axios** (`axios>=1.13.5`)
- **What**: Promise-based HTTP client
- **Why**: 
  - Interceptors for auth tokens
  - Request/response transformation
  - Automatic JSON parsing
  - Better error handling than fetch
- **Usage**: All API calls to backend
- **Connection**: HTTP requests to FastAPI backend (port 8000)

### Styling

#### **Tailwind CSS 4** (`tailwindcss>=4.1.18`)
- **What**: Utility-first CSS framework
- **Why**: 
  - Rapid UI development
  - Small bundle size (JIT compilation)
  - Dark mode support
  - Customizable design system
- **Usage**: All component styling, responsive design
- **Connection**: Processes CSS, generates utility classes

### Icons

#### **lucide-react** (`lucide-react>=0.564.0`)
- **What**: Icon library
- **Why**: 
  - Consistent icon set
  - Tree-shakeable (only imports used icons)
  - React components
- **Usage**: All icons throughout the UI
- **Connection**: React components, renders SVG icons

### Charts

#### **recharts** (`recharts>=3.7.0`)
- **What**: Composable charting library
- **Why**: 
  - Built for React
  - Responsive charts
  - Good documentation
- **Usage**: Dashboard metrics, system graphs
- **Connection**: Renders charts from API data

### Fonts

#### **@fontsource/inter** & **@fontsource/jetbrains-mono**
- **What**: Self-hosted font packages
- **Why**: 
  - No external font requests
  - Better privacy
  - Faster loading
- **Usage**: UI fonts (Inter for UI, JetBrains Mono for code)
- **Connection**: CSS font imports

### Testing

#### **Vitest** (`vitest>=4.0.18`)
- **What**: Fast unit test framework
- **Why**: 
  - Vite-native (fast)
  - Jest-compatible API
  - ESM support
- **Usage**: Unit tests for components, hooks, utilities
- **Connection**: Runs tests, uses jsdom for DOM simulation

#### **@testing-library/react** (`@testing-library/react>=16.3.2`)
- **What**: React testing utilities
- **Why**: 
  - User-centric testing
  - Accessible queries
  - Best practices
- **Usage**: Component testing
- **Connection**: Renders React components in test environment

---

## Database Stack

### PostgreSQL 15+ with pgvector

#### **PostgreSQL 15**
- **What**: Advanced open-source relational database
- **Why**: 
  - Row Level Security (RLS) for multi-tenancy
  - Composite primary keys
  - JSONB for flexible schemas
  - Excellent performance
  - ACID compliance
- **Usage**: Primary data store for all application data
- **Connection**: 
  - Backend connects via `asyncpg` driver
  - Connection string: `postgresql+asyncpg://user:pass@host:5432/db`
  - Connection pool: 20 connections (configurable)

#### **Row Level Security (RLS)**
- **What**: Database-level access control
- **Why**: 
  - Enforces tenant isolation at database level
  - Prevents data leaks even if application code has bugs
  - Zero-trust security model
- **Usage**: Every table has RLS policies filtering by `tenant_id`
- **Connection**: Policies set via `app.tenant_id` session variable

#### **pgvector Extension**
- **What**: Vector similarity search extension
- **Why**: 
  - Enables RAG (Retrieval-Augmented Generation)
  - Fast similarity search for embeddings
  - Native PostgreSQL integration
- **Usage**: 
  - `runbook_chunks` table: Stores runbook embeddings
  - `incident_embeddings` table: Stores incident summaries
  - Similarity search for context retrieval
- **Connection**: PostgreSQL extension, used by SQLAlchemy models

### Database Schema

#### **Composite Primary Keys**
- **Pattern**: `(tenant_id, id)`
- **Why**: 
  - Enforces multi-tenancy at database level
  - Prevents cross-tenant data access
  - Better query performance with proper indexes
- **Usage**: All tables except reference data

#### **Hash Chains**
- **What**: Immutable audit trail with cryptographic hashing
- **Why**: 
  - Tamper-evident logs
  - Each state transition links to previous hash
  - Detects any modification
- **Usage**: `state_transitions` table tracks all incident state changes
- **Connection**: SHA-256 hashing, stored in PostgreSQL

---

## Infrastructure Stack

### Containerization

#### **Docker**
- **What**: Containerization platform
- **Why**: 
  - Consistent environments
  - Easy deployment
  - Service isolation
- **Usage**: All services run in containers
- **Connection**: Docker Compose orchestrates all services

#### **Docker Compose**
- **What**: Multi-container Docker application
- **Why**: 
  - Single command to start entire stack
  - Service dependencies
  - Volume management
  - Network isolation
- **Usage**: Orchestrates 8 services (db, redis, backend, worker, frontend, ai-platform, prometheus, grafana)
- **Connection**: Defines service network, volumes, dependencies

### Web Server

#### **Nginx** (Production)
- **What**: High-performance web server
- **Why**: 
  - Reverse proxy
  - Static file serving
  - SSL termination
  - Load balancing
- **Usage**: Serves frontend in production, proxies API requests
- **Connection**: Receives HTTP requests, serves frontend, proxies to backend

### Monitoring

#### **Prometheus**
- **What**: Time-series database and monitoring system
- **Why**: 
  - Industry-standard metrics format
  - Powerful query language (PromQL)
  - Alerting support
- **Usage**: Scrapes metrics from backend `/metrics` endpoint
- **Connection**: HTTP requests to backend, stores metrics in time-series DB

#### **Grafana**
- **What**: Visualization and analytics platform
- **Why**: 
  - Beautiful dashboards
  - Multiple data sources
  - Alerting
- **Usage**: Visualizes Prometheus metrics
- **Connection**: Queries Prometheus, displays dashboards

---

## AI/LLM Stack

### LiteLLM Proxy

#### **LiteLLM** (`ghcr.io/berriai/litellm:main-v1.60.0`)
- **What**: Unified proxy for multiple LLM providers
- **Why**: 
  - Model-agnostic interface
  - Automatic fallback
  - Cost tracking
  - Rate limiting
  - Langfuse integration (tracing)
- **Usage**: 
  - Routes LLM requests to appropriate provider
  - Handles embeddings
  - Circuit breaker logic
- **Connection**: 
  - Backend connects via HTTP (port 4000)
  - Routes to Gemini 2.0 Flash (primary) or Flash Lite (fallback)
  - Integrates with Langfuse for observability

### LLM Models

#### **Gemini 2.0 Flash** (Primary)
- **What**: Google's fast, efficient LLM
- **Why**: 
  - Fast response times
  - Good quality
  - Cost-effective
  - Multimodal support
- **Usage**: Primary model for incident analysis, recommendations
- **Connection**: Via LiteLLM proxy, Vertex AI API

#### **Gemini 2.0 Flash Lite** (Fallback)
- **What**: Lighter version of Gemini Flash
- **Why**: 
  - Even faster
  - Lower cost
  - Fallback when primary fails
- **Usage**: Fallback model when primary times out or fails
- **Connection**: Via LiteLLM proxy

#### **text-embedding-3-large** (Embeddings)
- **What**: OpenAI embedding model
- **Why**: 
  - High-quality embeddings
  - 3072 dimensions
  - Good for similarity search
- **Usage**: Generates embeddings for runbooks and incidents (RAG)
- **Connection**: Via LiteLLM proxy, OpenAI API

### Observability

#### **Langfuse**
- **What**: LLM observability platform
- **Why**: 
  - Traces all LLM calls
  - Cost tracking
  - Performance monitoring
  - Debugging
- **Usage**: Tracks all LLM requests through LiteLLM
- **Connection**: Integrated with LiteLLM proxy

---

## Cloud Integration Stack

### AWS Integration

#### **AWS Systems Manager (SSM)**
- **What**: Secure remote management service
- **Why**: 
  - No SSH keys required
  - IAM-based access control
  - Audit logging
  - Secure by default
- **Usage**: Primary method for running diagnostics on AWS EC2 instances
- **Connection**: 
  - boto3 → AWS SSM API
  - Uses IAM roles or credentials
  - Runs commands via `AWS-RunShellScript` document

#### **EC2 Instance Connect**
- **What**: Browser-based SSH to EC2 instances
- **Why**: 
  - Ephemeral SSH keys (60s validity)
  - No stored keys
  - IAM-based access
- **Usage**: Fallback when SSM unavailable
- **Connection**: 
  - boto3 → EC2 Instance Connect API
  - Pushes temporary SSH key
  - Then uses asyncssh for connection

#### **CloudWatch Logs**
- **What**: AWS log management service
- **Why**: 
  - Centralized logging
  - Fast queries
  - Cost-effective
- **Usage**: Query logs during incident investigation
- **Connection**: boto3 → CloudWatch Logs API

### GCP Integration

#### **GCP OS Login**
- **What**: SSH key management via IAM
- **Why**: 
  - No stored SSH keys
  - IAM-based access
  - Automatic key rotation
- **Usage**: Primary method for SSH to GCP instances
- **Connection**: 
  - google-cloud-compute → OS Login API
  - asyncssh uses OS Login credentials

#### **Cloud Logging**
- **What**: GCP log management service
- **Why**: 
  - Fast queries
  - Structured logs
  - Integration with GCP services
- **Usage**: Query logs during incident investigation
- **Connection**: google-cloud-logging → Cloud Logging API

#### **Managed Instance Groups (MIG)**
- **What**: GCP auto-scaling groups
- **Why**: 
  - Automatic scaling
  - Health checks
  - Load balancing
- **Usage**: Scale instances up/down for remediation
- **Connection**: google-cloud-compute → MIG API

---

## Monitoring & Observability

### Metrics

#### **Prometheus Metrics**
- **What**: Time-series metrics
- **Metrics Tracked**:
  - `airex_incident_created_total`: Incident creation counter
  - `airex_state_transition_total`: State transition counter
  - `airex_incident_latency_seconds`: Time to resolution histogram
  - `airex_ai_failure_total`: AI/LLM failure counter
  - `airex_execution_total`: Action execution counter
  - `airex_execution_duration_seconds`: Execution duration histogram
  - `airex_circuit_breaker_state`: Circuit breaker state gauge
  - `airex_dlq_size`: Dead letter queue size gauge
  - `airex_http_request_duration_seconds`: HTTP latency histogram
- **Connection**: Backend exposes `/metrics` endpoint, Prometheus scrapes it

### Logging

#### **Structured Logging (structlog)**
- **What**: JSON-formatted logs
- **Why**: 
  - Machine-readable
  - Easy to parse
  - Searchable
  - Correlation IDs for tracing
- **Usage**: All application logs
- **Connection**: Logs to stdout, can be forwarded to log aggregation

### Tracing

#### **Langfuse Tracing**
- **What**: LLM call tracing
- **Why**: 
  - Debug LLM issues
  - Track costs
  - Monitor performance
- **Usage**: All LLM calls through LiteLLM
- **Connection**: LiteLLM proxy sends traces to Langfuse

---

## Data Flow & Connections

### Request Flow

```
1. User Action (Frontend)
   ↓
2. Axios HTTP Request
   ↓
3. FastAPI Route Handler
   ↓
4. Middleware Stack:
   - CORS
   - CSRF
   - Correlation ID
   - Prometheus Metrics
   ↓
5. Dependency Injection:
   - JWT Auth
   - Tenant ID Extraction
   - Database Session (with RLS)
   - Redis Connection
   ↓
6. Business Logic
   ↓
7. Database Query (SQLAlchemy → asyncpg → PostgreSQL)
   OR
   Redis Operation (aioredis → Redis)
   OR
   Background Task (ARQ → Redis Queue)
   ↓
8. Response (JSON)
   ↓
9. Frontend Update
```

### Real-Time Event Flow (SSE)

```
1. Frontend opens SSE connection
   ↓
2. FastAPI SSE route handler
   ↓
3. Redis Pub/Sub subscription
   ↓
4. Backend publishes event (via Redis)
   ↓
5. Redis broadcasts to all subscribers
   ↓
6. FastAPI streams event to frontend
   ↓
7. Frontend EventSource receives event
   ↓
8. React state update
```

### Background Task Flow

```
1. API endpoint enqueues task
   ↓
2. ARQ adds task to Redis queue
   ↓
3. ARQ Worker picks up task
   ↓
4. Task execution:
   - Investigation: Cloud APIs (AWS/GCP)
   - AI Analysis: LiteLLM → Gemini
   - Execution: Cloud APIs (AWS/GCP)
   - Verification: Cloud APIs (AWS/GCP)
   ↓
5. Success: Update database, publish SSE event
   OR
   Failure: Retry or move to DLQ
```

### Database Connection Flow

```
1. FastAPI request
   ↓
2. Dependency: TenantSession
   ↓
3. SQLAlchemy creates async session
   ↓
4. Sets PostgreSQL session variable: app.tenant_id
   ↓
5. RLS policies filter by tenant_id
   ↓
6. Query executes (asyncpg → PostgreSQL)
   ↓
7. Results filtered by RLS
   ↓
8. Session closes, resets app.tenant_id
```

### Multi-Tenancy Flow

```
1. User logs in
   ↓
2. JWT token contains tenant_id
   ↓
3. FastAPI extracts tenant_id from token
   ↓
4. Sets app.tenant_id in PostgreSQL session
   ↓
5. All queries automatically filtered by RLS
   ↓
6. Redis keys prefixed with tenant_id
   ↓
7. SSE events scoped to tenant_id
```

---

## Why These Choices?

### Backend: FastAPI over Django/Flask

**FastAPI** was chosen because:
- **Async-first**: Critical for I/O-bound operations (database, Redis, HTTP)
- **Type safety**: Pydantic validation catches errors early
- **Performance**: Comparable to Node.js, faster than Django
- **Modern**: Built for Python 3.8+, uses modern async patterns
- **Documentation**: Auto-generated OpenAPI docs

**Not Django** because:
- Django is synchronous by default (requires async views)
- Heavier framework (more overhead)
- ORM is less flexible for multi-tenancy

**Not Flask** because:
- No built-in async support
- Less type safety
- More boilerplate for validation

### Database: PostgreSQL over MySQL/MongoDB

**PostgreSQL** was chosen because:
- **RLS**: Critical for multi-tenant security
- **JSONB**: Flexible schemas for metadata
- **Composite keys**: Natural multi-tenancy pattern
- **Extensions**: pgvector for RAG
- **ACID**: Strong consistency guarantees

**Not MySQL** because:
- No RLS support
- Weaker JSON support
- Less extensible

**Not MongoDB** because:
- No RLS equivalent
- Weaker consistency guarantees
- Less mature ecosystem for Python

### Task Queue: ARQ over Celery

**ARQ** was chosen because:
- **Pure async**: No threading overhead
- **Simple**: Less configuration than Celery
- **Redis-native**: No separate broker needed
- **Fast**: Optimized for async workloads

**Not Celery** because:
- Requires separate broker (RabbitMQ/Redis)
- More complex configuration
- Threading overhead
- Overkill for our use case

### Frontend: React over Vue/Angular

**React** was chosen because:
- **Ecosystem**: Largest component library
- **SSE support**: Easy EventSource integration
- **Performance**: Virtual DOM, React 19 improvements
- **Developer experience**: Great tooling

**Not Vue** because:
- Smaller ecosystem
- Less common in enterprise

**Not Angular** because:
- Heavier framework
- More opinionated
- Overkill for our use case

### Build Tool: Vite over Webpack

**Vite** was chosen because:
- **Speed**: 10-100x faster HMR
- **Modern**: Native ESM support
- **Simple**: Less configuration
- **Future-proof**: Industry standard

**Not Webpack** because:
- Slower builds
- More complex configuration
- Legacy tooling

### Styling: Tailwind over CSS-in-JS

**Tailwind** was chosen because:
- **Speed**: Rapid development
- **Bundle size**: JIT compilation (only used classes)
- **Consistency**: Design system built-in
- **Dark mode**: Native support

**Not CSS-in-JS** because:
- Runtime overhead
- Larger bundle size
- Less performant

### AI: LiteLLM over Direct API Calls

**LiteLLM** was chosen because:
- **Flexibility**: Switch providers easily
- **Fallback**: Automatic failover
- **Observability**: Langfuse integration
- **Cost tracking**: Built-in

**Not direct API calls** because:
- Vendor lock-in
- No fallback mechanism
- More code to maintain

### Cloud: IAM-based over SSH Keys

**IAM-based access** was chosen because:
- **Security**: No stored credentials
- **Auditability**: All access logged
- **Scalability**: No key management
- **Zero-trust**: Principle of least privilege

**Not SSH keys** because:
- Security risk (stored keys)
- Key rotation complexity
- No audit trail

---

## Connection Details

### Ports & Endpoints

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Frontend (Dev) | 5173 | HTTP | Vite dev server |
| Frontend (Prod) | 80 | HTTP/HTTPS | Nginx |
| Backend API | 8000 | HTTP | FastAPI |
| PostgreSQL | 5432 | TCP | Database |
| Redis | 6379 | TCP | Cache/Queue |
| LiteLLM Proxy | 4000 | HTTP | AI Platform |
| Prometheus | 9090 | HTTP | Metrics |
| Grafana | 3000 | HTTP | Dashboards |

### Connection Strings

**PostgreSQL:**
```
postgresql+asyncpg://postgres:postgres@db:5432/airex
```

**Redis:**
```
redis://redis:6379/0
```

**LiteLLM:**
```
http://ai-platform:4000/v1
```

### Environment Variables

All connections configured via environment variables:
- `DATABASE_URL`: PostgreSQL connection
- `REDIS_URL`: Redis connection
- `LLM_BASE_URL`: LiteLLM proxy URL
- `LLM_API_KEY`: LiteLLM authentication
- `SECRET_KEY`: JWT signing key
- `CORS_ORIGINS`: Allowed frontend origins

---

## Summary

AIREX uses a **modern, async-first stack** designed for:

1. **Performance**: Async I/O, connection pooling, efficient queries
2. **Security**: RLS, zero-trust, no stored credentials
3. **Scalability**: Horizontal scaling, task queues, pub/sub
4. **Reliability**: Distributed locks, idempotency, retries, DLQ
5. **Observability**: Structured logs, metrics, tracing

The architecture follows **microservices principles** with clear separation:
- **Frontend**: React SPA with real-time updates
- **Backend API**: FastAPI with async operations
- **Background Workers**: ARQ for async tasks
- **Database**: PostgreSQL with RLS
- **Cache/Queue**: Redis for pub/sub and tasks
- **AI Platform**: LiteLLM proxy for LLM access
- **Monitoring**: Prometheus + Grafana

All components are **containerized** and **orchestrated** via Docker Compose for easy deployment and scaling.

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-24  
**Maintained By:** AIREX Development Team
