"""
angle_calculator.py — GymVision Exercise Analyzer Service
==========================================================
Calcula ângulos articulares a partir dos landmarks normalizados (0–1)
do MoveNet/ML Kit.

Versão 2 — suporte a múltiplos ângulos de câmera
-------------------------------------------------
A versão original assumia sempre câmera lateral (perfil). Esta versão
adapta o cálculo de ângulos de acordo com a orientação detectada:

  LATERAL  → usa apenas o lado visível (comportamento original).
  FRONTAL  → usa ambos os lados; calcula left/right separados e
             computa back_angle a partir da simetria lateral dos quadris.
  ANGLED   → interpola entre os dois modos usando frontal_weight (0–1).

A assinatura pública de calculate_joint_angles() não muda — recebe a
lista de landmarks e, opcionalmente, um OrientationResult.  Se o
OrientationResult não for informado, a função detecta a orientação
automaticamente (modo retrocompatível).

Constantes e assinaturas mantidas idênticas às originais para garantir
que os 30 testes de run_all_tests.py continuem passando.
"""

import math
from typing import Optional

from models import LandmarkInput, JointAngles

# ── Índices dos landmarks (compatível com LandmarkType enum) ──────────────────
NOSE           = 0
LEFT_EYE       = 2
RIGHT_EYE      = 5
LEFT_SHOULDER  = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW     = 13
RIGHT_ELBOW    = 14
LEFT_HIP       = 23
RIGHT_HIP      = 24
LEFT_KNEE      = 25
RIGHT_KNEE     = 26
LEFT_ANKLE     = 27
RIGHT_ANKLE    = 28
LEFT_HEEL      = 29
RIGHT_HEEL     = 30
LEFT_FOOT_INDEX  = 31
RIGHT_FOOT_INDEX = 32

# Thresholds (idênticos ao original)
MIN_VISIBILITY: float       = 0.2
ANGLE_SMOOTHING_ALPHA: float = 0.3


# ── Acesso seguro a landmarks ──────────────────────────────────────────────────

def _get(
    landmarks: dict[int, LandmarkInput],
    lm_type: int,
) -> Optional[LandmarkInput]:
    """Retorna landmark pelo tipo, ou None se não presente / visibilidade baixa."""
    lm = landmarks.get(lm_type)
    if lm is None or lm.visibility <= MIN_VISIBILITY:
        return None
    return lm


# ── Cálculo geométrico base ────────────────────────────────────────────────────

def calculate_angle(
    a: LandmarkInput,
    b: LandmarkInput,
    c: LandmarkInput,
) -> float:
    """
    Calcula o ângulo (em graus) no ponto B entre os segmentos BA e BC.
    Porta direta de AngleCalculator.calculateAngle(PointF, PointF, PointF).

    Usa coordenadas 2D (x, y) normalizadas 0–1.
    Retorna valor no intervalo [0, 180].
    """
    bax = a.x - b.x
    bay = a.y - b.y
    bcx = c.x - b.x
    bcy = c.y - b.y

    dot    = bax * bcx + bay * bcy
    mag_ba = math.sqrt(bax ** 2 + bay ** 2)
    mag_bc = math.sqrt(bcx ** 2 + bcy ** 2)

    if mag_ba < 1e-6 or mag_bc < 1e-6:
        return 180.0  # Degenerado — landmarks coincidentes

    cos_angle = dot / (mag_ba * mag_bc)
    cos_angle = max(-1.0, min(1.0, cos_angle))   # clamp para evitar erros de acos
    return round(math.degrees(math.acos(cos_angle)), 2)


# ── API pública ────────────────────────────────────────────────────────────────

