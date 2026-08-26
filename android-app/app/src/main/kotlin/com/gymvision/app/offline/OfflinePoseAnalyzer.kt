package com.gymvision.app.offline

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.pose.Pose
import com.google.mlkit.vision.pose.PoseDetection
import com.google.mlkit.vision.pose.PoseLandmark
import com.google.mlkit.vision.pose.accurate.AccuratePoseDetectorOptions
import com.gymvision.app.model.DetectedError
import com.gymvision.app.model.Landmark
import kotlinx.coroutines.tasks.await
import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.atan2
import kotlin.math.sqrt

/**
 * Detecção e análise de pose on-device usando ML Kit BlazePose (33 landmarks).
 *
 * Fluxo:
 *   1. Detecta landmarks via [PoseDetector] (TFLite no dispositivo, sem internet)
 *   2. Normaliza coordenadas para [0,1]
 *   3. Calcula ângulos articulares (knee, back)
 *   4. Detecta fase (STANDING/BOTTOM/DESCENDING/ASCENDING)
 *   5. Roda análise local simplificada (squat, deadlift, lunge, bench, row)
 *
 * Resultado é compatível com [AnalysisUiState] do [CameraViewModel].
 */
class OfflinePoseAnalyzer {

    // STREAM_MODE: reutiliza contexto entre frames — otimizado para vídeo ao vivo
    private val detector = PoseDetection.getClient(
        AccuratePoseDetectorOptions.Builder()
            .setDetectorMode(AccuratePoseDetectorOptions.STREAM_MODE)
            .build()
    )

    data class LocalAnalysisResult(
        val landmarks:  List<Landmark>,
        val phase:      String,
        val score:      Float,
        val errors:     List<DetectedError>,
        val hasAlert:   Boolean,
    )

    /** Processa um [Bitmap] e retorna resultado de análise local. */
    suspend fun analyze(bitmap: Bitmap, exerciseType: String): LocalAnalysisResult {
        val inputImage = InputImage.fromBitmap(bitmap, 0)
        val pose = detector.process(inputImage).await()

        if (pose.allPoseLandmarks.isEmpty()) {
            return LocalAnalysisResult(emptyList(), "UNKNOWN", 0f, emptyList(), false)
        }

        val w = bitmap.width.toFloat()
        val h = bitmap.height.toFloat()

        val landmarks = pose.allPoseLandmarks.map { lm ->
            Landmark(
                landmarkType = lm.landmarkType,
                x = (lm.position3D.x / w).coerceIn(0f, 1f),
                y = (lm.position3D.y / h).coerceIn(0f, 1f),
                z = lm.position3D.z / w,  // Z em mesma escala de X
                visibility = lm.inFrameLikelihood,
            )
        }

        val lmMap = landmarks.associateBy { it.landmarkType }

        val leftKneeAngle  = calcAngle(lmMap, HIP_L, KNEE_L, ANKLE_L)
        val rightKneeAngle = calcAngle(lmMap, HIP_R, KNEE_R, ANKLE_R)
        val kneeAngle = leftKneeAngle ?: rightKneeAngle

        val phase = detectPhase(kneeAngle)

        val errors = when (exerciseType.uppercase()) {
            "SQUAT"         -> analyzeSquat(lmMap, leftKneeAngle, rightKneeAngle, calcBackAngle(lmMap), phase)
            "DEADLIFT"      -> analyzeDeadlift(calcBackAngle(lmMap), calcHipAngle(lmMap), phase)
            "LUNGE"         -> analyzeLunge(leftKneeAngle, rightKneeAngle, calcBackAngle(lmMap), phase)
            "BENCH_PRESS"   -> analyzeBenchPress(lmMap)
            "BENT_OVER_ROW" -> analyzeRow(calcBackAngle(lmMap))
            else            -> emptyList()
        }

        val score = calculateScore(errors, phase)
        val hasAlert = errors.any { it.riskLevel == "MEDIUM" || it.riskLevel == "HIGH" }

        return LocalAnalysisResult(landmarks, phase, score, errors, hasAlert)
    }

    fun close() = detector.close()

    // ── Ângulos ──────────────────────────────────────────────────────────────

