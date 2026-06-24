# CI/CD — GymVision (versão visual)

Complemento ilustrado de [`CI_CD.md`](CI_CD.md) (que tem as tabelas detalhadas). Os diagramas abaixo são [Mermaid](https://mermaid.js.org/) — o GitHub renderiza automaticamente como imagem ao visualizar este arquivo no repositório.

## 1. Disparo e dependência entre jobs

```mermaid
flowchart LR
    subgraph Trigger["Disparo"]
        PUSH["push: main / master / develop"]
        PR["pull_request: main / master"]
    end

    subgraph Testes["Testes & Build (sempre rodam)"]
        UT["user-service-test\nGradle + Postgres + Redis"]
        PT["pose-service-test\npytest"]
        ST["session-service-build\nGradle (build -x test)"]
        AT["analytics-service-test\nflake8"]
        DB["dashboard-build\nnpm ci + build"]
        AB["android-build\nGradle assembleDebug"]
        CV["compose-validate\ndocker compose config"]
    end

    BP["build-and-push\nDocker build + push"]
    DS["deploy-staging\nSSH + docker compose up"]

    PUSH --> UT
    PUSH --> PT
    PUSH --> ST
    PUSH --> AT
    PUSH --> DB
    PUSH --> AB
    PUSH --> CV
    PR --> UT
    PR --> PT
    PR --> ST
    PR --> AT
    PR --> DB
    PR --> AB
    PR --> CV

    UT --> BP
    PT --> BP
    ST --> BP
    DB --> BP
    AB --> BP
    BP -->|"só se push em main/master"| DS

    style BP fill:#1f6feb,color:#fff
    style DS fill:#2da44e,color:#fff
```

`analytics-service-test` e `compose-validate` rodam sempre, mas não bloqueiam `build-and-push` (não estão no `needs:`). Se algum dos outros 5 falhar, a publicação não acontece.

## 2. Para onde vão as imagens

```mermaid
flowchart LR
    subgraph Build["build-and-push (Docker Buildx)"]
        US[user-service]
        PS[pose-service]
        SS[session-service]
        AS[analytics-service]
        BS[backup-service]
        NS[notification-service]
    end

    GHCR["ghcr.io/<owner>/gymvision/*<br/>(GitHub Container Registry)"]
    DH["docker.io/souzzamatheus/gymvision-*<br/>(Docker Hub)"]

    US & PS & SS & AS & BS & NS --> GHCR
    US & PS & SS & AS & BS & NS --> DH

    style GHCR fill:#24292e,color:#fff
    style DH fill:#1d63ed,color:#fff
```

`dashboard` (build estático) e `android-app` (gera `.apk`) não entram aqui — não são publicados como imagem Docker.

## 3. Deploy em staging

```mermaid
sequenceDiagram
    participant GH as GitHub Actions
    participant DH as Docker Hub / ghcr.io
    participant SV as Servidor de Staging (SSH)

    GH->>DH: build-and-push concluído
    GH->>SV: conecta via SSH (secrets STAGING_HOST/USER/SSH_KEY)
    SV->>DH: docker compose pull
    DH-->>SV: baixa imagens :latest atualizadas
    SV->>SV: docker compose up -d --remove-orphans
    SV-->>GH: docker compose ps (status final)
```

## 4. Secrets exigidos por etapa

```mermaid
flowchart TB
    GHL["Login ghcr.io"] -->|usa| GHT["GITHUB_TOKEN (automático)"]
    DHL["Login Docker Hub"] -->|usa| DHU["DOCKERHUB_USERNAME"]
    DHL -->|usa| DHK["DOCKERHUB_TOKEN"]
    SSH["deploy-staging"] -->|usa| SH["STAGING_HOST"]
    SSH -->|usa| SU["STAGING_USER"]
    SSH -->|usa| SK["STAGING_SSH_KEY"]

    style DHU fill:#f59e0b,color:#000
    style DHK fill:#f59e0b,color:#000
```

`DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN` (em destaque) ainda não foram configurados no repositório — sem eles, o job `build-and-push` falha no login do Docker Hub.
