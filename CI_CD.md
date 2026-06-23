# CI/CD — GymVision

Pipeline definida em [`.github/workflows/ci.yml`](.github/workflows/ci.yml), executada pelo GitHub Actions.

> Versão com diagramas (Mermaid): [`CI_CD_VISUAL.md`](CI_CD_VISUAL.md).

## Quando dispara

- **Push** em `main`, `master` ou `develop`.
- **Pull request** contra `main` ou `master`.

Só o push em `main`/`master` chega a publicar imagens e fazer deploy — push em `develop` e PRs rodam apenas os jobs de teste/build (ver abaixo).

## Etapas (jobs)

```
user-service-test ──┐
pose-service-test ──┤
session-service-build ─┤
dashboard-build ────┤──► build-and-push ──► deploy-staging
android-build ──────┘
analytics-service-test       (independente, não bloqueia o push)
compose-validate             (independente, não bloqueia o push)
```

| Job | O que faz | Falha o pipeline se... |
|---|---|---|
| `user-service-test` | Sobe Postgres + Redis de teste, roda `./gradlew test jacocoTestReport` no `user-service` (Kotlin/Spring) | Algum teste falhar |
| `pose-service-test` | Instala deps Python e roda `pytest tests/` no `pose-service` | Algum teste falhar |
| `session-service-build` | `./gradlew build -x test` no `session-service` (só compila, não roda os testes aqui) | Erro de compilação |
| `analytics-service-test` | `flake8` no `analytics-service` (lint, não tem testes automatizados ainda) | Erro de lint |
| `dashboard-build` | `npm ci` + `npm run build` no `dashboard` (React/Vite) | Build do frontend falhar |
| `android-build` | `./gradlew assembleDebug` no `android-app`; sobe o APK gerado como artefato (retenção de 7 dias) | Erro de compilação do app |
| `compose-validate` | `docker compose config --quiet` — valida que o `docker-compose.yml` é sintaticamente válido | YAML do compose inválido |
| `build-and-push` | Builda e publica as imagens Docker de cada serviço (ver abaixo) | Só roda em push para `main`/`master`, depois que os testes/builds principais passam |
| `deploy-staging` | Conecta via SSH no host de staging e roda `docker compose pull && up -d` | Só roda depois de `build-and-push`; precisa dos secrets `STAGING_*` |

## Onde as imagens são publicadas

`build-and-push` builda cada serviço com `docker/build-push-action` e publica **a mesma imagem em dois registries**:

- **GitHub Container Registry**: `ghcr.io/<owner>/gymvision/<serviço>:latest`
- **Docker Hub**: `docker.io/souzza-matheus/gymvision-<serviço>:latest`

Serviços publicados: `user-service`, `pose-service`, `session-service`, `analytics-service`, `backup-service`, `notification-service`.

> `dashboard` e `android-app` não têm imagem Docker — o dashboard é build estático (Vite) e o Android gera um APK, não um container.

## Secrets necessários (configurar em *Settings → Secrets and variables → Actions* no GitHub)

| Secret | Para quê | Observação |
|---|---|---|
| `GITHUB_TOKEN` | Login no `ghcr.io` | Gerado automaticamente pelo GitHub Actions, não precisa criar |
| `DOCKERHUB_USERNAME` | Login no Docker Hub | Username/organização do Docker Hub |
| `DOCKERHUB_TOKEN` | Login no Docker Hub | Access Token criado em Docker Hub → *Account Settings → Security → New Access Token* (não usar a senha da conta) |
| `STAGING_HOST` | SSH no `deploy-staging` | IP/hostname do servidor de staging |
| `STAGING_USER` | SSH no `deploy-staging` | Usuário SSH |
| `STAGING_SSH_KEY` | SSH no `deploy-staging` | Chave privada SSH |

Sem `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`, o step "Log in to Docker Hub" falha e nenhuma imagem é publicada (nem no ghcr.io, já que o job todo falha nesse step). Sem os `STAGING_*`, o `deploy-staging` falha, mas isso não afeta a publicação das imagens — só o deploy automático.

## Cache

Os builds de imagem usam cache do GitHub Actions (`cache-from`/`cache-to: type=gha`) — builds subsequentes do mesmo serviço reaproveitam camadas não alteradas, acelerando o pipeline.

## Rodar localmente sem esperar o CI

```bash
# Testes (espelham os jobs *-test)
cd user-service && ./gradlew test
cd pose-service && pytest tests/

# Build de imagem (espelha o build-and-push, sem publicar)
docker build -t gymvision-pose-service ./pose-service

# Validar o compose (espelha compose-validate)
docker compose config --quiet
```
