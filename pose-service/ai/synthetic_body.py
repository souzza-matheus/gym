"""
ai/synthetic_body.py — gerador procedural de landmarks sintéticos
====================================================================
Constrói listas de Landmark (formato MoveNet/MediaPipe, 33 pontos,
coordenadas normalizadas 0-1) a partir de alvos biomecânicos diretos
(ângulo de joelho, inclinação de tronco, % de colapso de joelho, etc.).

Em vez de simular física de corpo completo, cada landmark é posicionado
via geometria inversa para satisfazer exatamente os valores-alvo que o
angle_calculator.py / orientation_detector.py reais vão recalcular —
garantindo que o dataset sintético seja consistente com o que o modelo
verá em produção (mesma matemática, "ground truth" construída pela
geometria, não estimada).
"""

import math
import random
from dataclasses import dataclass

from models import Landmark

NOSE = 0
LEFT_EAR, RIGHT_EAR = 7, 8
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_ELBOW, RIGHT_ELBOW = 13, 14
LEFT_WRIST, RIGHT_WRIST = 15, 16
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26
LEFT_ANKLE, RIGHT_ANKLE = 27, 28
LEFT_HEEL, RIGHT_HEEL = 29, 30
LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX = 31, 32


@dataclass
class BodyWidths:
    shoulder_half: float
    hip_half: float
    ear_vis_left: float
    ear_vis_right: float
    nose_offset: float


# Larguras corporais aparentes na imagem variam com a orientação da câmera:
# de perfil o corpo "achata" no eixo X; de frente, a largura total aparece.
ORIENTATION_PROFILES: dict[str, "tuple[float, float]"] = {
    "LATERAL": (0.005, 0.025),
    "ANGLED": (0.045, 0.065),
    "FRONTAL": (0.075, 0.105),
}


def _rotate(vx: float, vy: float, theta_deg: float) -> tuple[float, float]:
    t = math.radians(theta_deg)
    c, s = math.cos(t), math.sin(t)
    return vx * c - vy * s, vx * s + vy * c


def _knee_from_hip_ankle(ankle_x, ankle_y, knee_x, knee_y, knee_angle_deg, thigh_len, prefer="min_y"):
    """
    Posiciona o quadril tal que angle(hip, knee, ankle) == knee_angle_deg.

    O ângulo entre dois segmentos de comprimento fixo admite duas soluções
    (rotação para um lado ou para o outro a partir do segmento joelho-
    tornozelo). `prefer` escolhe qual delas usar:
      "min_y"  — a que fica mais "para cima" (correto para quadril/perna:
                 uma pessoa de pé/agachando tem o quadril acima do joelho).
      "min_dx" — a mais próxima em X do ponto de referência (correto para
                 pulso/cotovelo: por padrão um antebraço neutro fica
                 alinhado verticalmente com o cotovelo, sem desvio lateral
                 — esse desvio deve vir só de wrist_extra_dev, não da
                 geometria da flexão do cotovelo).
    """
    vkx, vky = ankle_x - knee_x, ankle_y - knee_y
    mag = math.hypot(vkx, vky) or 1e-6
    vkx, vky = vkx / mag, vky / mag

    candidates = []
    for sign in (1.0, -1.0):
        dx, dy = _rotate(vkx, vky, sign * knee_angle_deg)
        candidates.append((knee_x + dx * thigh_len, knee_y + dy * thigh_len))

    if prefer == "min_dx":
        candidates.sort(key=lambda p: abs(p[0] - knee_x))
    else:
        candidates.sort(key=lambda p: p[1])
    return candidates[0]


def _lm(idx, x, y, z=0.0, vis=0.9) -> Landmark:
    return Landmark(landmark_type=idx, x=max(0.0, min(1.0, x)), y=max(0.0, min(1.0, y)),
                     z=z, visibility=max(0.0, min(1.0, vis)))