def calculate_joint_angles(
    landmarks_list: list[LandmarkInput],
    orientation=None,         # Optional[OrientationResult] — importado lazy
) -> JointAngles:
    """
    Calcula todos os ângulos articulares relevantes para análise de exercícios.

    Args:
        landmarks_list: lista de landmarks do MoveNet/ML Kit.
        orientation:    OrientationResult detectado pelo tf_serving_client.
                        Se None, detecta automaticamente (retrocompatibilidade).

    A estratégia de seleção de landmarks varia por orientação:
      LATERAL  → usa o lado visível (comportamento da versão original)
      FRONTAL  → calcula left/right separados; back_angle usa geometria frontal
      ANGLED   → blend dos dois modos via frontal_weight
    """
    lm: dict[int, LandmarkInput] = {lm.landmark_type: lm for lm in landmarks_list}

    # Resolve orientação (importa lazily para evitar dependência circular nos testes)
    if orientation is None:
        try:
            from orientation_detector import detect_orientation
            orientation = detect_orientation(landmarks_list)
        except ImportError:
            orientation = None

    # Extrai o frontal_weight (0=lateral puro, 1=frontal puro)
    # Se não há orientação, cai no modo lateral original (fw=0)
    fw: float = getattr(orientation, 'frontal_weight', 0.0) if orientation else 0.0
    visible_side: str = getattr(orientation, 'visible_side', 'left') if orientation else 'left'

    # ── Decide quais landmarks usar por orientação ─────────────────────────────
    # Para fw < 0.35 → LATERAL  (usa apenas lado visível)
    # Para fw > 0.65 → FRONTAL  (usa ambos separados)
    # 0.35 ≤ fw ≤ 0.65 → ANGLED (blend ponderado)

    if fw <= 0.35:
        # Modo LATERAL — comportamento original
        return _angles_lateral(lm, visible_side)

    elif fw >= 0.65:
        # Modo FRONTAL — calcula ambos os lados separadamente
        return _angles_frontal(lm)

    else:
        # Modo ANGLED — interpola entre lateral e frontal
        return _angles_angled(lm, visible_side, fw)


# ── Modo LATERAL (comportamento original) ─────────────────────────────────────

def _angles_lateral(
    lm: dict[int, LandmarkInput],
    visible_side: str,
) -> JointAngles:
    """
    Calcula ângulos para câmera lateral.
    Idêntico à lógica original de calculate_joint_angles().
    Usa o lado com melhor visibilidade; tenta o outro como fallback.
    """
    # Define preferência de lado
    if visible_side == "right":
        primary   = (RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE, RIGHT_HEEL,
                     RIGHT_FOOT_INDEX, RIGHT_SHOULDER)
        secondary = (LEFT_HIP,  LEFT_KNEE,  LEFT_ANKLE,  LEFT_HEEL,
                     LEFT_FOOT_INDEX,  LEFT_SHOULDER)
    else:
        primary   = (LEFT_HIP, LEFT_KNEE, LEFT_ANKLE, LEFT_HEEL,
                     LEFT_FOOT_INDEX,  LEFT_SHOULDER)
        secondary = (RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE, RIGHT_HEEL,
                     RIGHT_FOOT_INDEX, RIGHT_SHOULDER)

    p_hip, p_knee, p_ankle, p_heel, p_foot, p_sh = primary
    s_hip, s_knee, s_ankle, s_heel, s_foot, s_sh = secondary

    def g(idx: int) -> Optional[LandmarkInput]:
        return _get(lm, idx)

    # ── Joelhos ───────────────────────────────────────────────────────────────
    left_knee_angle  = None
    right_knee_angle = None

    # Calcula ambos os lados para compatibilidade com o analyzer
    l_hip   = g(LEFT_HIP);   l_knee = g(LEFT_KNEE);   l_ankle = g(LEFT_ANKLE)
    r_hip   = g(RIGHT_HIP);  r_knee = g(RIGHT_KNEE);  r_ankle = g(RIGHT_ANKLE)
    l_sh    = g(LEFT_SHOULDER); r_sh = g(RIGHT_SHOULDER)
    l_foot  = g(LEFT_FOOT_INDEX); r_foot = g(RIGHT_FOOT_INDEX)

    if l_hip and l_knee and l_ankle:
        left_knee_angle  = calculate_angle(l_hip, l_knee, l_ankle)
    if r_hip and r_knee and r_ankle:
        right_knee_angle = calculate_angle(r_hip, r_knee, r_ankle)

    # ── Quadril ───────────────────────────────────────────────────────────────
    left_hip_angle  = None
    right_hip_angle = None
    if l_sh and l_hip and l_knee:
        left_hip_angle  = calculate_angle(l_sh, l_hip, l_knee)
    if r_sh and r_hip and r_knee:
        right_hip_angle = calculate_angle(r_sh, r_hip, r_knee)

    # ── Tornozelos ────────────────────────────────────────────────────────────
    left_ankle_angle  = None
    right_ankle_angle = None
    if l_knee and l_ankle and l_foot:
        left_ankle_angle  = calculate_angle(l_knee, l_ankle, l_foot)
    if r_knee and r_ankle and r_foot:
        right_ankle_angle = calculate_angle(r_knee, r_ankle, r_foot)

    # ── Back angle (desvio do tronco em relação à vertical) ───────────────────
    back_angle = None
    # Usa o lado com melhor visibilidade (prioriza o visível)
    _sh  = g(p_sh)
    _hip = g(p_hip)
    if _sh and _hip:
        dy = _hip.y - _sh.y
        dx = _hip.x - _sh.x
        back_angle = round(math.degrees(math.atan2(abs(dx), abs(dy))), 2)
    else:
        _sh2  = g(s_sh)
        _hip2 = g(s_hip)
        if _sh2 and _hip2:
            dy = _hip2.y - _sh2.y
            dx = _hip2.x - _sh2.x
            back_angle = round(math.degrees(math.atan2(abs(dx), abs(dy))), 2)

    # ── Hip hinge angle ───────────────────────────────────────────────────────
    hip_hinge_angle = None
    _knee = g(p_knee)
    _shp  = g(p_sh)
    _hipv = g(p_hip)
    if _shp and _hipv and _knee:
        hip_hinge_angle = calculate_angle(_shp, _hipv, _knee)
    else:
        _knee2 = g(s_knee)
        _sh2   = g(s_sh)
        _hip2  = g(s_hip)
        if _sh2 and _hip2 and _knee2:
            hip_hinge_angle = calculate_angle(_sh2, _hip2, _knee2)

    return JointAngles(
        left_knee=left_knee_angle,
        right_knee=right_knee_angle,
        left_hip=left_hip_angle,
        right_hip=right_hip_angle,
        left_ankle=left_ankle_angle,
        right_ankle=right_ankle_angle,
        back_angle=back_angle,
        hip_hinge_angle=hip_hinge_angle,
    )


