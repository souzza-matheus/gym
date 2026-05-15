package com.gymvision.app.ui.camera

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.camera.core.ImageProxy
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.ExerciseAnalysis
import com.gymvision.app.model.PoseAnalysisResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream

data class AnalysisUiState(
    val isAnalyzing: Boolean = false,
    val score: Float = 0f,
    val phase: String = "–",
    val errors: List<String> = emptyList(),
    val hasAlert: Boolean = false,
    val landmarkCount: Int = 0,
    val frameSeq: Int = 0,
    val errorMessage: String? = null
)

class CameraViewModel : ViewModel() {

    private val _state = MutableStateFlow(AnalysisUiState())
    val state: StateFlow<AnalysisUiState> = _state

    private var frameCounter = 0
    private var analyzeJob: Job? = null

    // Throttle: processa 1 frame a cada 200ms (~5fps de análise)
    // para não sobrecarregar o servidor com 30fps da câmera
    private var lastAnalysisTime = 0L
    private val ANALYSIS_INTERVAL_MS = 200L

    fun onFrame(
        academyId: String = "",
        imageProxy: ImageProxy,
        exerciseType: String,
        sessionId: String,
        studentId: String
    ) {
        val now = System.currentTimeMillis()
        if (now - lastAnalysisTime < ANALYSIS_INTERVAL_MS) {
            imageProxy.close()
            return
        }
        lastAnalysisTime = now

        val bytes = imageProxy.toJpegBytes()
        imageProxy.close()

        if (bytes == null) return

        val seq = ++frameCounter

        analyzeJob?.cancel()
        analyzeJob = viewModelScope.launch(Dispatchers.IO) {
            _state.value = _state.value.copy(isAnalyzing = true, errorMessage = null)
            runCatching {
                val framePart = MultipartBody.Part.createFormData(
                    "frame", "frame.jpg",
                    bytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
                )
                val response = ApiClient.poseApi.analyze(
                    frame = framePart,
                    exerciseType = exerciseType.toRequestBody("text/plain".toMediaTypeOrNull()),
                    sessionId = sessionId.toRequestBody("text/plain".toMediaTypeOrNull()),
                    studentId = studentId.toRequestBody("text/plain".toMediaTypeOrNull()),
                    frameSeq = seq.toString().toRequestBody("text/plain".toMediaTypeOrNull()),
                    academyId = academyId.toRequestBody("text/plain".toMediaTypeOrNull())
                )

                if (response.isSuccessful) {
                    val body = response.body()!!
                    val analysis = body.analysis
                    _state.value = AnalysisUiState(
                        isAnalyzing = false,
                        score = analysis?.score ?: 0f,
                        phase = analysis?.phase ?: "–",
                        errors = analysis?.errors?.map { it.description } ?: emptyList(),
                        hasAlert = analysis?.hasAlert ?: false,
                        landmarkCount = body.landmarkCount,
                        frameSeq = seq
                    )
                } else {
                    _state.value = _state.value.copy(
                        isAnalyzing = false,
                        errorMessage = "Erro ${response.code()}"
                    )
                }
            }.onFailure { e ->
                _state.value = _state.value.copy(
                    isAnalyzing = false,
                    errorMessage = e.message
                )
            }
        }
    }

    private fun ImageProxy.toJpegBytes(): ByteArray? {
        return runCatching {
            val buffer = planes[0].buffer
            val bytes = ByteArray(buffer.remaining())
            buffer.get(bytes)
            // Converte para Bitmap para corrigir rotação, depois volta para JPEG
            val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return null
            val matrix = Matrix().apply { postRotate(imageInfo.rotationDegrees.toFloat()) }
            val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            ByteArrayOutputStream().use { out ->
                rotated.compress(Bitmap.CompressFormat.JPEG, 85, out)
                out.toByteArray()
            }
        }.getOrNull()
    }
}
// NOTE: academy_id is passed via the analyze call.
// Update onFrame() signature if needed in CameraFragment.
