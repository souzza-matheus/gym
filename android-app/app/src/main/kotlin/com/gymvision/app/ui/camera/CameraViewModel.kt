package com.gymvision.app.ui.camera

import android.app.Application
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.camera.core.ImageProxy
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.DetectedError
import com.gymvision.app.model.Landmark
import com.gymvision.app.offline.ConnectivityObserver
import com.gymvision.app.offline.LocalFrameStore
import com.gymvision.app.offline.OfflinePoseAnalyzer
import com.gymvision.app.offline.SyncWorker
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream

enum class AutoDetectPhase { DETECTING, CONFIRMING, CONFIRMED }

data class AnalysisUiState(
    val isAnalyzing: Boolean = false,
    val score: Float = 0f,
    val phase: String = "UNKNOWN",
    val errors: List<DetectedError> = emptyList(),
    val hasAlert: Boolean = false,
    val landmarks: List<Landmark> = emptyList(),
    val frameSeq: Int = 0,
    val repCount: Int = 0,
    val errorMessage: String? = null,
    val isOffline: Boolean = false,
    val pendingFrames: Int = 0,
    // Auto-detection
    val autoDetectPhase: AutoDetectPhase? = null,
    val detectedExercise: String? = null,
    val detectionConfidence: Float = 0f,
    val detectionProgress: Int = 0,  // frames coletados (0–10)
)

class CameraViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(AnalysisUiState())
    val state: StateFlow<AnalysisUiState> = _state

    private var frameCounter     = 0
    private var analyzeJob: Job? = null
    private var lastPhase        = "UNKNOWN"
    private var lastAnalysisTime = 0L
    private val analysisIntervalMs = 200L

    private val offlinePoseAnalyzer = OfflinePoseAnalyzer()
    private val frameStore = LocalFrameStore(application.applicationContext)

    // Auto-detection tracking
    private var activeExerciseType    = ""
    private val detectionVotes        = mutableMapOf<String, Float>()
    private var detectionFrameCount   = 0
    private var detectionRetries      = 0
    private val maxDetectionFrames    = 10
    private val maxDetectionRetries   = 3

    init {
        viewModelScope.launch {
            ConnectivityObserver.observe(application.applicationContext).collect { isOnline ->
                _state.value = _state.value.copy(
                    isOffline     = !isOnline,
                    pendingFrames = if (isOnline) _state.value.pendingFrames else frameStore.pendingCount(),
                )
                if (isOnline && frameStore.pendingCount() > 0) {
                    SyncWorker.schedule(application.applicationContext)
                }
            }
        }
    }

    fun onFrame(
        imageProxy: ImageProxy,
        exerciseType: String,
        sessionId: String,
        studentId: String,
        academyId: String = "",
    ) {
        // Inicializa tipo de exercício e fase de auto-detecção na primeira chamada
        if (activeExerciseType.isEmpty()) {
            activeExerciseType = exerciseType
            if (exerciseType == "AUTO") {
                _state.value = _state.value.copy(autoDetectPhase = AutoDetectPhase.DETECTING)
            }
        }

        val now = System.currentTimeMillis()
        if (now - lastAnalysisTime < analysisIntervalMs) {
            imageProxy.close()
            return
        }
        lastAnalysisTime = now

        val bitmap = imageProxyToBitmap(imageProxy)
        val bytes  = bitmap?.let { bitmapToJpeg(it, imageProxy.imageInfo.rotationDegrees) }
        imageProxy.close()

        val seq     = ++frameCounter
        val offline = _state.value.isOffline

        analyzeJob?.cancel()
        analyzeJob = viewModelScope.launch(
            if (activeExerciseType != "AUTO" && offline) Dispatchers.Default else Dispatchers.IO
        ) {
            _state.value = _state.value.copy(isAnalyzing = true, errorMessage = null)

            when {
                activeExerciseType == "AUTO" -> {
                    if (bytes != null) runAutoDetection(bytes, sessionId, studentId)
                    else _state.value = _state.value.copy(isAnalyzing = false)
                }
                offline -> {
                    if (bitmap != null)
                        onFrameOffline(bitmap, activeExerciseType, sessionId, studentId, academyId, seq)
                    else
                        _state.value = _state.value.copy(isAnalyzing = false)
                }
                else -> {
                    if (bytes != null)
                        onFrameOnline(bytes, activeExerciseType, sessionId, studentId, academyId, seq)
                    else
                        _state.value = _state.value.copy(isAnalyzing = false)
                }
            }
        }
    }

    // ── Auto-detecção ─────────────────────────────────────────────────────────

    private suspend fun runAutoDetection(bytes: ByteArray, sessionId: String, studentId: String) {
        if (detectionFrameCount >= maxDetectionFrames) {
            _state.value = _state.value.copy(isAnalyzing = false)
            return
        }

        detectionFrameCount++
        _state.value = _state.value.copy(
            isAnalyzing      = false,
            detectionProgress = detectionFrameCount,
        )

        runCatching {
            val framePart = MultipartBody.Part.createFormData(
                "frame", "frame.jpg",
                bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            )
            ApiClient.poseApi.detectExercise(
                frame     = framePart,
                sessionId = sessionId.toRequestBody("text/plain".toMediaTypeOrNull()),
                studentId = studentId.toRequestBody("text/plain".toMediaTypeOrNull()),
            )
        }.onSuccess { response ->
            val body = response.body()
            if (response.isSuccessful && body != null && body.exerciseType != "UNKNOWN") {
                val prev = detectionVotes.getOrDefault(body.exerciseType, 0f)
                detectionVotes[body.exerciseType] = prev + body.confidence
            }
        }

        if (detectionFrameCount >= maxDetectionFrames) {
            computeAutoDetectionResult()
        }
    }

    private fun computeAutoDetectionResult() {
        val totalConfidence = detectionVotes.values.sum()
        val best = detectionVotes.maxByOrNull { it.value }

        if (best != null && totalConfidence > 0) {
            val relativeConf = best.value / totalConfidence
            val avgConf      = best.value / maxDetectionFrames.toFloat()
            if (relativeConf >= 0.65f && avgConf >= 0.35f) {
                _state.value = _state.value.copy(
                    autoDetectPhase     = AutoDetectPhase.CONFIRMING,
                    detectedExercise    = best.key,
                    detectionConfidence = relativeConf,
                )
                return
            }
        }

        // Baixa confiança — tenta novamente ou força confirmação
        detectionRetries++
        if (detectionRetries >= maxDetectionRetries) {
            val fallback = best?.key ?: "SQUAT"
            _state.value = _state.value.copy(
                autoDetectPhase     = AutoDetectPhase.CONFIRMING,
                detectedExercise    = fallback,
                detectionConfidence = (detectionVotes[fallback] ?: 0f) / maxDetectionFrames,
            )
        } else {
            detectionVotes.clear()
            detectionFrameCount = 0
            _state.value = _state.value.copy(
                autoDetectPhase   = AutoDetectPhase.DETECTING,
                detectionProgress = 0,
            )
        }
    }

    /** Usuário confirmou o exercício detectado. */
    fun confirmDetection() {
        val detected = _state.value.detectedExercise ?: "SQUAT"
        activeExerciseType = detected
        detectionVotes.clear()
        detectionFrameCount = 0
        _state.value = _state.value.copy(autoDetectPhase = AutoDetectPhase.CONFIRMED)
    }

    /** Usuário escolheu manualmente outro exercício. */
    fun overrideExercise(exercise: String) {
        activeExerciseType = exercise
        detectionVotes.clear()
        detectionFrameCount = 0
        _state.value = _state.value.copy(
            autoDetectPhase     = null,
            detectedExercise    = null,
            detectionConfidence = 0f,
            detectionProgress   = 0,
        )
    }

    // ── Caminho online (envia para o servidor) ────────────────────────────────

    private suspend fun onFrameOnline(
        bytes: ByteArray,
        exerciseType: String,
        sessionId: String,
        studentId: String,
        academyId: String,
        seq: Int,
    ) {
        runCatching {
            val framePart = MultipartBody.Part.createFormData(
                "frame", "frame.jpg",
                bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            )
            ApiClient.poseApi.analyze(
                frame        = framePart,
                exerciseType = exerciseType.toRequestBody("text/plain".toMediaTypeOrNull()),
                sessionId    = sessionId.toRequestBody("text/plain".toMediaTypeOrNull()),
                studentId    = studentId.toRequestBody("text/plain".toMediaTypeOrNull()),
                frameSeq     = seq.toString().toRequestBody("text/plain".toMediaTypeOrNull()),
                academyId    = academyId.toRequestBody("text/plain".toMediaTypeOrNull())
            )
        }.onSuccess { response ->
            val body = response.body()
            if (response.isSuccessful && body != null) {
                val analysis    = body.analysis
                val newPhase    = analysis?.phase ?: _state.value.phase
                val newRepCount = if (lastPhase == "BOTTOM" && newPhase == "STANDING")
                    _state.value.repCount + 1 else _state.value.repCount
                lastPhase = newPhase
                _state.value = AnalysisUiState(
                    isAnalyzing   = false,
                    score         = analysis?.score ?: _state.value.score,
                    phase         = newPhase,
                    errors        = analysis?.errors ?: emptyList(),
                    hasAlert      = analysis?.hasAlert ?: false,
                    landmarks     = body.landmarks,
                    frameSeq      = seq,
                    repCount      = newRepCount,
                    isOffline     = false,
                    pendingFrames = frameStore.pendingCount(),
                    autoDetectPhase     = _state.value.autoDetectPhase,
                    detectedExercise    = _state.value.detectedExercise,
                    detectionConfidence = _state.value.detectionConfidence,
                )
            } else {
                _state.value = _state.value.copy(
                    isAnalyzing  = false,
                    errorMessage = "Erro ${response.code()}",
                )
            }
        }.onFailure { e ->
            _state.value = _state.value.copy(
                isAnalyzing  = false,
                errorMessage = e.message,
            )
        }
    }

    // ── Caminho offline (ML Kit on-device) ───────────────────────────────────

    private suspend fun onFrameOffline(
        bitmap: Bitmap?,
        exerciseType: String,
        sessionId: String,
        studentId: String,
        academyId: String,
        seq: Int,
    ) {
        if (bitmap == null) {
            _state.value = _state.value.copy(isAnalyzing = false)
            return
        }

        runCatching {
            offlinePoseAnalyzer.analyze(bitmap, exerciseType)
        }.onSuccess { result ->
            val newPhase    = result.phase
            val newRepCount = if (lastPhase == "BOTTOM" && newPhase == "STANDING")
                _state.value.repCount + 1 else _state.value.repCount
            lastPhase = newPhase

            frameStore.insert(LocalFrameStore.PendingFrame(
                sessionId    = sessionId,
                studentId    = studentId,
                academyId    = academyId,
                exerciseType = exerciseType,
                frameSeq     = seq,
                landmarks    = result.landmarks,
                score        = result.score,
                phase        = newPhase,
            ))

            _state.value = AnalysisUiState(
                isAnalyzing   = false,
                score         = result.score,
                phase         = newPhase,
                errors        = result.errors,
                hasAlert      = result.hasAlert,
                landmarks     = result.landmarks,
                frameSeq      = seq,
                repCount      = newRepCount,
                isOffline     = true,
                pendingFrames = frameStore.pendingCount(),
                autoDetectPhase     = _state.value.autoDetectPhase,
                detectedExercise    = _state.value.detectedExercise,
                detectionConfidence = _state.value.detectionConfidence,
            )
        }.onFailure { e ->
            _state.value = _state.value.copy(
                isAnalyzing  = false,
                errorMessage = "Offline: ${e.message}",
            )
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun imageProxyToBitmap(imageProxy: ImageProxy): Bitmap? = runCatching {
        val buffer = imageProxy.planes[0].buffer
        val bytes  = ByteArray(buffer.remaining())
        buffer.get(bytes)
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
    }.getOrNull()

    private fun bitmapToJpeg(bitmap: Bitmap, rotationDegrees: Int): ByteArray? = runCatching {
        val matrix  = Matrix().apply { postRotate(rotationDegrees.toFloat()) }
        val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        ByteArrayOutputStream().use { out ->
            rotated.compress(Bitmap.CompressFormat.JPEG, 85, out)
            out.toByteArray()
        }
    }.getOrNull()

    override fun onCleared() {
        super.onCleared()
        offlinePoseAnalyzer.close()
    }
}