    private fun calcAngle(lm: Map<Int, Landmark>, a: Int, b: Int, c: Int): Float? {
        val pa = lm[a] ?: return null
        val pb = lm[b] ?: return null
        val pc = lm[c] ?: return null
        if (pa.visibility < 0.3f || pb.visibility < 0.3f || pc.visibility < 0.3f) return null

        val ax = pa.x - pb.x; val ay = pa.y - pb.y
        val cx = pc.x - pb.x; val cy = pc.y - pb.y
        val dot = ax * cx + ay * cy
        val mag = sqrt(ax * ax + ay * ay) * sqrt(cx * cx + cy * cy)
        if (mag < 1e-6f) return null
        return Math.toDegrees(acos((dot / mag).toDouble().coerceIn(-1.0, 1.0))).toFloat()
    }

    private fun calcBackAngle(lm: Map<Int, Landmark>): Float? {
        val sh = lm[SHOULDER_L] ?: lm[SHOULDER_R] ?: return null
        val hp = lm[HIP_L] ?: lm[HIP_R] ?: return null
        if (sh.visibility < 0.3f || hp.visibility < 0.3f) return null
        val dx = sh.x - hp.x; val dy = sh.y - hp.y
        return Math.toDegrees(atan2(abs(dx.toDouble()), abs(dy.toDouble()))).toFloat()
    }

    private fun calcHipAngle(lm: Map<Int, Landmark>): Float? =
        calcAngle(lm, SHOULDER_L, HIP_L, KNEE_L)
            ?: calcAngle(lm, SHOULDER_R, HIP_R, KNEE_R)

    // ── Fase ─────────────────────────────────────────────────────────────────

    private var _prevKneeAngle: Float? = null

    private fun detectPhase(kneeAngle: Float?): String {
        val angle = kneeAngle ?: return "UNKNOWN"
        val phase = when {
            angle > 160f -> "STANDING"
            angle < 90f  -> "BOTTOM"
            else -> {
                val prev = _prevKneeAngle
                if (prev == null) "DESCENDING"
                else if (angle > prev) "ASCENDING" else "DESCENDING"
            }
        }
        _prevKneeAngle = angle
        return phase
    }

    // ── Severidade exibida na UI (Aviso/Grave) ────────────────────────────────
    // Espelha _alert_severity() do exercise_analyzer.py: tipos de erro com
    // risco de lesão (joelho colapsando/passando do pé, lombar arredondada/
    // tronco caído) são sempre GRAVE ao disparar, independente do percentual;
    // os demais só escalam para GRAVE quando o RiskLevel já é HIGH.
    private val ALWAYS_CRITICAL_ERROR_TYPES = setOf(
        "KNEE_CAVE_LEFT", "KNEE_CAVE_RIGHT",
        "KNEE_OVER_TOE_LEFT", "KNEE_OVER_TOE_RIGHT",
        "BACK_NOT_STRAIGHT", "BACK_ROUNDED",
    )

    private fun severityFor(errorType: String, riskLevel: String): String =
        if (errorType in ALWAYS_CRITICAL_ERROR_TYPES || riskLevel == "HIGH") "CRITICAL" else "WARNING"

    // ── Análise simplificada (porta dos thresholds do exercise_analyzer.py) ──
    // Descrições não incluem métricas (%/graus) — esse dado é interno, só para
    // a lógica de threshold; a UI mostra apenas o motivo em linguagem simples.

    private fun analyzeSquat(
        lm: Map<Int, Landmark>,
        leftKnee: Float?, rightKnee: Float?,
        backAngle: Float?, phase: String,
    ): List<DetectedError> {
        val errors = mutableListOf<DetectedError>()

        // 1. Profundidade insuficiente
        if (phase == "BOTTOM") {
            val knee = leftKnee ?: rightKnee
            if (knee != null && knee > 90f) {
                errors += DetectedError("DEPTH_INSUFFICIENT", "LOW",
                    "Profundidade insuficiente — desça mais no agachamento",
                    severity = severityFor("DEPTH_INSUFFICIENT", "LOW"))
            }
        }

        // 2. Costas inclinadas
        if (backAngle != null && backAngle > 45f) {
            val risk = if (backAngle > 63f) "HIGH" else "MEDIUM"
            errors += DetectedError("BACK_NOT_STRAIGHT", risk,
                "Tronco muito inclinado para frente",
                severity = severityFor("BACK_NOT_STRAIGHT", risk))
        }

        // 3. Joelho caindo (câmera frontal — heurística simples)
        val lKnee  = lm[KNEE_L]; val lAnkle = lm[ANKLE_L]
        val rKnee  = lm[KNEE_R]; val rAnkle = lm[ANKLE_R]
        if (lKnee != null && lAnkle != null && (lKnee.x - lAnkle.x) * 100 > 4f) {
            errors += DetectedError("KNEE_CAVE_LEFT", "MEDIUM",
                "Joelho esquerdo colapsando para dentro",
                severity = severityFor("KNEE_CAVE_LEFT", "MEDIUM"))
        }
        if (rKnee != null && rAnkle != null && (rAnkle.x - rKnee.x) * 100 > 4f) {
            errors += DetectedError("KNEE_CAVE_RIGHT", "MEDIUM",
                "Joelho direito colapsando para dentro",
                severity = severityFor("KNEE_CAVE_RIGHT", "MEDIUM"))
        }

        return errors
    }

