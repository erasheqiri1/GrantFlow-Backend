# GrantFlow — Backend

A multi-tenant grant management platform built with FastAPI and PostgreSQL. The system supports grant publishing, applicant submissions, AI-powered scoring, commissioner review workflows, and automated finalization.

---

## Architecture Overview

```
Client (React)
      |
      | HTTP/REST
      v
Routers      — receive and validate HTTP requests, delegate to services
Services     — contain all business logic, orchestrate data access
Models       — SQLAlchemy ORM-mapped domain models
Database     — PostgreSQL with schema-based multi-tenancy
Celery       — async email tasks (Redis broker)
```

### Multi-Tenancy

Each organization (tenant) gets its own isolated PostgreSQL schema at approval time. The `public` schema holds shared data — users, tenants, roles, permissions. Every tenant schema holds per-organization data — grants, applications, scores, criteria, attachments.

The tenant is identified from the JWT token on every request. A middleware extracts `tenant_slug` and runs `SET search_path TO tenant_<slug>, public` so all ORM queries are automatically routed to the correct schema.

---

## How Multi-Tenancy Works

```mermaid
flowchart LR
    classDef org fill:#1e3a5f,stroke:#60a5fa,color:#fff,stroke-width:1.5px;
    classDef jwt fill:#78350F,stroke:#FBBF24,color:#fff,stroke-width:1.5px;
    classDef mw fill:#4a2080,stroke:#a78bfa,color:#fff,stroke-width:2px;
    classDef schema fill:#14532D,stroke:#4ADE80,color:#fff,stroke-width:1.5px;
    classDef shared fill:#1F2937,stroke:#9CA3AF,color:#F9FAFB,stroke-width:1.5px;
    classDef blocked fill:#4a1a1a,stroke:#f87171,color:#fff,stroke-width:1.5px;

    A1["OrgAlpha\nBearer: tenant_slug=orgalpha"]
    A2["OrgBeta\nBearer: tenant_slug=orgbeta"]

    subgraph MW["— 1 TenantMiddleware — e njëjta instancë për të gjithë —"]
        M["1. dekodifikon JWT\n2. nxjerr tenant_slug\n3. SET search_path"]
    end

    subgraph DB["PostgreSQL — grantflow_db"]
        PUB["public\nusers · tenants · roles"]
        S1["tenant_orgalpha\ngrants · applications"]
        S2["tenant_orgbeta\ngrants · applications"]
        BLOCK["tenant_orgbeta\ni paaksesueshëm\nnga OrgAlpha"]
    end

    A1 -->|"request"| M
    A2 -->|"request"| M
    M -->|"gjithmonë"| PUB
    M -->|"slug=orgalpha"| S1
    M -->|"slug=orgbeta"| S2
    S1 -.->|"nuk mund ta shohë"| BLOCK

    class A1,A2 org
    class M mw
    class S1,S2 schema
    class PUB shared
    class BLOCK blocked
```

---

## Request Lifecycle

```mermaid
flowchart LR
    A(["👤 User\nklikon Grants"]) --> B["React\nuseEffect fires"]
    B --> C["api.get\n/grants"]
    C --> D["axios interceptor\nshton Authorization\nBearer eyJhbGci..."]
    D --> E(["HTTP GET\nlocalhost:8000\n/grants"])
    E --> F["TenantMiddleware\ndecode JWT\nset search_path"]
    F --> G["Router\nget_grants()"]
    G --> H["Service\nquery DB"]
    H --> I(["JSON Response\n200 OK"])

    style A fill:#14532D,color:#fff
    style D fill:#78350F,color:#fff
    style F fill:#1e3a5f,color:#fff
    style I fill:#14532D,color:#fff
```

---

## Grant Flow

```mermaid
flowchart LR
    A(["📝 DRAFT\nOrg krijon grant"]) --> B["PUBLISHED\nAplikantët aplikojnë"]
    B --> C["CLOSED\nDeadline kaloi ose\nmbyllet manualisht"]
    C --> D["FINALIZED\nAI + Komisioner\nvendosin"]

    subgraph APPS["Aplikimet gjatë PUBLISHED"]
        E["SUBMITTED\nAplikanti dërgon"] --> F["UNDER_REVIEW\nKomisioner shqyrton"]
        F --> G["APPROVED ✓"]
        F --> H["REJECTED ✗"]
    end

    B --> APPS

    style A fill:#78350F,color:#fff
    style B fill:#14532D,color:#fff
    style C fill:#1F2937,color:#fff
    style D fill:#1e3a5f,color:#fff
    style G fill:#14532D,color:#fff
    style H fill:#4a1a1a,color:#fff
```

---

## AI Scoring Flow

