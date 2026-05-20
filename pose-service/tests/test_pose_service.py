"""
tests/test_pose_service.py

Testes unitários e de integração do Pose Service.
Espelham os thresholds e lógica do app Android:
  - MIN_CONFIDENCE = 0.5
  - Resolução 480x640
  - Mesmos landmark types do ML Kit
"""
import io
import numpy as np
import pytest
import cv2
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app
from models import Landmark, LandmarkType
from tf_serving_client import TFServingClient, MIN_CONFIDENCE, MOVENET_TO_MLKIT

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────
def make_blank_frame(w: int = 480, h: int = 640) -> bytes:
    """Gera um frame JPEG em branco para testes."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def make_landmark(ltype: int, x: float, y: float, confidence: float = 0.9) -> Landmark:
    return Landmark(landmark_type=ltype, x=x, y=y, z=0.0, visibility=confidence)


# ── Health ────────────────────────────────────────────────────────────────────
class TestHealth:
    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_schema(self):
        r = client.get("/health")
        body = r.json()
        assert "status" in body
        assert "model_loaded" in body
        assert "tf_serving_connected" in body


# ── Pose analyze endpoint ─────────────────────────────────────────────────────
class TestAnalyzeEndpoint:
    def test_empty_body_returns_422(self):
        r = client.post("/api/v1/pose/analyze")
        assert r.status_code == 422

    def test_invalid_content_type_returns_415(self):
        r = client.post(
            "/api/v1/pose/analyze",
            files={"frame": ("frame.txt", b"not an image", "text/plain")},
        )
        assert r.status_code == 415

    def test_valid_frame_returns_200(self):
        frame_bytes = make_blank_frame()
        with patch.object(TFServingClient, "predict", return_value=([], 25.0, None)):
            r = client.post(
                "/api/v1/pose/analyze",
                files={"frame": ("frame.jpg", frame_bytes, "image/jpeg")},
            )
        assert r.status_code == 200
        body = r.json()
        assert "landmarks" in body
        assert "inference_ms" in body
        assert body["frame_width"] == 480
        assert body["frame_height"] == 640

    def test_response_includes_landmark_count(self):
        landmarks = [
            make_landmark(LandmarkType.LEFT_KNEE, 0.4, 0.6),
            make_landmark(LandmarkType.RIGHT_KNEE, 0.6, 0.6),
        ]
        with patch.object(TFServingClient, "predict", return_value=(landmarks, 30.0, None)):
            r = client.post(
                "/api/v1/pose/analyze",
                files={"frame": ("f.jpg", make_blank_frame(), "image/jpeg")},
            )
        assert r.json()["landmark_count"] == 2

    def test_oversized_frame_returns_413(self):
        huge = b"x" * (11 * 1024 * 1024)
        r = client.post(
            "/api/v1/pose/analyze",
            files={"frame": ("big.jpg", huge, "image/jpeg")},
        )
        assert r.status_code == 413


# ── Landmark confidence filtering ─────────────────────────────────────────────
class TestConfidenceFilter:
    """
    Espelha o filtro MIN_CONFIDENCE do PoseDetectorProcessor.kt:
    landmarks com inFrameLikelihood < 0.5 são descartados.
    """

    def test_min_confidence_value(self):
        assert MIN_CONFIDENCE == 0.5

    def test_low_confidence_landmarks_filtered(self):
        keypoints = np.zeros((17, 3))
        # Apenas joelho esquerdo com confiança alta
        keypoints[13] = [0.6, 0.4, 0.95]   # left_knee — visível
        keypoints[14] = [0.6, 0.6, 0.2]    # right_knee — abaixo de 0.5, deve ser filtrado

        tf = TFServingClient()
        result = tf._keypoints_to_landmarks(keypoints)

        types_in_result = {l.landmark_type for l in result}
        assert LandmarkType.LEFT_KNEE in types_in_result
        assert LandmarkType.RIGHT_KNEE not in types_in_result

    def test_all_low_confidence_returns_empty(self):
        keypoints = np.zeros((17, 3))
        # Todos abaixo de 0.5
        for i in range(17):
            keypoints[i] = [0.5, 0.5, 0.1]

        tf = TFServingClient()
        result = tf._keypoints_to_landmarks(keypoints)
        assert result == []


# ── Landmark type mapping ──────────────────────────────────────────────────────
class TestLandmarkMapping:
    """
    Garante que o mapeamento MoveNet → ML Kit está correto.
    Crítico: ExerciseAnalyzer usa PoseLandmark.RIGHT_KNEE (26), LEFT_HIP (23), etc.
    """

    def test_hip_landmarks_mapped(self):
        assert LandmarkType.LEFT_HIP in MOVENET_TO_MLKIT.values()
        assert LandmarkType.RIGHT_HIP in MOVENET_TO_MLKIT.values()

    def test_knee_landmarks_mapped(self):
        assert LandmarkType.LEFT_KNEE in MOVENET_TO_MLKIT.values()
        assert LandmarkType.RIGHT_KNEE in MOVENET_TO_MLKIT.values()

    def test_ankle_landmarks_mapped(self):
        assert LandmarkType.LEFT_ANKLE in MOVENET_TO_MLKIT.values()
        assert LandmarkType.RIGHT_ANKLE in MOVENET_TO_MLKIT.values()

    def test_shoulder_landmarks_mapped(self):
        assert LandmarkType.LEFT_SHOULDER in MOVENET_TO_MLKIT.values()
        assert LandmarkType.RIGHT_SHOULDER in MOVENET_TO_MLKIT.values()

    def test_all_17_movenet_keypoints_have_mapping(self):
        assert len(MOVENET_TO_MLKIT) == 17

    def test_landmark_coordinates_normalized(self):
        keypoints = np.zeros((17, 3))
        keypoints[11] = [0.5, 0.5, 0.9]   # left_hip

        tf = TFServingClient()
        result = tf._keypoints_to_landmarks(keypoints)

        hip = next((l for l in result if l.landmark_type == LandmarkType.LEFT_HIP), None)
        assert hip is not None
        assert 0.0 <= hip.x <= 1.0
        assert 0.0 <= hip.y <= 1.0
