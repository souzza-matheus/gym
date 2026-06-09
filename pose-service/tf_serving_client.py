"""
tf_serving_client.py — GymVision Pose Service
==============================================
Cliente gRPC para TF Serving / MoveNet Thunder.

Melhorias em relação à versão original:
  1. Normalização de resolução — aceita qualquer resolução de entrada e
     normaliza para 256×256 antes de enviar ao MoveNet (antes assumia 480×640).
  2. Detecção de orientação — após a inferência, detecta automaticamente se
     a câmera é LATERAL, FRONTAL ou ANGLED e anota o resultado nos metadados.
  3. Padding proporcional — mantém aspect ratio ao redimensionar para 256×256,
     adicionando padding preto nos eixos menores para não distorcer a pose.

O mapeamento MoveNet → ML Kit e a filtragem por confiança são mantidos
identicamente à versão original para preservar compatibilidade total com
exercise_analyzer.py e com os 30 testes de run_all_tests.py.
"""

import time
import logging
from typing import Optional

import numpy as np
import cv2
import grpc
import tensorflow as tf
from tensorflow_serving.apis import predict_pb2, prediction_service_pb2_grpc

from models import Landmark, LandmarkType
from config import settings
from orientation_detector import detect_orientation, OrientationResult, CameraOrientation

logger = logging.getLogger(__name__)

# ── Mapeamento MoveNet (17 keypoints COCO) → índices ML Kit (33 landmarks) ────
MOVENET_TO_MLKIT: dict[int, LandmarkType] = {
    0:  LandmarkType.NOSE,
    1:  LandmarkType.LEFT_EYE,
    2:  LandmarkType.RIGHT_EYE,
    3:  LandmarkType.LEFT_EAR,
    4:  LandmarkType.RIGHT_EAR,
    5:  LandmarkType.LEFT_SHOULDER,
    6:  LandmarkType.RIGHT_SHOULDER,
    7:  LandmarkType.LEFT_ELBOW,
    8:  LandmarkType.RIGHT_ELBOW,
    9:  LandmarkType.LEFT_WRIST,
    10: LandmarkType.RIGHT_WRIST,
    11: LandmarkType.LEFT_HIP,
    12: LandmarkType.RIGHT_HIP,
    13: LandmarkType.LEFT_KNEE,
    14: LandmarkType.RIGHT_KNEE,
    15: LandmarkType.LEFT_ANKLE,
    16: LandmarkType.RIGHT_ANKLE,
}

MIN_CONFIDENCE: float = 0.5
MOVENET_INPUT_SIZE: int = 256