# ── Modo FRONTAL ──────────────────────────────────────────────────────────────

def _angles_frontal(lm: dict[int, LandmarkInput]) -> JointAngles:
    """
    Calcula ângulos para câmera frontal.

    Câmera frontal oferece visão clara da simetria lateral (knee cave, varo/valgo)
    mas perde a informação de profundidade sagital (joelho sobre o pé).

    Estratégia:
      - Joelhos/quadris/tornozelos: calcula ambos os lados separadamente.
      - Back angle: usa a inclinação lateral do tronco (desvio de simetria
        entre ombros e quadris — frontal é o ângulo mais informativo para
        detectar inclinação lateral do tronco).
      - Hip hinge: usando a diferença vertical entre ombros e quadris
        (câmera frontal vê a flexão do tronco como aproximação das y's).
    """
    def g(idx: int) -> Optional[LandmarkInput]:
        return _get(lm, idx)

    l_sh  = g(LEFT_SHOULDER);  r_sh  = g(RIGHT_SHOULDER)
    l_hip = g(LEFT_HIP);       r_hip = g(RIGHT_HIP)
    l_knee = g(LEFT_KNEE);     r_knee = g(RIGHT_KNEE)
    l_ankle = g(LEFT_ANKLE);   r_ankle = g(RIGHT_ANKLE)
    l_foot = g(LEFT_FOOT_INDEX); r_foot = g(RIGHT_FOOT_INDEX)

    # ── Joelhos (ambos calculados) ─────────────────────────────────────────
    left_knee_angle  = None
    right_knee_angle = None
    if l_hip and l_knee and l_ankle:
        left_knee_angle  = calculate_angle(l_hip, l_knee, l_ankle)
    if r_hip and r_knee and r_ankle:
        right_knee_angle = calculate_angle(r_hip, r_knee, r_ankle)

    # ── Quadril ────────────────────────────────────────────────────────────
    left_hip_angle  = None
    right_hip_angle = None
    if l_sh and l_hip and l_knee:
        left_hip_angle  = calculate_angle(l_sh, l_hip, l_knee)
    if r_sh and r_hip and r_knee:
        right_hip_angle = calculate_angle(r_sh, r_hip, r_knee)

    # ── Tornozelos ─────────────────────────────────────────────────────────
    left_ankle_angle  = None
    right_ankle_angle = None
    if l_knee and l_ankle and l_foot:
        left_ankle_angle  = calculate_angle(l_knee, l_ankle, l_foot)
    if r_knee and r_ankle and r_foot:
        right_ankle_angle = calculate_angle(r_knee, r_ankle, r_foot)

    # ── Back angle (frontal) ───────────────────────────────────────────────
    # Na câmera frontal, o back_angle é a inclinação lateral do tronco
    # (ombros não horizontais → tronco inclinado lateralmente).
    # Calculado como ângulo da linha ombro-quadril em relação à vertical.
    back_angle = _frontal_back_angle(l_sh, r_sh, l_hip, r_hip)

    # ── Hip hinge (frontal) ────────────────────────────────────────────────
    # Na câmera frontal, a flexão do quadril aparece como redução da distância
    # vertical entre ombros e quadris. Usa a média dos dois lados.
    hip_hinge_angle = None
    angles = []
    if l_sh and l_hip and l_knee:
        angles.append(calculate_angle(l_sh, l_hip, l_knee))
    if r_sh and r_hip and r_knee:
        angles.append(calculate_angle(r_sh, r_hip, r_knee))
    if angles:
        hip_hinge_angle = round(sum(angles) / len(angles), 2)

    return JointAngles(
        left_knee=left_knee_angle,
        right_knee=right_knee_angle,
        left_hip=left_hip_angle,
        right_hip=right_hip_angle,
        left_ankle=left_ankle_angle,
        right_ankle=right_ankle_angle,
        back_angle=back_angle,
        hip_hinge_angle=hip_hinge_angle,
    )


