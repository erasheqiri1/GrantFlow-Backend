# RBAC & Permissions

GrantFlow uses a **database-driven Role-Based Access Control** system. Permissions are stored as `resource:action` string pairs and assigned to roles via the `role_permissions` join table. The `require_permission()` dependency enforces them at the endpoint level.

---

## Roles & Permissions

```mermaid
flowchart LR
    subgraph ROLES["Rolet"]
        SA["SUPER_ADMIN"]:::superadmin
        OA["ORG_ADMIN"]:::orgadmin
        CO["COMMISSIONER"]:::commissioner
        AP["APPLICANT"]:::applicant
    end

    subgraph SA_PERMS["SUPER_ADMIN"]
        SA1["tenants:approve\ntenants:reject\ntenants:read\ntenants:deactivate"]:::perm
        SA2["users:read\nusers:deactivate\nusers:assign_role"]:::perm
        SA3["audit:read"]:::perm
        SA4["profile:read\nprofile:update"]:::perm
    end

    subgraph OA_PERMS["ORG_ADMIN"]
        OA1["grants:create\ngrants:read\ngrants:update\ngrants:publish\ngrants:delete"]:::perm
        OA2["applications:read_all"]:::perm
        OA3["invitations:send\nteam:read\nteam:manage"]:::perm
        OA4["profile:read\nprofile:update"]:::perm
    end

    subgraph CO_PERMS["COMMISSIONER"]
        CO1["grants:read"]:::perm
        CO2["applications:read_all"]:::perm
        CO3["profile:read\nprofile:update"]:::perm
    end

    subgraph AP_PERMS["APPLICANT"]
        AP1["grants:read"]:::perm
        AP2["applications:submit\napplications:read_own"]:::perm
        AP3["profile:read\nprofile:update"]:::perm
    end

    SA --> SA1 & SA2 & SA3 & SA4
    OA --> OA1 & OA2 & OA3 & OA4
    CO --> CO1 & CO2 & CO3
    AP --> AP1 & AP2 & AP3

    classDef superadmin   fill:#4c1d95,stroke:#8b5cf6,color:#fff
    classDef orgadmin     fill:#1e3a5f,stroke:#60a5fa,color:#fff
    classDef commissioner fill:#1a3340,stroke:#0ea5e9,color:#fff
    classDef applicant    fill:#14532d,stroke:#22c55e,color:#fff
    classDef perm         fill:#1F2937,stroke:#4B5563,color:#9CA3AF
```

---

## How `require_permission()` Works

```mermaid
flowchart LR
    subgraph DB_RBAC["Database — RBAC Tabelat"]
        T_ROLE["roles\nid | name"]:::table
        T_PERM["permissions\nid | codename\nresource | action"]:::table
        T_RP["role_permissions\nrole_id | permission_id"]:::table
        T_UR["user_roles\nuser_id | role_id | tenant_id"]:::table

        T_ROLE -->|"N:M"| T_RP
        T_PERM -->|"N:M"| T_RP
        T_UR --> T_ROLE
    end

    subgraph FLOW_RBAC["Si funksionon require_permission()"]
        F1["Request vjen\nBearer token"]:::step
        F2["AuthMiddleware\ndekodoj JWT\nextract role + user_id"]:::step
        F3["require_permission\nRole → RolePermission\n→ Permission"]:::step
        F4{"Ka leje?"}:::decision
        F5["403 Forbidden"]:::denied
        F6["Vazhdon te\nendpoint-i"]:::allowed

        F1 --> F2 --> F3 --> F4
        F4 -->|"Jo"| F5
        F4 -->|"Po"| F6
    end

    subgraph TENANT_ISO["Izolimi sipas Tenant"]
        TI1["ORG_ADMIN — Org A\ntenant_slug = org-a"]:::tenant
        TI2["ORG_ADMIN — Org B\ntenant_slug = org-b"]:::tenant
        TI3["search_path =\ntenant_org_a"]:::schema
        TI4["search_path =\ntenant_org_b"]:::schema
        TI5["Shikon vetem\ngrantet e Org A"]:::isolated
        TI6["Shikon vetem\ngrantet e Org B"]:::isolated

        TI1 --> TI3 --> TI5
        TI2 --> TI4 --> TI6
    end

    classDef table        fill:#1c2432,stroke:#6B7280,color:#fff
    classDef step         fill:#1F2937,stroke:#4B5563,color:#fff
    classDef decision     fill:#1c1c2e,stroke:#818cf8,color:#fff
    classDef denied       fill:#7f1d1d,stroke:#ef4444,color:#fff
    classDef allowed      fill:#14532d,stroke:#22c55e,color:#fff
    classDef tenant       fill:#1e3a5f,stroke:#60a5fa,color:#fff
    classDef schema       fill:#2d1f0e,stroke:#f59e0b,color:#fff
    classDef isolated     fill:#1F2937,stroke:#4B5563,color:#9CA3AF
```

---

## Permission Matrix

| Permission | Super Admin | Org Admin | Commissioner | Applicant |
|------------|:-----------:|:---------:|:------------:|:---------:|
| `tenants:approve` | ✓ | — | — | — |
| `tenants:reject` | ✓ | — | — | — |
| `tenants:read` | ✓ | — | — | — |
| `tenants:deactivate` | ✓ | — | — | — |
| `users:read` | ✓ | — | — | — |
| `users:deactivate` | ✓ | — | — | — |
| `users:assign_role` | ✓ | — | — | — |
| `audit:read` | ✓ | — | — | — |
| `grants:create` | — | ✓ | — | — |
| `grants:read` | — | ✓ | ✓ | ✓ |
| `grants:update` | — | ✓ | — | — |
| `grants:publish` | — | ✓ | — | — |
| `grants:delete` | — | ✓ | — | — |
| `applications:read_all` | — | ✓ | ✓ | — |
| `applications:submit` | — | — | — | ✓ |
| `applications:read_own` | — | — | — | ✓ |
| `invitations:send` | — | ✓ | — | — |
| `team:read` | — | ✓ | — | — |
| `team:manage` | — | ✓ | — | — |
| `profile:read` | ✓ | ✓ | ✓ | ✓ |
| `profile:update` | ✓ | ✓ | ✓ | ✓ |

---

## Tenant Isolation

Each approved organization gets its own PostgreSQL schema (`tenant_{slug}`). `TenantMiddleware` extracts the tenant slug from the JWT and issues `SET search_path TO tenant_{slug}, public` before every request, ensuring that all ORM queries are automatically scoped to that organization's data. No cross-tenant data leakage is possible at the query level.