```mermaid
flowchart TD
    A(["POST\n/applications/{id}/score"]) --> B{"API key\nekziston?"}
    B -->|"OpenAI"| C["GPT-4o-mini"]
    B -->|"Groq"| D["llama-3.1-8b-instant"]
    B -->|"Asnjë"| E["Heuristic\nFallback"]

    C --> F["_build_prompt\nmotivation + answers\n+ PDF docs"]
    D --> F
    F --> G["AI Response\nscore 0-100\njustification shqip"]
    G --> H["final_score =\nai_score × ai_weight\n+ commissioner × (1-weight)"]
    E --> H

    H --> I[("ai_scores\ntable")]

    style C fill:#1e3a5f,color:#fff
    style D fill:#1e3a5f,color:#fff
    style E fill:#78350F,color:#fff
    style H fill:#14532D,color:#fff
```

---

## Commissioner Assignment — Round Robin

```mermaid
flowchart LR
    A(["Aplikim\nSubmit-ohet"]) --> B["_auto_assign_commissioner"]
    B --> C["Gjej të gjithë\nkomisionerët e tenant-it"]
    C --> D{"Ka komisioner\npа workload record?"}
    D -->|"Po"| E["Zgjedh të parin\npа asnjë caktim"]
    D -->|"Jo"| F["ORDER BY\nassigned_count ASC\nupdated_at ASC"]
    F --> G["Komisioner me\nngarkesë më të vogël\n+ ka pritur më gjatë"]
    E --> H["app.assigned_to = chosen_id\nworkload.assigned_count += 1"]
    G --> H

    style A fill:#14532D,color:#fff
    style F fill:#1e3a5f,color:#fff
    style H fill:#78350F,color:#fff
```

---

## Auto-Finalize Logic

```mermaid
flowchart TD
    A(["set_commissioner_score\nthirret"]) --> B["Ruaj pikët\nrillogarit final_score"]
    B --> C["_check_auto_finalize"]
    C --> D{"Deadline\nka kaluar OSE\ngranti CLOSED?"}
    D -->|"Jo"| E(["Stop\nPrit deadline"])
    D -->|"Po"| F["Merr të gjitha\naplikimet aktive"]
    F --> G{"Të gjitha kanë\ncommissioner_score?"}
    G -->|"Jo"| H(["Stop\nPrit komisionerët"])
    G -->|"Po"| I["finalize_grant()\nautomatik"]
    I --> J["APPROVED / REJECTED\nsipas final_score"]
    J --> K["Email\naplikantëve"]

    style D fill:#78350F,color:#fff
    style G fill:#78350F,color:#fff
    style I fill:#14532D,color:#fff
    style K fill:#1e3a5f,color:#fff
```

---

## RBAC — Role-Based Access Control

Çdo user ka një rol të caktuar në JWT. Çdo endpoint kontrollon rolin para se të ekzekutojë logjikën.

```mermaid
flowchart TD
    classDef role fill:#1e3a5f,stroke:#60a5fa,color:#fff,stroke-width:1.5px;
    classDef check fill:#78350F,stroke:#FBBF24,color:#fff,stroke-width:1.5px;
    classDef allow fill:#14532D,stroke:#4ADE80,color:#fff,stroke-width:1.5px;
    classDef deny fill:#4a1a1a,stroke:#f87171,color:#fff,stroke-width:1.5px;
    classDef action fill:#1F2937,stroke:#9CA3AF,color:#F9FAFB,stroke-width:1.5px;

    REQ(["HTTP Request\n+ Bearer token"])
    MW["Middleware\nnxjerr role nga JWT"]
    CHECK{"user role?"}

    SA["SUPER_ADMIN"]
    OA["ORG_ADMIN"]
    CO["COMMISSIONER"]
    AP["APPLICANT"]

    SA_ACT["aprovo/refuzo org\n menaxho users\n shiko audit logs\n fto super_admin"]
    OA_ACT["krijo/publiko grante\n menaxho ekipin\n shiko aplikimet + scores\n finalizo grante"]
    CO_ACT["shqyrto aplikime\n jep pikë"]
    AP_ACT["apliko për grante\n ndrysho profilin\n shiko aplikimet e veta"]

    DENY(["403 Forbidden"])

    REQ --> MW
    MW --> CHECK
    CHECK -->|"SUPER_ADMIN"| SA --> SA_ACT
    CHECK -->|"ORG_ADMIN"| OA --> OA_ACT
    CHECK -->|"COMMISSIONER"| CO --> CO_ACT
    CHECK -->|"APPLICANT"| AP --> AP_ACT
    CHECK -->|"rol i gabuar"| DENY

    class SA,OA,CO,AP role
    class CHECK check
    class SA_ACT,OA_ACT,CO_ACT,AP_ACT allow
    class DENY deny
    class MW action
```

### Si kontrollohet roli në kod