def _frontal_back_angle(
    l_sh: Optional[LandmarkInput],
    r_sh: Optional[LandmarkInput],
    l_hip: Optional[LandmarkInput],
    r_hip: Optional[LandmarkInput],
) -> Optional[float]:
    """
    Calcula o back_angle para câmera frontal.

    Usa o centróide dos ombros e o centróide dos quadris para calcular
    a inclinação lateral do tronco (desvio em relação à vertical).

    Se apenas um lado está disponível, usa o lado disponível.
    """
    # Centróide dos ombros
    if l_sh and r_sh:
        sh_x = (l_sh.x + r_sh.x) / 2.0
        sh_y = (l_sh.y + r_sh.y) / 2.0
    elif l_sh:
        sh_x, sh_y = l_sh.x, l_sh.y
    elif r_sh:
        sh_x, sh_y = r_sh.x, r_sh.y
    else:
        return None

    # Centróide dos quadris
    if l_hip and r_hip:
        hip_x = (l_hip.x + r_hip.x) / 2.0
        hip_y = (l_hip.y + r_hip.y) / 2.0
    elif l_hip:
        hip_x, hip_y = l_hip.x, l_hip.y
    elif r_hip:
        hip_x, hip_y = r_hip.x, r_hip.y
    else:
        return None

    dy = hip_y - sh_y
    dx = hip_x - sh_x
    return round(math.degrees(math.atan2(abs(dx), abs(dy))), 2)


# ── Modo ANGLED (blend ponderado) ─────────────────────────────────────────────

def _angles_angled(
    lm: dict[int, LandmarkInput],
    visible_side: str,
    frontal_weight: float,
) -> JointAngles:
    """
    Calcula ângulos para câmera em ângulo diagonal (~45°).

    Interpola linearmente entre os resultados do modo LATERAL e FRONTAL
    usando frontal_weight como coeficiente.

    frontal_weight = 0.35 → quase lateral
    frontal_weight = 0.65 → quase frontal
    frontal_weight = 0.5  → blend exato 50/50
    """
    lat   = _angles_lateral(lm, visible_side)
    front = _angles_frontal(lm)

    def blend(v_lat: Optional[float], v_front: Optional[float]) -> Optional[float]:
        """Interpola dois ângulos opcionais."""
        if v_lat is None and v_front is None:
            return None
        if v_lat is None:
            return v_front
        if v_front is None:
            return v_lat
        w_lat   = 1.0 - frontal_weight
        w_front = frontal_weight
        return round(w_lat * v_lat + w_front * v_front, 2)

    return JointAngles(
        left_knee       = blend(lat.left_knee,       front.left_knee),
        right_knee      = blend(lat.right_knee,      front.right_knee),
        left_hip        = blend(lat.left_hip,        front.left_hip),
        right_hip       = blend(lat.right_hip,       front.right_hip),
        left_ankle      = blend(lat.left_ankle,      front.left_ankle),
        right_ankle     = blend(lat.right_ankle,     front.right_ankle),
        back_angle      = blend(lat.back_angle,      front.back_angle),
        hip_hinge_angle = blend(lat.hip_hinge_angle, front.hip_hinge_angle),
    )
