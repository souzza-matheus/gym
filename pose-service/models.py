from pydantic import BaseModel, Field
from typing import Optional
from enum import IntEnum, Enum


# ── Landmarks ─────────────────────────────────────────────────────────────────

class LandmarkType(IntEnum):
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


class Landmark(BaseModel):
    landmark_type: int
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    z: float = Field(default=0.0)
    visibility: float = Field(..., ge=0.0, le=1.0)


# alias para angle_calculator/exercise_analyzer que importam LandmarkInput
LandmarkInput = Landmark


# ── Exercise Analyzer enums ───────────────────────────────────────────────────

class ExerciseType(str, Enum):
    SQUAT = "SQUAT"
    DEADLIFT = "DEADLIFT"
    LUNGE = "LUNGE"
    BENCH_PRESS = "BENCH_PRESS"
    BENT_OVER_ROW = "BENT_OVER_ROW"
    UNKNOWN = "UNKNOWN"


class MovementPhase(str, Enum):
    STANDING = "STANDING"
    DESCENDING = "DESCENDING"
    BOTTOM = "BOTTOM"
    ASCENDING = "ASCENDING"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ErrorType(str, Enum):
    KNEE_CAVE_LEFT = "KNEE_CAVE_LEFT"
    KNEE_CAVE_RIGHT = "KNEE_CAVE_RIGHT"
    KNEE_OVER_TOE_LEFT = "KNEE_OVER_TOE_LEFT"
    KNEE_OVER_TOE_RIGHT = "KNEE_OVER_TOE_RIGHT"
    BACK_NOT_STRAIGHT = "BACK_NOT_STRAIGHT"
    DEPTH_INSUFFICIENT = "DEPTH_INSUFFICIENT"
    HEELS_OFF_GROUND = "HEELS_OFF_GROUND"
    BACK_ROUNDED = "BACK_ROUNDED"
    HIPS_TOO_HIGH = "HIPS_TOO_HIGH"
    BAR_PATH_DRIFT = "BAR_PATH_DRIFT"
    ELBOW_FLARE = "ELBOW_FLARE"
    ELBOW_INSUFFICIENT_RANGE = "ELBOW_INSUFFICIENT_RANGE"
    WRIST_BENT = "WRIST_BENT"
    ROW_INCOMPLETE = "ROW_INCOMPLETE"
    LANDMARK_MISSING = "LANDMARK_MISSING"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


# ── Analyzer schemas ──────────────────────────────────────────────────────────

class JointAngles(BaseModel):
    left_knee: Optional[float] = None
    right_knee: Optional[float] = None
    left_hip: Optional[float] = None
    right_hip: Optional[float] = None
    left_ankle: Optional[float] = None
    right_ankle: Optional[float] = None
    back_angle: Optional[float] = None
    hip_hinge_angle: Optional[float] = None


class DetectedError(BaseModel):
    error_type: ErrorType
    risk_level: RiskLevel
    description: str
    joint_angle: Optional[float] = None
    threshold_violated: Optional[float] = None


class ExerciseAnalysis(BaseModel):
    """Resultado da análise embutido na resposta do Pose Service."""
    exercise_type: ExerciseType
    phase: MovementPhase
    score: float = Field(..., ge=0.0, le=100.0)
    joint_angles: JointAngles
    errors: list[DetectedError] = Field(default_factory=list)
    has_alert: bool = False
    analysis_ms: float


# ── Request / Response ────────────────────────────────────────────────────────

class PoseAnalysisResponse(BaseModel):
    # Pose
    landmarks: list[Landmark]
    landmark_count: int
    inference_ms: float
    frame_width: int
    frame_height: int
    model: str = "movenet_thunder"
    # Analyzer (presente quando exercise_type foi informado)
    analysis: Optional[ExerciseAnalysis] = None


class HealthResponse(BaseModel):
    status: str
    service: str = "pose-service"
    version: str = "1.0.0"
    model_loaded: bool
    tf_serving_connected: bool
