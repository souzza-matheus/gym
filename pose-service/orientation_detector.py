"""
orientation_detector.py — GymVision Pose Service
=================================================
Detecta automaticamente a orientação da câmera a partir dos landmarks
MoveNet/ML Kit e adapta o pipeline de análise de ângulos articulares.

Orientações suportadas:
  LATERAL  — câmera de lado (perfil esquerdo ou direito)
             → usa apenas o lado visível
  FRONTAL  — câmera de frente (pessoa encarando a câmera)
             → usa landmarks bilaterais, calcula médias
  ANGLED   — câmera em ângulo diagonal (~45°)
             → interpolação ponderada entre lateral e frontal

Heurísticas utilizadas:
  1. Simetria dos ombros: câmera frontal → ombros simétricos horizontalmente
     (|x_left - x_right| pequeno relativo à largura do frame).
     Câmera lateral → ombros quase sobrepostos em x (um muito atrás do outro).
  2. Simetria dos quadris: reforça o sinal dos ombros.
  3. Visibilidade das orelhas: frontal → ambas visíveis com confiança similar.
     Lateral → apenas a orelha do lado visível tem alta confiança.
  4. Posição relativa do nariz: frontal → nariz centrado entre ombros.
     Lateral → nariz claramente fora do intervalo ombro-ombro.

A detecção é feita DEPOIS da inferência MoveNet, sobre os landmarks já
normalizados (0–1), sem custo adicional de rede neural.
"""

from __future__ import annotations

import math
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models import LandmarkInput

logger = logging.getLogger(__name__)

# ── Índices dos landmarks (MediaPipe / ML Kit style, usado pelo projeto) ───────
_NOSE          = 0
_LEFT_EAR      = 7
_RIGHT_EAR     = 8
_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_HIP      = 23
_RIGHT_HIP     = 24
_LEFT_KNEE     = 25
_RIGHT_KNEE    = 26
_LEFT_ANKLE    = 27
_RIGHT_ANKLE   = 28


class CameraOrientation(str, Enum):
    """Orientação detectada da câmera em relação ao sujeito."""
    LATERAL  = "LATERAL"   # Perfil (lateral esquerdo ou direito)
    FRONTAL  = "FRONTAL"   # Frente (encarando a câmera)
    ANGLED   = "ANGLED"    # Ângulo diagonal (~45°)
    UNKNOWN  = "UNKNOWN"   # Landmarks insuficientes para decidir


@dataclass
class OrientationResult:
    """Resultado completo da detecção de orientação."""
    orientation: CameraOrientation

    # Confiança da detecção (0.0–1.0)
    confidence: float

    # Qual lado está visível (relevante para LATERAL/ANGLED)
    # "left"  → lado esquerdo do sujeito está voltado para a câmera
    # "right" → lado direito do sujeito está voltado para a câmera
    # "both"  → ambos visíveis (frontal)
    visible_side: str

    # Score bruto de cada heurística (útil para debug/logging)
    shoulder_symmetry_score: float  # 0 = assimétrico (lateral), 1 = simétrico (frontal)
    ear_symmetry_score: float       # idem
    nose_centering_score: float     # 0 = fora (lateral), 1 = centrado (frontal)

    # Peso sugerido para interpolação lateral/frontal nos ângulos (0=lateral, 1=frontal)
    frontal_weight: float


# ── Thresholds de decisão ──────────────────────────────────────────────────────
# Câmera frontal: distância horizontal entre ombros deve ser relativamente
# grande (ombros lado a lado). Câmera lateral: distância muito pequena
# (ombros sobrepostos em x, um à frente do outro em profundidade).
# Em coordenadas normalizadas 0–1:
_SHOULDER_FRONTAL_MIN = 0.12   # ombros com pelo menos 12% do frame entre si → frontal
_SHOULDER_LATERAL_MAX = 0.06   # ombros a menos de 6% → lateral puro

# Simetria de orelhas: |vis_esq - vis_dir| / max(vis_esq, vis_dir)
_EAR_SYMMETRY_FRONTAL_MIN = 0.0   # quanto menor a diferença, mais frontal
_EAR_SYMMETRY_LATERAL_MAX = 0.60  # diferença > 60% → lateral

