# Divergências: prompt de origem vs. código real (`exercise_analyzer.py` / `angle_calculator.py`)

Extraído de `RELATORIO_CALCULOS_BIOMEDICOS.md` (seção 6) como referência
rápida e isolada. Cada item foi confirmado **executando o código real**
(scripts de apoio + `tests/test_exercise_analyzer_extended.py`), não por
inspeção visual.

## 1. `back_angle` usa 2 pontos, não 3

- **Prompt assume**: ângulo do tronco = `calculate_angle(ombro, quadril, joelho)`
  (arccos, 3 pontos, vértice no quadril).
- **Código real** (`angle_calculator._angles_lateral`, linhas 213-228):
  `back_angle = atan2(|quadril.x - ombro.x|, |quadril.y - ombro.y|)` —
  **2 pontos** (ombro→quadril vs. vertical). O joelho não entra no cálculo.
- **Impacto**: os conjuntos de landmarks sintéticos do prompt (desenhados
  para a fórmula de 3 pontos) não reproduzem os erros descritos quando
  processados pelo pipeline real:

  | Cenário | Ângulo 3 pontos (prompt) | `back_angle` real (2 pontos) | Dispara erro? |
  |---|---|---|---|
  | Squat "BACK_NOT_STRAIGHT" | 161.76° | **12.53°** | Não (threshold real=45°) |
  | Deadlift "BACK_TOO_CURVED" | 159.67° | **14.62°** | Não (threshold real=30°) |

## 2. `KNEE_CAVE` — threshold e métrica diferentes

- **Prompt assume**: `desvio = (x_joelho - x_tornozelo) / (x_ombro_D - x_ombro_E)`,
  threshold 4% (de Padua et al., 2009).
- **Código real** (`_analyze_squat`, linha 252): `(l_knee.x - l_ankle.x) * 100`
  — diferença bruta de coordenada normalizada, **sem dividir pela largura
  dos ombros**. Threshold real = **2.0**, não 4.0. Sempre `risk_level=MEDIUM`
  (binário: dispara ou não — não há 3 faixas LOW/MEDIUM/HIGH como o prompt
  descreve).

## 3. `BENT_OVER_ROW` não tem `TORSO_NOT_PARALLEL`

- **Prompt assume**: `ErrorType.TORSO_NOT_PARALLEL`, banda 30°-60° do tronco
  em relação à horizontal.
- **Código real**: esse `ErrorType` **não existe** em `models.py`.
  `_analyze_bent_over_row()` só verifica `BACK_ROUNDED` (>35° MEDIUM, >52.5°
  HIGH) e `ROW_INCOMPLETE` (amplitude do cotovelo <120°).

## 4. `LUNGE` não tem `KNEE_CAVE` nem `FRONT_KNEE_FORWARD`

- **Prompt assume**: LUNGE tem checagem de joelho valgo (`KNEE_CAVE`) e
  joelho à frente do pé (`FRONT_KNEE_FORWARD`), com referências peer-review.
- **Código real**: `_analyze_lunge()` só verifica `DEPTH_INSUFFICIENT`
  (banda de ângulo do joelho frontal, [85°,100°], risco sempre LOW) e
  `BACK_NOT_STRAIGHT` (>40°, risco sempre MEDIUM — sem escalonar para HIGH).

## 5. Supino — abertura do cotovelo medida diferente

- **Prompt assume**: `abertura_E/D = |x_ombro - x_cotovelo| / largura_ombros`,
  calculada **por lado**, com banda MEDIUM (20-35%) / HIGH (>35%).
- **Código real** (linhas 456-468, câmera frontal `fw≥0.5`):
  `flare_pct = ((largura_total_cotovelos - largura_ombros) / largura_ombros) * 100`
  — largura **total** cotovelo-a-cotovelo, não por lado. Threshold = 20%,
  mas **sempre dispara em HIGH** — não existe banda MEDIUM.

## 6. `SQUAT`/`BACK_NOT_STRAIGHT` só tem 2 faixas de risco

- **Prompt assume**: 4 faixas — OK (<45°), LOW_RISK (45-55°), MEDIUM_RISK
  (55-63°), HIGH_RISK (>63°).
- **Código real**: 2 faixas — MEDIUM (45°-63°), HIGH (>63°, onde
  63 = 45×1.4). Não existe faixa LOW_RISK separada.

## 7. Suíte de testes já estava muito além do assumido

- **Prompt assume**: 34 testes, 7 classes, 0.13s de execução.
- **Estado real ANTES deste trabalho**: 53 testes em 12 classes só em
  `test_exercise_analyzer.py` (83 testes contando a suíte inteira do
  pose-service). `LUNGE` de fato não tinha classe de teste dedicada
  (confirmado por grep) — esse gap específico do prompt estava correto.

## 8. `MIN_VISIBILITY` real é 0.2, não o que o prompt supõe

- **Prompt assume**: landmarks com `visibility=0.3` devem ser filtrados
  como "abaixo do threshold".
- **Código real** (`angle_calculator.py`, `_get()`): filtra quando
  `visibility <= MIN_VISIBILITY` e `MIN_VISIBILITY = 0.2`. Logo
  `visibility=0.3` **não seria filtrada** (0.3 > 0.2). É preciso usar um
  valor ≤0.2 (ex. 0.1) para de fato exercitar esse caminho — foi o valor
  usado no teste gerado (`TestLowVisibilityLandmarks`).

## 9. `detect_phase(160.0)` não é STANDING

- Threshold é `> 160.0` estrito. Ângulo exatamente 160° cai no ramo `else`
  (sem `prev_angle` → DESCENDING), não STANDING. Caso de contorno não
  mencionado no prompt de origem.

## 10. Score mínimo real de um frame de SQUAT é 10.0, não 0.0

- O máximo de erros simultâneos que `_analyze_squat` pode gerar num único
  frame é 6 (com `frontal_weight=0.5`, faixa onde `knee_cave` e
  `knee_over_toe` ficam ativos ao mesmo tempo): DEPTH_INSUFFICIENT(-5) +
  KNEE_CAVE_LEFT(-15) + KNEE_CAVE_RIGHT(-15) + KNEE_OVER_TOE_LEFT(-15) +
  KNEE_OVER_TOE_RIGHT(-15) + BACK_NOT_STRAIGHT HIGH(-25) = -90 → score 10.0.
  O piso de 0.0 em `calculate_score()` existe e funciona (validado
  isoladamente), mas um único frame de SQUAT sozinho não consegue atingi-lo.

## 11. Mecanismo de config de URL do Android já existe

- **Prompt pede**: `ConfigLoader.kt` + `assets/config.json` para configurar
  a URL do backend em runtime.
- **Já existe e funciona**: `API_HOST` configurável via propriedade Gradle
  (`./gradlew assembleDebug -PapiHost=<IP>`, `build.gradle.kts:10`, exposto
  como `BuildConfig.API_HOST`, consumido em `ApiClient.kt`). Duplicar com um
  mecanismo runtime concorrente criaria duas fontes de verdade divergentes —
  **não implementado**, documentado aqui em vez disso.

## 12. Kong não tinha CORS configurado (gap real, não do prompt)

- Diferente dos itens acima (onde o código diverge do prompt), este é um
  gap real que o prompt corretamente identificou: `api-gateway/kong.yml`
  não tinha nenhum plugin `cors` antes deste trabalho — foi adicionado.
