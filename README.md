# GrantFlow — Backend API

> Multi-tenant grant management platform with AI-assisted scoring, role-based access control, and automated workflows.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135.3-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-multi--schema-336791?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-cache%20%2B%20queue-DC382D?logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.6.3-37814A)

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Grant Lifecycle](#grant-lifecycle)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

---

## Overview

GrantFlow enables organizations to publish grants, manage the full application lifecycle, and process payments — with AI and human commissioner scoring combined into a single weighted final score.

**User Roles:**

| Role | Responsibilities |
|------|-----------------|
| **Super Admin** | Approves/rejects organizations, manages users and system permissions |
| **Org Admin** | Creates grants, manages team, reviews applications, processes payments |
| **Commissioner** | Scores applications per-criterion (0–100); invited by Org Admin |
| **Applicant** | Browses published grants, submits applications, tracks results and payments |

**Key Features:**

- Multi-tenant PostgreSQL with schema-per-organization data isolation
- Database-driven RBAC with per-resource/action permissions
- AI scoring via OpenAI GPT-4o-mini with Groq llama-3.1-8b-instant as fallback
- Async task queue (Celery + Redis) for AI scoring and email notifications
- Redis caching with TTL-based invalidation for public grant listings
- JWT authentication with refresh tokens, token blacklisting, and rate limiting
- Round-robin application assignment to commissioners
- Full audit logging for all system actions

---

## Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| API Framework | FastAPI | 0.135.3 |
| ORM | SQLAlchemy | 2.0.49 |
| Migrations | Alembic | 1.18.4 |
| Database | PostgreSQL | 14+ |
| Cache / Broker | Redis | 7+ |
| Task Queue | Celery | 5.6.3 |
| Validation | Pydantic v2 | 2.12.5 |
| Auth | PyJWT + bcrypt | 2.12.1 / 5.0.0 |
| AI — Primary | OpenAI GPT-4o-mini | 2.38.0 |
| AI — Fallback | Groq llama-3.1-8b-instant | — |
| Email | Gmail SMTP (STARTTLS port 587) | — |
| ASGI Server | Uvicorn | 0.44.0 |

---

## System Architecture

```mermaid
flowchart TB

    subgraph CLIENT["CLIENT LAYER — React 19"]
        direction LR
        C1["GrantsPage · GrantDetailPage\nMyApplicationsPage · ApplicationDetailPage\nApplyPage · ProfilePage"]:::frontend
        C2["OrgDashboard · GrantsManagePage · GrantFormPage\nApplicationsReviewPage · PaymentsPage · TeamPage"]:::frontend
        C3["CommissionerDashboard\nCommissionerApplicationsPage"]:::frontend
        C4["SuperAdminDashboard · PendingOrgsPage\nUsersListPage · AuditLogsPage\nManagePermissionsPage · AddSuperAdminPage"]:::frontend
        C5["LoginPage · RegisterPage · OrgRegisterPage\nAcceptInvitePage · ForgotPasswordPage\nResetPasswordPage · VerifyEmailPage"]:::frontend
        C6["AuthContext · useAuth() · ProtectedRoute"]:::context
        C7["axios.js · Bearer token · Auto refresh · Interceptors"]:::context
    end

    subgraph API["API LAYER — FastAPI 0.135"]
        direction LR
        subgraph MW["Middleware Stack"]
            MW1["LoggingMiddleware\nmethod + path + ms"]:::middleware
            MW2["AuthMiddleware\nJWT decode · Blacklist check"]:::middleware
            MW3["TenantMiddleware\nSET search_path · Slug validation"]:::middleware
            MW1 --> MW2 --> MW3
        end
        subgraph ROUTES["Routers"]
            R1["/auth\nregister · login · logout · refresh · reset-password"]:::router
            R2["/grants · /applications · /criteria · /payments"]:::router
            R3["/team · /profile · /users · /tenants"]:::router
            R4["/chatbot · /audit-logs · /permissions"]:::router
        end
        subgraph DEP["Dependencies"]
            D1["get_current_user()\nrequire_permission()\nget_tenant_db()"]:::dep
        end
        subgraph SWAGGER["Swagger UI"]
            SW["/docs · /redoc · /openapi.json"]:::doc
        end
    end

    subgraph SERVICE["SERVICE LAYER — Business Logic"]
        direction LR
        S1["AuthService\nhash · verify · token · register · login"]:::service
        S2["GrantService\nCRUD · publish · finalize · cache"]:::service
        S3["ApplicationService\nsubmit · review · assign · status"]:::service
        S4["AIScoreService\nprompt build · final_score calc"]:::service
        S5["PaymentService\ncreate · mark_paid"]:::service
        S6["ChatService\nprofile context · grant suggestions"]:::service
        S7["TeamService · AuditService\nTenantService · UserService"]:::service
    end

    subgraph ASYNC["ASYNC LAYER — Celery + Redis"]
        direction LR
        BG1["score_application_task\nOpenAI / Groq call · retry x3"]:::celery
        BG2["send_verification_email\nsend_invitation_email\nsend_reset_password_email"]:::celery
        BG3["send_org_approval_email\nsend_org_rejection_email\nsend_application_result_email"]:::celery
    end

    subgraph CACHE["CACHE LAYER — Redis DB1"]
        direction LR
        RC1["grants:public:* · TTL 60s\ncache_get / cache_set"]:::cache
        RC2["bl:{token_hash}\nToken Blacklist"]:::cache
        RC3["rl:login:{ip} · rl:forgot:{ip}\nRate Limiting"]:::cache
    end

    subgraph DB["DATABASE LAYER — PostgreSQL"]
        direction LR
        subgraph PUB["Schema: public"]
            DB1["users · tenants · roles · permissions"]:::db
            DB2["user_roles · role_permissions · refresh_tokens"]:::db
            DB3["audit_logs · password_reset_tokens · email_verification_tokens"]:::db
        end
        subgraph TEN["Schema: tenant_{slug} × N"]
            DB4["grants · criteria · grant_tags · application_questions"]:::db
            DB5["applications · application_answers · attachments · cvs"]:::db
            DB6["ai_scores · commissioner_scores · payments · invitations"]:::db
        end
    end

    subgraph EXT["EXTERNAL SERVICES"]
        E1["OpenAI API\ngpt-4o-mini"]:::ext
        E2["Groq API\nllama-3.1-8b-instant (fallback)"]:::ext
        E3["Gmail SMTP\nSTARTTLS port 587"]:::ext
    end

    CLIENT -->|"HTTP/HTTPS REST\nAuthorization: Bearer"| API
    API --> MW
    MW --> ROUTES
    ROUTES --> DEP
    ROUTES --> SERVICE
    SERVICE --> ASYNC
    SERVICE --> CACHE
    SERVICE --> DB
    ASYNC --> EXT
    ASYNC --> DB

    classDef frontend   fill:#1e3a5f,stroke:#60a5fa,color:#fff
    classDef context    fill:#1a2744,stroke:#3b82f6,color:#93c5fd
    classDef middleware fill:#3b1f5e,stroke:#a855f7,color:#fff
    classDef router     fill:#1F2937,stroke:#4B5563,color:#fff
    classDef dep        fill:#1c2432,stroke:#6B7280,color:#9CA3AF
    classDef doc        fill:#1c2e2e,stroke:#0d9488,color:#5eead4
    classDef service    fill:#1a3040,stroke:#0ea5e9,color:#fff
    classDef celery     fill:#2d1f0e,stroke:#f59e0b,color:#fbbf24
    classDef cache      fill:#1f1a10,stroke:#ca8a04,color:#fde68a
    classDef db         fill:#14532d,stroke:#22c55e,color:#fff
    classDef ext        fill:#2d1515,stroke:#ef4444,color:#fca5a5
```

---

## Grant Lifecycle

```mermaid
flowchart TD
    subgraph ORG["ORG_ADMIN — Regjistrim & Aprovim"]
        A["ORG_ADMIN Regjistrohet"]:::blue
        B["Llogari krijuar\nis_active = False"]:::dark
        C["Email Konfirmimi"]:::orange
        D{"E klikon\nlinkun?"}:::decision
        E["Llogari e paaktivizuar"]:::muted
        F["Llogaria e aktivizuar\nis_active = True\nemail_verified = True\ntenant.status = PENDING"]:::dark
        G{"Super Admin\naprovo?"}:::decision
        H["Email Refuzimi"]:::red
        I["tenant.status = ACTIVE\nSchema e krijuar"]:::dark
        J["Email Aprovimi"]:::orange
        K["ORG_ADMIN kyçet"]:::green

        A --> B --> C --> D
        D -->|"Jo"| E
        D -->|"Po"| F --> G
        G -->|"Refuzo"| H
        G -->|"Aprovo"| I --> J --> K
    end

    subgraph APP["APPLICANT — Regjistrim"]
        AP_A["APPLICANT Regjistrohet"]:::blue
        AP_B["Llogari krijuar\nis_active = False"]:::dark
        AP_C["Email Konfirmimi"]:::orange
        AP_D{"E klikon\nlinkun?"}:::decision
        AP_E["Llogari e paaktivizuar"]:::muted
        AP_F["APPLICANT kyçet"]:::green

        AP_A --> AP_B --> AP_C --> AP_D
        AP_D -->|"Jo"| AP_E
        AP_D -->|"Po"| AP_F
    end

    subgraph FLOW["Grant Lifecycle"]
        L["Email Ftese COMMISSIONER\nlink aktivizimi"]:::orange
        L_D{"E hap\nlinkun?"}:::decision
        L_NO["Ftesa e paperdorur"]:::muted
        M["COMMISSIONER kyçet"]:::green

        N["ORG_ADMIN krijon Grant\nDRAFT → PUBLISHED\nRedis cache invalidohet"]:::dark

        P["APPLICANT aplikon\nper grant"]:::blue
        P_CHECK{"Profili\ni plotë?"}:::decision
        P_FAIL["Aplikimi refuzohet\nPROFILE_INCOMPLETE"]:::red
        P_SUB["SUBMITTED\nRound-Robin → COMMISSIONER"]:::dark

        Q["UNDER_REVIEW"]:::dark
        S["AI Score\nGroq / OpenAI"]:::orange
        T["COMMISSIONER jep pike\n0-100 per kriter"]:::dark
        U["final_score =\nai x weight + comm x (1 - weight)"]:::dark

        DEADLINE{"Deadline\nkaloi?"}:::decision
        CLOSE["Grant CLOSED\nautomatikisht"]:::dark
        ALL_SCORED{"Krejt\nvleresuar?"}:::decision
        FIN["Grant FINALIZED"]:::dark

        W["APPROVED"]:::green
        X["REJECTED"]:::red
        Y["Email rezultatit\naplikantit"]:::orange

        L --> L_D
        L_D -->|"Jo"| L_NO
        L_D -->|"Po"| M
        M --> Q
        N --> P
        P --> P_CHECK
        P_CHECK -->|"Jo"| P_FAIL
        P_CHECK -->|"Po"| P_SUB --> Q
        Q --> S & T
        S & T --> U --> DEADLINE
        DEADLINE -->|"Jo — pret"| Q
        DEADLINE -->|"Po"| CLOSE --> ALL_SCORED
        ALL_SCORED -->|"Jo — pret"| Q
        ALL_SCORED -->|"Po"| FIN --> W & X --> Y
    end

    subgraph PAY["Sistemi i Pagesave"]
        PAY_A["Payment PENDING\nkrijuar automatikisht\nper cdo APPROVED"]:::dark
        PAY_B["ORG_ADMIN shikon\nlisten e pagesave\n+ IBAN aplikantit"]:::blue
        PAY_C["ORG_ADMIN shenon\nPAID + reference bankare"]:::dark
        PAY_D["Payment PAID"]:::green
        PAY_E["APPLICANT shikon\nstatusin e pageses"]:::blue

        PAY_A --> PAY_B --> PAY_C --> PAY_D
        PAY_A --> PAY_E
    end

    K -->|"Fton COMMISSIONER"| L
    K --> N
    AP_F --> P
    W --> PAY_A

    classDef blue     fill:#1e3a5f,stroke:#60a5fa,color:#fff
    classDef dark     fill:#1F2937,stroke:#4B5563,color:#fff
    classDef orange   fill:#78350f,stroke:#f59e0b,color:#fff
    classDef green    fill:#14532d,stroke:#22c55e,color:#fff
    classDef red      fill:#7f1d1d,stroke:#ef4444,color:#fff
    classDef muted    fill:#111827,stroke:#6B7280,color:#9CA3AF
    classDef decision fill:#1c1c2e,stroke:#818cf8,color:#fff
```

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Node.js 18+ *(for running the frontend)*

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/GrantFlow-Backend.git
cd GrantFlow-Backend
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Linux / macOS
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Open .env and fill in the required values (see table below)
```

### 5. Create the PostgreSQL database

```bash
createdb grantflow
```

### 6. Run migrations

```bash
alembic upgrade head
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ENV` | Environment mode (`development` / `production`) |
| `DATABASE_URL` | PostgreSQL connection string — `postgresql://user:pass@localhost/grantflow` |
| `SECRET_KEY` | JWT signing key — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `REDIS_URL` | Redis URL — `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key (primary AI scoring) |
| `GROQ_API_KEY` | Groq API key (fallback AI scoring) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL in minutes (default: `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL in days (default: `7`) |
| `SUPER_ADMIN_EMAIL` | Email for the initial super admin account |
| `SUPER_ADMIN_PASSWORD` | Password for the initial super admin account |
| `MAIL_USERNAME` | Gmail SMTP username |
| `MAIL_PASSWORD` | Gmail app password |
| `MAIL_FROM` | From address used in outgoing emails |
| `FRONTEND_URL` | Frontend origin for CORS (e.g. `http://localhost:5173`) |

---

## Running the Project

### API Server

```bash
uvicorn app.main:app --reload
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | REST API |
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc |
| `http://localhost:8000/openapi.json` | OpenAPI schema |

### Celery Worker

Open a second terminal and run:

```bash
celery -A app.core.celery_app worker -l info
```

The worker processes the following task queues:

| Task | Trigger |
|------|---------|
| `score_application_ai` | Application submitted → AI scores via OpenAI / Groq (retry ×3) |
| `send_verification_email` | New user registration |
| `send_invitation_email` | Org Admin invites Commissioner |
| `send_reset_password_email` | Forgot password request |
| `send_org_approval_email` | Super Admin approves organization |
| `send_org_rejection_email` | Super Admin rejects organization |
| `send_application_result_email` | Grant finalized → notifies applicant |

> Redis must be running before starting either the API server or the Celery worker.
> Redis **DB0** is used as the Celery broker; **DB1** for app cache, token blacklist, and rate limiting.

---

## API Reference

Full interactive documentation is available at **`/docs`** (Swagger UI) when the server is running.

### Endpoints Overview

| Router | Base Path | Key Endpoints |
|--------|-----------|---------------|
| Auth | `/auth` | `POST /register` · `POST /login` · `POST /logout` · `POST /refresh` · `POST /forgot-password` · `POST /reset-password` |
| Grants | `/grants` | `GET /` · `POST /` · `PUT /{id}` · `DELETE /{id}` · `POST /{id}/publish` · `POST /{id}/finalize` |
| Applications | `/applications` | `POST /` · `GET /` · `GET /{id}` · `POST /{id}/decision` · `POST /{id}/assign` |
| Criteria | `/grants/{id}/criteria` | `POST /` · `GET /` · `PUT /{cid}` · `DELETE /{cid}` |
| Payments | `/payments` | `GET /` · `GET /{id}` · `POST /{id}/mark-paid` |
| Team | `/team` | `GET /` · `DELETE /{id}` · `POST /invitations` |
| Profile | `/profile` | `GET /` · `PUT /` · `GET /applicant` · `PUT /applicant` |
| Users | `/users` | `GET /` · `PUT /{id}/deactivate` |
| Tenants | `/tenants` | `GET /` · `GET /{id}` · `POST /{id}/approve` · `POST /{id}/reject` |
| Audit Logs | `/audit-logs` | `GET /` |
| Permissions | `/permissions` | `GET /` · `POST /` · `DELETE /{id}` · `POST /roles/{role}/assign` |
| Chatbot | `/chatbot` | `POST /chat` |

All endpoints except `/auth/*` require `Authorization: Bearer <access_token>`.  
Permission-protected endpoints additionally require the appropriate `resource:action` permission assigned to the user's role.

---

## Project Structure

```
GrantFlow-Backend/
├── app/
│   ├── core/               # Config, Redis client, Celery app, JWT utilities
│   ├── dependencies/       # get_current_user, require_permission, get_tenant_db
│   ├── middleware/         # LoggingMiddleware, AuthMiddleware, TenantMiddleware
│   ├── models/
│   │   ├── public/         # SQLAlchemy models — shared public schema
│   │   └── tenant/         # SQLAlchemy models — per-organization schema
│   ├── routers/            # FastAPI route handlers (one file per router)
│   ├── schemas/            # Pydantic request / response schemas
│   ├── services/           # Business logic layer (one file per domain)
│   └── tasks/              # Celery async tasks (email.py + ai_tasks.py)
├── alembic/
│   └── versions/           # Migration scripts
├── docs/
│   ├── database.md         # ER diagram + table descriptions
│   └── rbac.md             # Role definitions, permission matrix, tenant isolation
├── requirements.txt
└── .env.example
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/database.md](docs/database.md) | Full ER diagram, public schema and tenant schema table descriptions |
| [docs/rbac.md](docs/rbac.md) | Role definitions, permission matrix, `require_permission()` flow, tenant isolation |