class TFServingClient:
    """
    Cliente gRPC para TF Serving com pré-processamento adaptativo de resolução.
    Detecta orientação da câmera automaticamente após cada inferência.
    """

    def __init__(self):
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[prediction_service_pb2_grpc.PredictionServiceStub] = None
        self._connected: bool = False

    def connect(self) -> bool:
        try:
            self._channel = grpc.insecure_channel(
                f"{settings.tf_serving_host}:{settings.tf_serving_port}",
                options=[
                    ("grpc.max_send_message_length",    10 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 10 * 1024 * 1024),
                    ("grpc.keepalive_time_ms", 10_000),
                ]
            )
            self._stub = prediction_service_pb2_grpc.PredictionServiceStub(self._channel)
            grpc.channel_ready_future(self._channel).result(timeout=5)
            self._connected = True
            logger.info(
                f"TF Serving conectado em "
                f"{settings.tf_serving_host}:{settings.tf_serving_port}"
            )
            return True
        except Exception as e:
            logger.warning(f"TF Serving não disponível: {e}. Usando fallback on-device.")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def predict(
        self,
        frame_bytes: bytes,
    ) -> tuple[list[Landmark], float, Optional[OrientationResult]]:
        """
        Executa inferência de pose em um frame JPEG.

        Aceita qualquer resolução — normaliza para 256×256 mantendo
        aspect ratio (letterbox com padding preto).

        Returns:
            landmarks:    lista de Landmark com coordenadas normalizadas [0-1]
            inference_ms: latência da inferência em milissegundos
            orientation:  OrientationResult com orientação detectada
        """
        if not self._connected or self._stub is None:
            landmarks, ms = self._fallback_predict(frame_bytes)
            orientation = detect_orientation(landmarks) if landmarks else None
            return landmarks, ms, orientation

        # Decodifica frame (qualquer resolução)
        nparr = np.frombuffer(frame_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Frame inválido: não foi possível decodificar a imagem")

        original_h, original_w = img.shape[:2]

        # Pré-processa mantendo aspect ratio com letterbox
        img_rgb     = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_padded, pad_info = _letterbox(img_rgb, MOVENET_INPUT_SIZE)
        input_tensor = np.expand_dims(img_padded.astype(np.int32), axis=0)

        # Request gRPC
        request = predict_pb2.PredictRequest()
        request.model_spec.name            = settings.model_name
        request.model_spec.signature_name  = "serving_default"
        request.inputs["input"].CopyFrom(
            tf.make_tensor_proto(input_tensor, shape=input_tensor.shape)
        )

        t0           = time.perf_counter()
        response     = self._stub.Predict(request, timeout=2.0)
        inference_ms = (time.perf_counter() - t0) * 1000

        # Output: shape [1, 1, 17, 3] → (y, x, confidence)
        output_key = list(response.outputs.keys())[0]
        keypoints  = tf.make_ndarray(response.outputs[output_key])[0][0]

        landmarks   = self._keypoints_to_landmarks(keypoints, pad_info)
        orientation = detect_orientation(landmarks)

        logger.debug(
            f"Inferência: {inference_ms:.1f}ms | "
            f"resolução: {original_w}x{original_h} | "
            f"landmarks: {len(landmarks)} | "
            f"orientação: {orientation.orientation.value} "
            f"(fw={orientation.frontal_weight:.2f})"
        )

        return landmarks, inference_ms, orientation

    def _keypoints_to_landmarks(
        self,
        keypoints: np.ndarray,
        pad_info: "Optional[_PadInfo]" = None,
    ) -> list[Landmark]:
        """
        Converte 17 keypoints MoveNet para lista de Landmark.
        Filtra por MIN_CONFIDENCE (0.5 — espelha PoseDetectorProcessor.kt).
        Quando pad_info é fornecido, corrige coordenadas removendo letterbox offset.
        """
        landmarks: list[Landmark] = []

        for movenet_idx, mlkit_type in MOVENET_TO_MLKIT.items():
            y_norm, x_norm, confidence = keypoints[movenet_idx]

            if confidence < MIN_CONFIDENCE:
                continue

            if pad_info is not None:
                x_final = _unpad_coord(float(x_norm), pad_info.pad_left, pad_info.scale_w)
                y_final = _unpad_coord(float(y_norm), pad_info.pad_top,  pad_info.scale_h)
            else:
                x_final = float(x_norm)
                y_final = float(y_norm)

            landmarks.append(Landmark(
                landmark_type=int(mlkit_type),
                x=float(np.clip(x_final, 0.0, 1.0)),
                y=float(np.clip(y_final, 0.0, 1.0)),
                z=0.0,
                visibility=float(confidence),
            ))

        return landmarks

    def _fallback_predict(
        self,
        frame_bytes: bytes,
    ) -> tuple[list[Landmark], float]:
        """Fallback com MediaPipe Pose quando TF Serving não está disponível."""
        logger.warning("Usando fallback MediaPipe (sem TF Serving)")
        t0 = time.perf_counter()
        try:
            import mediapipe as mp

            nparr = np.frombuffer(frame_bytes, np.uint8)
            img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return [], (time.perf_counter() - t0) * 1000

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            with mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=1,
                min_detection_confidence=0.3,
                min_tracking_confidence=0.3,
            ) as pose:
                results = pose.process(img_rgb)

            if not results.pose_landmarks:
                logger.warning("MediaPipe não detectou landmarks na imagem.")
                return [], (time.perf_counter() - t0) * 1000

            landmarks: list[Landmark] = []
            for idx, lm in enumerate(results.pose_landmarks.landmark):
                if lm.visibility < 0.2:
                    continue
                landmarks.append(Landmark(
                    landmark_type=idx,
                    x=float(np.clip(lm.x, 0.0, 1.0)),
                    y=float(np.clip(lm.y, 0.0, 1.0)),
                    z=float(lm.z),
                    visibility=float(np.clip(lm.visibility, 0.0, 1.0)),
                ))

            logger.info(f"MediaPipe detectou {len(landmarks)} landmarks.")
            return landmarks, (time.perf_counter() - t0) * 1000

        except Exception as e:
            logger.error(f"Erro no fallback MediaPipe: {e}")
            return [], (time.perf_counter() - t0) * 1000

    def close(self):
        if self._channel:
            self._channel.close()
            self._connected = False


# ── Utilitários de pré/pós-processamento ─────────────────────────────────────

class _PadInfo:
    """Metadados do padding letterbox aplicado ao frame."""
    __slots__ = ("pad_top", "pad_left", "scale_w", "scale_h")

    def __init__(self, pad_top: float, pad_left: float,
                 scale_w: float, scale_h: float):
        self.pad_top  = pad_top
        self.pad_left = pad_left
        self.scale_w  = scale_w
        self.scale_h  = scale_h


def _letterbox(img: np.ndarray, target: int) -> tuple[np.ndarray, _PadInfo]:
    """
    Redimensiona img para target×target mantendo aspect ratio.
    Adiciona padding preto simétrico nos eixos que sobrarem.

    Returns:
        img_out:  array uint8 shape (target, target, 3)
        pad_info: frações de padding normalizadas para desfazer depois
    """
    h, w = img.shape[:2]

    # Escala uniforme que cabe no quadrado target×target
    scale = target / max(h, w)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))

    img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Centraliza no quadrado com padding simétrico
    pad_top  = (target - new_h) // 2
    pad_left = (target - new_w) // 2

    img_out = np.zeros((target, target, 3), dtype=np.uint8)
    img_out[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = img_resized

    return img_out, _PadInfo(
        pad_top=pad_top   / target,
        pad_left=pad_left / target,
        scale_w=new_w     / target,
        scale_h=new_h     / target,
    )


def _unpad_coord(coord_padded: float, pad_offset: float, scale: float) -> float:
    """
    Converte coordenada normalizada de espaço padded (256×256) para
    espaço normalizado original da imagem.
    """
    if scale < 1e-9:
        return coord_padded
    return (coord_padded - pad_offset) / scale


# Singleton compartilhado pela aplicação
tf_client = TFServingClient()