```python
# Middleware e vendos rolin nga JWT:
request.state.role = payload.get("role")

# get_current_user e lexon:
user = { "role": request.state.role, "user_id": ..., "tenant_slug": ... }

# Çdo endpoint e kontrollon:
if user["role"] != "ORG_ADMIN":
    raise HTTPException(403, "Nuk ke leje")
```

### Struktura e tabelave në DB

```mermaid
erDiagram
    USERS {
        uuid id PK
        string email
        string password_hash
        boolean is_active
        boolean email_verified
    }
    ROLES {
        uuid id PK
        string name
    }
    PERMISSIONS {
        uuid id PK
        string codename
        string resource
        string action
    }
    ROLE_PERMISSIONS {
        uuid id PK
        uuid role_id FK
        uuid permission_id FK
    }
    USER_ROLES {
        uuid id PK
        uuid user_id FK
        uuid role_id FK
        uuid tenant_id FK
    }

    USERS ||--o{ USER_ROLES : "ka rol"
    ROLES ||--o{ USER_ROLES : "i caktuar"
    ROLES ||--o{ ROLE_PERMISSIONS : "ka leje"
    PERMISSIONS ||--o{ ROLE_PERMISSIONS : "i përket"
```

- **`roles`** — 4 role: SUPER_ADMIN, ORG_ADMIN, COMMISSIONER, APPLICANT
- **`permissions`** — veprime specifike: `grants:create`, `applications:score`, etj.
- **`role_permissions`** — cila rol ka cilën leje
- **`user_roles`** — user-i + roli + tenant (një user mund të jetë ORG_ADMIN në OrgAlpha dhe APPLICANT diku tjetër)

### Multi-Tenancy + RBAC bashkë

```
Request vjen
    ↓
TenantMiddleware  →  "je i OrgAlpha"          (IZOLIM — multi-tenancy)
    ↓
get_current_user  →  "je ORG_ADMIN"           (AUTORIZIM — RBAC)
    ↓
✅ Lejohet të krijojë grant në OrgAlpha
```

---

## JWT Authentication

```mermaid
flowchart LR
    A(["POST /auth/login\nemail + password"]) --> B["verify_password\nbcrypt check"]
    B --> C{"Valid?"}
    C -->|"Jo"| D(["401 Unauthorized"])
    C -->|"Po"| E["create_token\nuser_id · role · tenant_slug\nexp 24h"]
    E --> F["JWT\nHS256\nSECRET_KEY"]
    F --> G(["TokenResponse\naccess_token · role · user_id"])

    G --> H["Çdo request\nAuthorization: Bearer ..."]
    H --> I["TenantMiddleware\ndecode + validate"]
    I --> J{"Valid?"}
    J -->|"Jo"| K(["401 Unauthorized"])
    J -->|"Po"| L(["✅ Route Handler"])

    style D fill:#4a1a1a,color:#fff
    style F fill:#78350F,color:#fff
    style G fill:#14532D,color:#fff
    style K fill:#4a1a1a,color:#fff
    style L fill:#14532D,color:#fff
```

---

## Email Verification Flow (Org Registration)

```mermaid
flowchart LR
    A(["POST\n/auth/register-org"]) --> B["Krijo Tenant\nstatus=PENDING"]
    B --> C["Krijo User\nis_active=False\nemail_verified=False"]
    C --> D["Gjenero token\n24h · ruaj në DB"]
    D --> E["Celery Task\nsend_verification_email"]
    E --> F(["📧 Email\nme link verifikimi"])

    F --> G(["GET\n/auth/verify-email?token=..."])
    G --> H["Valido token\nkontrollo skadimin"]
    H --> I["email_verified=True\nis_active=True"]
    I --> J(["✅ Prit aprovimin\nnga Super Admin"])

    style A fill:#1e3a5f,color:#fff
    style E fill:#78350F,color:#fff
    style I fill:#14532D,color:#fff
    style J fill:#78350F,color:#fff
```

---

## Celery Email Tasks

```mermaid
flowchart LR
    subgraph TRIGGERS["Ku thirren"]
        T1["register_org\n→ verification email"]
        T2["finalize_grant\n→ result email"]
        T3["approve_tenant\n→ org approval email"]
        T4["reject_tenant\n→ org rejection email"]
        T5["forgot_password\n→ reset email"]
        T6["invite_user\n→ invitation email"]
    end

    subgraph CELERY["Celery Worker"]
        C1["send_verification_email"]
        C2["send_application_result_email"]
        C3["send_org_approval_email"]
        C4["send_org_rejection_email"]
        C5["send_reset_password_email"]
        C6["send_invitation_email"]
    end

    REDIS[("Redis\nBroker")]

    T1 -->|".delay()"| REDIS
    T2 -->|".delay()"| REDIS
    T3 -->|".delay()"| REDIS
    T4 -->|".delay()"| REDIS
    T5 -->|".delay()"| REDIS
    T6 -->|".delay()"| REDIS

    REDIS --> C1
    REDIS --> C2
    REDIS --> C3
    REDIS --> C4
    REDIS --> C5
    REDIS --> C6

    C1 & C2 & C3 & C4 & C5 & C6 -->|"SMTP\nGmail"| MAIL(["📧 Email\ndërguar"])

    style REDIS fill:#78350F,color:#fff
    style MAIL fill:#14532D,color:#fff
```