def build_frame(
    orientation_bucket: str,
    knee_angle: float,
    back_angle: float,
    knee_cave_pct_left: float = 0.0,
    knee_cave_pct_right: float = 0.0,
    knee_over_toe_left: float = 0.0,
    knee_over_toe_right: float = 0.0,
    elbow_flare_pct: float = 0.0,
    elbow_flare_angle_lateral: float = 10.0,
    arm_angle_left: float = 90.0,
    arm_angle_right: float = 90.0,
    wrist_extra_dev_left: float = 0.0,
    wrist_extra_dev_right: float = 0.0,
    noise_sigma: float = 0.01,
    knee_angle_left: float = None,
    knee_angle_right: float = None,
    stance_offset_right: float = 0.0,
) -> list[Landmark]:
    """
    Constrói um frame completo (33 landmarks) que satisfaz os alvos
    biomecânicos passados, prontos para alimentar calculate_joint_angles()
    e o motor de regras (usado como professor para gerar rótulos).
    """
    shoulder_half, hip_half = ORIENTATION_PROFILES[orientation_bucket]
    shoulder_half *= random.uniform(0.85, 1.15)
    hip_half *= random.uniform(0.85, 1.15)

    torso_len = random.uniform(0.24, 0.30)
    thigh_len = random.uniform(0.20, 0.24)
    shank_len = random.uniform(0.19, 0.23)
    upperarm_len = random.uniform(0.10, 0.14)
    forearm_len = random.uniform(0.10, 0.14)
    foot_forward = random.uniform(0.025, 0.045)

    # ── Pernas (esquerda/direita independentes para cave/over-toe) ──────────
    ankle_cx = 0.5 + random.uniform(-0.03, 0.03)
    ankle_y = random.uniform(0.86, 0.93)

    l_ankle_x = ankle_cx - hip_half
    r_ankle_x = ankle_cx + hip_half + stance_offset_right

    l_knee_x = l_ankle_x + knee_cave_pct_left / 100.0
    r_knee_x = r_ankle_x - knee_cave_pct_right / 100.0
    knee_y = ankle_y - shank_len

    l_foot_x = l_knee_x - knee_over_toe_left
    r_foot_x = r_knee_x - knee_over_toe_right

    knee_angle_l = knee_angle_left if knee_angle_left is not None else knee_angle
    knee_angle_r = knee_angle_right if knee_angle_right is not None else knee_angle
    l_hip_x, l_hip_y = _knee_from_hip_ankle(l_ankle_x, ankle_y, l_knee_x, knee_y, knee_angle_l, thigh_len)
    r_hip_x, r_hip_y = _knee_from_hip_ankle(r_ankle_x, ankle_y, r_knee_x, knee_y, knee_angle_r, thigh_len)

    hip_cx = (l_hip_x + r_hip_x) / 2.0
    hip_cy = (l_hip_y + r_hip_y) / 2.0

    # ── Tronco (back_angle exato via inversão de atan2) ──────────────────────
    # Usa seno/cosseno (não tangente) para que dx/dz fiquem limitados a
    # torso_len mesmo quando back_angle se aproxima de 90° (tronco quase
    # horizontal, caso do supino) — tan(theta) diverge perto de 90° e
    #"explodia" as coordenadas para fora de [0,1], colapsando ombros no
    # clamp e zerando shoulder_width.
    theta = math.radians(back_angle)
    dy = torso_len * math.cos(theta)
    dx = torso_len * math.sin(theta)
    dz = dx  # mesma magnitude: garante leitura consistente lateral E frontal

    sh_cx = hip_cx + dx
    sh_cy = hip_cy - dy
    sh_z = -dz

    l_sh_x, r_sh_x = sh_cx - shoulder_half, sh_cx + shoulder_half

    # ── Braços ────────────────────────────────────────────────────────────
    shoulder_width = 2 * shoulder_half
    elbow_width = shoulder_width * (1.0 + elbow_flare_pct / 100.0) if shoulder_width > 1e-6 else 0.0
    elbow_half = elbow_width / 2.0
    l_el_x, r_el_x = sh_cx - elbow_half, sh_cx + elbow_half
    el_y = sh_cy + upperarm_len
    el_dz = math.tan(math.radians(elbow_flare_angle_lateral)) * upperarm_len
    l_el_z = sh_z - el_dz
    r_el_z = sh_z - el_dz

    l_wr_x, l_wr_y = _knee_from_hip_ankle(sh_cx - shoulder_half, sh_cy, l_el_x, el_y, arm_angle_left, forearm_len, prefer="min_dx")
    r_wr_x, r_wr_y = _knee_from_hip_ankle(sh_cx + shoulder_half, sh_cy, r_el_x, el_y, arm_angle_right, forearm_len, prefer="min_dx")
    l_wr_x += wrist_extra_dev_left
    r_wr_x += wrist_extra_dev_right

    # ── Cabeça (orelhas/nariz controlam a detecção de orientação) ───────────
    if orientation_bucket == "LATERAL":
        ear_l, ear_r = random.uniform(0.75, 0.92), random.uniform(0.0, 0.15)
        nose_x = l_sh_x - 0.10
    elif orientation_bucket == "FRONTAL":
        ear_l, ear_r = random.uniform(0.7, 0.9), random.uniform(0.7, 0.9)
        nose_x = sh_cx
    else:  # ANGLED
        ear_l, ear_r = random.uniform(0.55, 0.75), random.uniform(0.25, 0.45)
        nose_x = sh_cx - 0.04
    nose_y = sh_cy - 0.06

    pts = {
        NOSE: (nose_x, nose_y, 0.0, 0.85),
        LEFT_EAR: (l_sh_x - 0.02, nose_y - 0.01, 0.0, ear_l),
        RIGHT_EAR: (r_sh_x + 0.02, nose_y - 0.01, 0.0, ear_r),
        LEFT_SHOULDER: (l_sh_x, sh_cy, sh_z, 0.9),
        RIGHT_SHOULDER: (r_sh_x, sh_cy, sh_z, 0.9),
        LEFT_ELBOW: (l_el_x, el_y, l_el_z, 0.85),
        RIGHT_ELBOW: (r_el_x, el_y, r_el_z, 0.85),
        LEFT_WRIST: (l_wr_x, l_wr_y, l_el_z, 0.8),
        RIGHT_WRIST: (r_wr_x, r_wr_y, r_el_z, 0.8),
        LEFT_HIP: (l_hip_x, l_hip_y, 0.0, 0.9),
        RIGHT_HIP: (r_hip_x, r_hip_y, 0.0, 0.9),
        LEFT_KNEE: (l_knee_x, knee_y, 0.0, 0.88),
        RIGHT_KNEE: (r_knee_x, knee_y, 0.0, 0.88),
        LEFT_ANKLE: (l_ankle_x, ankle_y, 0.0, 0.85),
        RIGHT_ANKLE: (r_ankle_x, ankle_y, 0.0, 0.85),
        LEFT_HEEL: (l_ankle_x - 0.01, ankle_y + 0.02, 0.0, 0.7),
        RIGHT_HEEL: (r_ankle_x + 0.01, ankle_y + 0.02, 0.0, 0.7),
        LEFT_FOOT_INDEX: (l_foot_x, ankle_y + 0.03, 0.0, 0.7),
        RIGHT_FOOT_INDEX: (r_foot_x, ankle_y + 0.03, 0.0, 0.7),
    }

    landmarks = []
    for idx, (x, y, z, vis) in pts.items():
        x += random.gauss(0, noise_sigma)
        y += random.gauss(0, noise_sigma)
        z += random.gauss(0, noise_sigma * 0.5)
        landmarks.append(_lm(idx, x, y, z, vis))

    return landmarks