# Mínima visibilidade para considerar um landmark confiável na detecção
_MIN_VIS_FOR_DETECTION = 0.15


def detect_orientation(landmarks: list) -> OrientationResult:
    """
    Detecta a orientação da câmera a partir dos landmarks do MoveNet.

    Args:
        landmarks: lista de Landmark (ou LandmarkInput) com atributos
                   landmark_type, x, y, visibility

    Returns:
        OrientationResult com orientação, confiança e metadados
    """
    lm: dict[int, object] = {lm.landmark_type: lm for lm in landmarks}

    # ── 1. Coleta landmarks de referência ─────────────────────────────────────
    l_sh = lm.get(_LEFT_SHOULDER)
    r_sh = lm.get(_RIGHT_SHOULDER)
    l_ear = lm.get(_LEFT_EAR)
    r_ear = lm.get(_RIGHT_EAR)
    nose  = lm.get(_NOSE)
    l_hip = lm.get(_LEFT_HIP)
    r_hip = lm.get(_RIGHT_HIP)

    def vis(landmark) -> float:
        if landmark is None:
            return 0.0
        return getattr(landmark, 'visibility', 0.0)

    def x(landmark) -> Optional[float]:
        if landmark is None:
            return None
        return getattr(landmark, 'x', None)

    # Sem ombros visíveis, não podemos detectar
    if vis(l_sh) < _MIN_VIS_FOR_DETECTION and vis(r_sh) < _MIN_VIS_FOR_DETECTION:
        return OrientationResult(
            orientation=CameraOrientation.UNKNOWN,
            confidence=0.0,
            visible_side="unknown",
            shoulder_symmetry_score=0.5,
            ear_symmetry_score=0.5,
            nose_centering_score=0.5,
            frontal_weight=0.5,
        )

    # ── 2. Heurística A: Simetria de ombros ───────────────────────────────────
    # Câmera frontal → ambos ombros visíveis com x bem separados
    # Câmera lateral → ombros sobrepostos em x (Δx ≈ 0)
    shoulder_dx: Optional[float] = None
    if vis(l_sh) >= _MIN_VIS_FOR_DETECTION and vis(r_sh) >= _MIN_VIS_FOR_DETECTION:
        shoulder_dx = abs((x(l_sh) or 0.0) - (x(r_sh) or 0.0))

    # Score: 0 = lateral puro, 1 = frontal puro
    if shoulder_dx is None:
        sh_score = 0.3  # apenas um ombro visível → provavelmente lateral
    else:
        sh_score = _clamp(
            _remap(shoulder_dx, _SHOULDER_LATERAL_MAX, _SHOULDER_FRONTAL_MIN)
        )

    # ── 3. Heurística B: Simetria de visibilidade das orelhas ─────────────────
    vis_l_ear = vis(l_ear)
    vis_r_ear = vis(r_ear)
    max_ear = max(vis_l_ear, vis_r_ear)

    if max_ear < _MIN_VIS_FOR_DETECTION:
        ear_score = 0.5  # sem orelhas, neutro
    else:
        ear_diff_ratio = abs(vis_l_ear - vis_r_ear) / max_ear
        # Diferença grande → assimétrico → lateral
        ear_score = _clamp(1.0 - _remap(ear_diff_ratio, _EAR_SYMMETRY_FRONTAL_MIN, _EAR_SYMMETRY_LATERAL_MAX))

    # ── 4. Heurística C: Centralização do nariz entre os ombros ───────────────
    nose_score = 0.5  # default neutro
    if (nose and vis(nose) >= _MIN_VIS_FOR_DETECTION and
            vis(l_sh) >= _MIN_VIS_FOR_DETECTION and
            vis(r_sh) >= _MIN_VIS_FOR_DETECTION):
        x_l = x(l_sh) or 0.0
        x_r = x(r_sh) or 0.0
        x_nose = x(nose) or 0.0
        sh_min, sh_max = min(x_l, x_r), max(x_l, x_r)
        sh_width = sh_max - sh_min

        if sh_width > 0.01:
            # Quanto o nariz está dentro do intervalo ombro-ombro
            # frontal → nariz no meio → score ~1
            # lateral → nariz fora do range → score ~0
            relative_pos = (x_nose - sh_min) / sh_width
            # Centralidade: 1 quando em 0.5, decai para extremos
            nose_score = _clamp(1.0 - abs(relative_pos - 0.5) * 2.0)

    # ── 5. Heurística D: Simetria de quadris (reforçador) ─────────────────────
    hip_score = 0.5
    if vis(l_hip) >= _MIN_VIS_FOR_DETECTION and vis(r_hip) >= _MIN_VIS_FOR_DETECTION:
        hip_dx = abs((x(l_hip) or 0.0) - (x(r_hip) or 0.0))
        hip_score = _clamp(
            _remap(hip_dx, _SHOULDER_LATERAL_MAX, _SHOULDER_FRONTAL_MIN)
        )

    # ── 6. Combina heurísticas com pesos ──────────────────────────────────────
    # Ombros e quadris são os sinais mais confiáveis para a distinção lateral/frontal
    weights = {
        "shoulder": 0.40,
        "ear":      0.20,
        "nose":     0.25,
        "hip":      0.15,
    }
    frontal_weight = (
        weights["shoulder"] * sh_score +
        weights["ear"]      * ear_score +
        weights["nose"]     * nose_score +
        weights["hip"]      * hip_score
    )

    # ── 7. Classifica orientação ───────────────────────────────────────────────
    # frontal_weight: 0.0 = lateral puro, 1.0 = frontal puro
    # Zona de transição 0.35–0.65 → ANGLED
    if frontal_weight >= 0.65:
        orientation = CameraOrientation.FRONTAL
        confidence = _clamp((frontal_weight - 0.65) / 0.35)
    elif frontal_weight <= 0.35:
        orientation = CameraOrientation.LATERAL
        confidence = _clamp((0.35 - frontal_weight) / 0.35)
    else:
        orientation = CameraOrientation.ANGLED
        # Confiança máxima no centro (0.5) da zona de transição
        confidence = _clamp(1.0 - abs(frontal_weight - 0.5) / 0.15)

    # ── 8. Determina lado visível ──────────────────────────────────────────────
    visible_side = _determine_visible_side(lm, orientation, vis, x)

    result = OrientationResult(
        orientation=orientation,
        confidence=round(confidence, 3),
        visible_side=visible_side,
        shoulder_symmetry_score=round(sh_score, 3),
        ear_symmetry_score=round(ear_score, 3),
        nose_centering_score=round(nose_score, 3),
        frontal_weight=round(frontal_weight, 3),
    )

    logger.debug(
        f"Orientação detectada: {orientation.value} "
        f"(fw={frontal_weight:.2f}, conf={confidence:.2f}, lado={visible_side}) | "
        f"sh={sh_score:.2f} ear={ear_score:.2f} nose={nose_score:.2f} hip={hip_score:.2f}"
    )

    return result