    private fun analyzeDeadlift(backAngle: Float?, hipAngle: Float?, phase: String): List<DetectedError> {
        val errors = mutableListOf<DetectedError>()
        if (phase in listOf("BOTTOM", "ASCENDING") && backAngle != null && backAngle > 30f) {
            val risk = if (backAngle > 45f) "HIGH" else "MEDIUM"
            errors += DetectedError("BACK_ROUNDED", risk,
                "Lombar arredondada — risco de lesão na coluna",
                severity = severityFor("BACK_ROUNDED", risk))
        }
        if (phase == "STANDING" && hipAngle != null && hipAngle < 160f) {
            errors += DetectedError("HIPS_TOO_HIGH", "LOW",
                "Quadril não totalmente estendido no topo do movimento",
                severity = severityFor("HIPS_TOO_HIGH", "LOW"))
        }
        return errors
    }

    private fun analyzeLunge(leftKnee: Float?, rightKnee: Float?, backAngle: Float?, phase: String): List<DetectedError> {
        val errors = mutableListOf<DetectedError>()
        if (phase == "BOTTOM") {
            val knee = leftKnee ?: rightKnee
            if (knee != null && (knee < 85f || knee > 100f)) {
                errors += DetectedError("DEPTH_INSUFFICIENT", "LOW",
                    "Ângulo do joelho frontal fora do ideal — ajuste a profundidade do passo",
                    severity = severityFor("DEPTH_INSUFFICIENT", "LOW"))
            }
        }
        if (backAngle != null && backAngle > 40f) {
            errors += DetectedError("BACK_NOT_STRAIGHT", "MEDIUM",
                "Tronco muito inclinado no avanço",
                severity = severityFor("BACK_NOT_STRAIGHT", "MEDIUM"))
        }
        return errors
    }

    private fun analyzeBenchPress(lm: Map<Int, Landmark>): List<DetectedError> {
        val errors = mutableListOf<DetectedError>()
        val lElbow = lm[ELBOW_L]; val lWrist = lm[WRIST_L]
        if (lElbow != null && lWrist != null && abs(lWrist.x - lElbow.x) > 0.04f) {
            errors += DetectedError("WRIST_BENT", "MEDIUM",
                "Pulso dobrado lateralmente — mantenha o pulso neutro",
                severity = severityFor("WRIST_BENT", "MEDIUM"))
        }
        return errors
    }

    private fun analyzeRow(backAngle: Float?): List<DetectedError> {
        val errors = mutableListOf<DetectedError>()
        if (backAngle != null && backAngle > 35f) {
            val risk = if (backAngle > 52f) "HIGH" else "MEDIUM"
            errors += DetectedError("BACK_ROUNDED", risk,
                "Lombar arredondada — risco de lesão na coluna",
                severity = severityFor("BACK_ROUNDED", risk))
        }
        return errors
    }

    private fun calculateScore(errors: List<DetectedError>, phase: String): Float {
        if (phase == "UNKNOWN") return 0f
        var score = 100f
        for (e in errors) score -= when (e.riskLevel) {
            "HIGH"   -> 25f
            "MEDIUM" -> 15f
            else     -> 5f
        }
        return score.coerceAtLeast(0f)
    }

    companion object {
        // MediaPipe BlazePose landmark indices (mesmo enum do backend)
        private const val SHOULDER_L = 11; private const val SHOULDER_R = 12
        private const val ELBOW_L    = 13; @Suppress("unused") private const val ELBOW_R = 14
        private const val WRIST_L    = 15; @Suppress("unused") private const val WRIST_R = 16
        private const val HIP_L      = 23; private const val HIP_R      = 24
        private const val KNEE_L     = 25; private const val KNEE_R     = 26
        private const val ANKLE_L    = 27; private const val ANKLE_R    = 28
    }
}