---

## Database Schema

```mermaid
erDiagram
    TENANTS {
        uuid id PK
        string slug
        string name
        enum status
        boolean is_active
    }

    USERS {
        uuid id PK
        string email
        string password_hash
        boolean is_active
        boolean email_verified
    }

    GRANTS {
        uuid id PK
        string title
        enum status
        datetime deadline
        float ai_weight
        int max_applicants
    }

    APPLICATIONS {
        uuid id PK
        uuid grant_id FK
        uuid user_id FK
        uuid assigned_to FK
        enum status
        text motivation_letter
        float final_score
    }

    AI_SCORES {
        uuid id PK
        uuid application_id FK
        float ai_score
        float commissioner_score
        float final_score
        string model_used
        text justification
    }

    CRITERIA {
        uuid id PK
        uuid grant_id FK
        string name
        float weight
        boolean is_required
    }

    GRANTS ||--o{ APPLICATIONS : "has"
    GRANTS ||--o{ CRITERIA : "has"
    APPLICATIONS ||--|| AI_SCORES : "scored by"
    USERS ||--o{ APPLICATIONS : "submits"
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.100+ |
| Language | Python 3.11+ |
| Database | PostgreSQL 15 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | JWT (PyJWT) + bcrypt |
| Background Jobs | Celery + Redis |
| AI Integration | Groq API (llama-3.1-8b-instant) / OpenAI |
| PDF Parsing | pdfplumber |
| Documentation | FastAPI Swagger UI (auto-generated) |



## API Overview

Të gjitha endpoint-et kërkojnë `Authorization: Bearer <token>` me përjashtim të `/auth/**`.

| Module | Base Path |
|---|---|
| Authentication | `/auth` |
| Grants | `/grants` |
| Applications | `/applications` |
| AI Scoring | `/applications/{id}/score` |
| Attachments | `/attachments` |
| Team / Invites | `/team` |
| Tenants (Super Admin) | `/tenants` |
| Users / Profile | `/users` |

Dokumentacioni interaktiv: `http://localhost:8000/docs`

---

## Alembic Migrations

```
ef642ea726cd → initial_public_schema
d63e3266533f → fix_tenant_is_active_default
3e22a7665629 → add_user_roles_to_public
f7a3c9e1b402 → add_public_audit_logs
a1b2c3d4e5f6 → add_email_verification  ← HEAD
```

---

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Install

```bash
pip install -r requirements.txt
```

### Environment

Krijo `.env` në root:

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/grantflow_db
SECRET_KEY=your-secret-key-min-32-chars
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your-groq-api-key
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=your@gmail.com
FRONTEND_URL=http://localhost:5173
```

### Database

```bash
python -m alembic upgrade head
python seed.py
```

### Run

```bash
# Backend
uvicorn app.main:app --reload

# Celery Worker (email tasks)
celery -A app.core.celery_app worker --loglevel=info
```

---

## Key Design Decisions

**Schema isolation per tenant** — Çdo organizatë ka schema-n e vet PostgreSQL. Eliminon rrezikun e data leakage dhe lejon backup/delete të plotë të një tenant pa prekur të tjerët.

**JWT contains tenant_slug** — Token mban `tenant_slug` kështu çdo request është i vetë-mjaftueshëm. Middleware nuk ka nevojë për DB lookup shtesë për të identifikuar tenant-in.

**AI weight configurable per grant** — `final_score = ai_score × ai_weight + commissioner_score × (1 - ai_weight)`. Organizata vendos vetë sa beson AI-n (default 60%).

**Auto-finalize** — Pas çdo pikë komisioner sistemi kontrollon: deadline kaloi + të gjitha aplikimet kanë pikë → finalizim automatik pa ndërhyrje manuale.

**Round-robin commissioner assignment** — Kur komisioner kanë ngarkesë të barabartë, merr ai që ka pritur më gjatë (`updated_at ASC` si tiebreaker).

**Celery fallback** — Nëse Celery nuk ecën, email nuk dërgohet por operacioni vazhdon normalisht. Asnjë HTTP request nuk bllokohet nga dështimi i email-it.

**PDF reading for AI** — `pdfplumber` ekstrakton tekstin nga PDF-të e ngarkuara (max 5 faqe, 2000 karaktere) dhe ia kalon AI-t si kontekst shtesë gjatë vlerësimit.