def _determine_visible_side(
    lm: dict,
    orientation: CameraOrientation,
    vis_fn,
    x_fn,
) -> str:
    """
    Determina qual lado do sujeito está voltado para a câmera.

    Para câmera LATERAL: o lado com maior visibilidade de joelho/tornozelo
    é o lado visível (está na frente).
    Para câmera FRONTAL: "both".
    Para câmera ANGLED: o lado dominante.
    """
    if orientation == CameraOrientation.FRONTAL:
        return "both"

    l_knee  = lm.get(_LEFT_KNEE)
    r_knee  = lm.get(_RIGHT_KNEE)
    l_ankle = lm.get(_LEFT_ANKLE)
    r_ankle = lm.get(_RIGHT_ANKLE)
    l_hip   = lm.get(_LEFT_HIP)
    r_hip   = lm.get(_RIGHT_HIP)

    # Soma de visibilidades dos joints inferiores por lado
    left_vis  = sum([vis_fn(l_knee), vis_fn(l_ankle), vis_fn(l_hip)])
    right_vis = sum([vis_fn(r_knee), vis_fn(r_ankle), vis_fn(r_hip)])

    if left_vis > right_vis + 0.15:
        return "left"
    elif right_vis > left_vis + 0.15:
        return "right"
    else:
        # Muito similar — verifica posição x dos joelhos
        # Na câmera lateral, o joelho do lado visível tende a estar mais à frente
        if l_knee and r_knee:
            lx = x_fn(l_knee) or 0.0
            rx = x_fn(r_knee) or 0.0
            return "left" if lx < rx else "right"  # mais à esquerda do frame → lado esquerdo na frente
        return "left" if left_vis >= right_vis else "right"


