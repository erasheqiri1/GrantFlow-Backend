``` mermaid 
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
