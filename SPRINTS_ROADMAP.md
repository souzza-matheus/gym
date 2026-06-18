# GymVision — Roadmap de Próximas Entregas
## Planejamento em 3 Sprints (pós-MVP)

> **Contexto:** 23 melhorias já entregues (itens 1–23).
> Este documento organiza as próximas 10 melhorias em 3 sprints de 2 semanas cada.
> Ordenação otimizada: fundação → produto → plataforma.

---

## Sprint 1 — Fundação e Segurança
**Duração:** 2 semanas | **Foco:** estabilidade, compliance e qualidade de código

| Item | Nome | Esforço | Impacto |
|------|------|---------|---------|
| 27 | Backup automático (PostgreSQL + MongoDB → MinIO) | Baixo | Crítico |
| 33 | Refresh token rotation (Redis + invalidação) | Baixo | Alto |
| 32 | LGPD compliance (exportar dados, deletar conta, política) | Médio | Crítico |
| 26 | CI/CD com GitHub Actions (pytest, Gradle test, APK build) | Médio | Alto |

### Entregáveis do Sprint 1
- **Backup:** job agendado (cron) que gera `pg_dump` + `mongodump` diariamente e sobe para bucket MinIO `gymvision-backups`; retenção de 30 dias
- **Token rotation:** tabela `revoked_tokens` no Redis; cada uso de refresh token invalida o anterior e emite um novo par — token roubado não pode ser reutilizado
- **LGPD:**
  - `DELETE /api/v1/users/me` — apaga sessões, analytics e conta
  - `GET /api/v1/users/me/export` — JSON com todos os dados do aluno
  - Tela "Meus Dados" no app Android com botões de exportar e excluir conta
- **CI/CD:** pipeline `.github/workflows/ci.yml` executando testes unitários do pose-service (`pytest`), build do user-service e session-service (`./gradlew test`), lint do dashboard (`eslint`), e build do APK em cada pull request

### Critérios de Aceite
- [ ] Backup roda sem erros às 03:00 UTC e arquivo aparece no MinIO
- [ ] Token roubado após rotação retorna 401
- [ ] Conta excluída não aparece mais em nenhuma coleção/tabela
- [ ] Pipeline verde em PR de exemplo

---

## Sprint 2 — Produto e Experiência
**Duração:** 2 semanas | **Foco:** funcionalidades de alto valor para professor e aluno

| Item | Nome | Esforço | Impacto |
|------|------|---------|---------|
| 28 | Relatório semanal gerencial para o professor (e-mail) | Médio | Alto |
| 29 | Auto-detecção de exercício (regras + Random Forest) | Médio | Alto |
| 31 | Progressão de carga inteligente nos planos de treino | Médio | Alto |
| 30 | FCM push notifications no Android | Médio | Médio |

### Entregáveis do Sprint 2
- **Relatório professor:** toda segunda-feira às 07:00 UTC, e-mail automático para cada professor com: alunos ativos na semana, alunos sem treino há 7+ dias, top 3 alunos que evoluíram, alunos com score caindo ≥ 3 sessões consecutivas
- **Auto-detecção:** nos primeiros 3 segundos de sessão, classificar exercício automaticamente por padrão de landmarks — `SQUAT/LUNGE` (joelho < 120°), `DEADLIFT` (quadril desce < 30 cm), `BENCH_PRESS` (ombros fixos, cotovelo abre), `BENT_OVER_ROW` (tronco > 45°); fallback para seleção manual se confiança < 70%
- **Progressão de carga:** se aluno completou plano com score ≥ 85 e 0 alertas críticos por 2 semanas seguidas → sugestão de +2,5 kg aparece no WorkoutPlanPage para o professor aprovar
- **FCM:** Firebase Cloud Messaging integrado ao app; professor recebe push de alerta `HIGH` mesmo com app em background; aluno recebe push quando sessão é encerrada com score final

### Critérios de Aceite
- [ ] E-mail chega toda segunda com dados corretos da academia de teste
- [ ] App detecta SQUAT corretamente em 80%+ dos casos sem seleção manual
- [ ] Sugestão de progressão aparece após 2 semanas de score alto
- [ ] Push chega em dispositivo com app em background

---

## Sprint 3 — Plataforma e Escala
**Duração:** 2 semanas | **Foco:** observabilidade, alcance e inteligência artificial

| Item | Nome | Esforço | Impacto |
|------|------|---------|---------|
| 25 | Prometheus + Grafana (métricas e alertas) | Médio | Alto |
| 34 | PWA de câmera (alunos sem Android) | Alto | Médio |
| 24 | Modelo de IA próprio — classificador de erros (fine-tuning) | Muito Alto | Alto |

### Entregáveis do Sprint 3
- **Prometheus + Grafana:**
  - pose-service expõe `/metrics` (latência por exercício, frames/s, erros de análise)
  - Grafana com 3 dashboards pré-configurados: operacional (latência p50/p95), produto (sessões/dia, alunos ativos), negócio (crescimento por academia)
  - Alertas: latência p95 > 2s → notificação no Slack/e-mail do admin
- **PWA câmera:**
  - Rota `/train` no dashboard React abre câmera via `MediaDevices.getUserMedia`
  - Envia frames ao `/api/v1/pose/analyze` via fetch (mesmo endpoint do Android)
  - Exibe score e alertas em tempo real; funciona em iPhone Safari e Chrome desktop
  - Manifesto PWA para instalação na tela inicial
- **Modelo de IA próprio (item 24):**
  - Coleta de dataset: 500+ sessões rotuladas com erros biomecânicos anotados
  - Treinamento de classificador (TFLite) com MediaPipe Model Maker
  - Substitui regras hardcoded do `exercise_analyzer.py` por inferência de modelo
  - Acurácia alvo: ≥ 85% vs. anotação humana

### Critérios de Aceite
- [ ] Dashboard Grafana mostra latência em tempo real
- [ ] Alerta dispara quando pose-service demora > 2s
- [ ] Usuário iPhone consegue fazer sessão completa pelo navegador
- [ ] Modelo TFLite detecta `KNEE_CAVE` com ≥ 85% de precisão no conjunto de teste

---

## Resumo Executivo

| Sprint | Período | Tema | Itens |
|--------|---------|------|-------|
| Sprint 1 | Semanas 1–2 | Fundação e Segurança | 27, 33, 32, 26 |
| Sprint 2 | Semanas 3–4 | Produto e Experiência | 28, 29, 31, 30 |
| Sprint 3 | Semanas 5–6 | Plataforma e Escala | 25, 34, 24 |

```
Semana:  1    2    3    4    5    6
         ├────┤ Sprint 1
                   ├────┤ Sprint 2
                             ├────┤ Sprint 3
```

> **Nota sobre o item 24:** classificado no Sprint 3 pois depende de coleta de dataset
> que pode começar durante o Sprint 1 em paralelo (gravar sessões de treino anotadas).
> O item 29 (auto-detecção) foi colocado no Sprint 2 com abordagem baseada em regras,
> podendo ser refinado pelo modelo treinado no Sprint 3 sem bloquear a entrega.