# ── Utilitários ───────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _remap(v: float, in_min: float, in_max: float) -> float:
    """Remapeia v do intervalo [in_min, in_max] para [0, 1]."""
    if abs(in_max - in_min) < 1e-9:
        return 0.0
    return (v - in_min) / (in_max - in_min)


# ── Seleção de landmarks por orientação ───────────────────────────────────────

def select_knee_angle_landmarks(
    lm: dict,
    orientation_result: OrientationResult,
    min_visibility: float = 0.2,
) -> tuple[Optional[object], Optional[object], Optional[object],
           Optional[object], Optional[object], Optional[object]]:
    """
    Seleciona os landmarks de hip/knee/ankle mais apropriados para o ângulo
    de câmera detectado.

    Returns:
        (primary_hip, primary_knee, primary_ankle,
         secondary_hip, secondary_knee, secondary_ankle)

    Para LATERAL: primary = lado visível, secondary = None
    Para FRONTAL: primary = esquerdo, secondary = direito (ambos usados)
    Para ANGLED:  primary = lado dominante, secondary = outro lado (ponderado)
    """
    def get(idx: int) -> Optional[object]:
        lmk = lm.get(idx)
        if lmk is None or getattr(lmk, 'visibility', 0.0) < min_visibility:
            return None
        return lmk

    l_hip   = get(_LEFT_HIP)
    l_knee  = get(_LEFT_KNEE)
    l_ankle = get(_LEFT_ANKLE)
    r_hip   = get(_RIGHT_HIP)
    r_knee  = get(_RIGHT_KNEE)
    r_ankle = get(_RIGHT_ANKLE)

    if orientation_result.orientation == CameraOrientation.FRONTAL:
        # Câmera frontal: usa ambos os lados — chamador calculará média
        return l_hip, l_knee, l_ankle, r_hip, r_knee, r_ankle

    if orientation_result.orientation == CameraOrientation.LATERAL:
        # Lateral: usa somente o lado visível
        if orientation_result.visible_side == "left":
            return l_hip, l_knee, l_ankle, None, None, None
        else:
            return r_hip, r_knee, r_ankle, None, None, None

    # ANGLED: usa ambos, mas o chamador vai ponderar pelo frontal_weight
    if orientation_result.visible_side == "left":
        return l_hip, l_knee, l_ankle, r_hip, r_knee, r_ankle
    else:
        return r_hip, r_knee, r_ankle, l_hip, l_knee, l_ankle


def blend_landmarks(
    primary,
    secondary,
    frontal_weight: float,
) -> Optional[object]:
    """
    Cria um landmark "virtual" interpolado entre primary e secondary
    para câmera em ângulo. Retorna primary se secondary for None.

    frontal_weight = 0.0 → usa primary puro (lateral)
    frontal_weight = 1.0 → média dos dois (frontal)
    """
    if primary is None:
        return secondary
    if secondary is None:
        return primary

    # frontal_weight controla o quanto puxamos para a média bilateral
    # Para ângulo (~0.5): peso = 0.5 → blend de 50%
    w_sec = frontal_weight  # quanto do lado secundário incorporamos
    w_pri = 1.0 - w_sec

    # Cria objeto "virtual" com x/y interpolados
    class BlendedLandmark:
        def __init__(self):
            px = getattr(primary, 'x', 0.0)
            py = getattr(primary, 'y', 0.0)
            sx = getattr(secondary, 'x', 0.0)
            sy = getattr(secondary, 'y', 0.0)
            pv = getattr(primary, 'visibility', 0.9)
            sv = getattr(secondary, 'visibility', 0.9)

            self.x = w_pri * px + w_sec * sx
            self.y = w_pri * py + w_sec * sy
            self.z = 0.0
            self.visibility = min(pv, sv)  # conservador: usa a menor visibilidade
            self.landmark_type = getattr(primary, 'landmark_type', -1)

    return BlendedLandmark()
