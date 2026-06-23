package com.gymvision.app.ui.videotest

import android.content.Context
import android.graphics.Bitmap
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.DetectedError
import com.gymvision.app.model.Landmark
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.File

data class FrameData(
    val timestampMs: Long,
    val landmarks: List<Landmark>,
    val score: Float,
    val phase: String,
    val errors: List<DetectedError>,
    val hasAlert: Boolean,
)

sealed class VideoTestState {
    object Idle : VideoTestState()
    data class Processing(val progress: Int, val total: Int) : VideoTestState()
    data class Ready(val videoUri: Uri, val frames: List<FrameData>) : VideoTestState()
    data class Error(val message: String) : VideoTestState()
}

data class SampleVideo(val assetName: String, val label: String, val exerciseType: String)

val SAMPLE_VIDEOS = listOf(
    SampleVideo("squat2.mp4", "Agachamento", "SQUAT"),
    SampleVideo("deadlift.mp4", "Levantamento Terra (1)", "DEADLIFT"),
    SampleVideo("deadlift2.mp4", "Levantamento Terra (2)", "DEADLIFT"),
    SampleVideo("lunge.mp4", "Avanço", "LUNGE"),
    SampleVideo("bench_press.mp4", "Supino (1)", "BENCH_PRESS"),
    SampleVideo("bench_press2.mp4", "Supino (2)", "BENCH_PRESS"),
    SampleVideo("bent_over_row.mp4", "Remada Curvada", "BENT_OVER_ROW"),
)

class VideoTestViewModel : ViewModel() {

    private val _state = MutableStateFlow<VideoTestState>(VideoTestState.Idle)
    val state: StateFlow<VideoTestState> = _state

    fun processSampleVideo(sample: SampleVideo, context: Context) {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val outFile = File(context.cacheDir, "sample_${sample.assetName}")
                if (!outFile.exists()) {
                    context.assets.open("test_videos/${sample.assetName}").use { input ->
                        outFile.outputStream().use { output -> input.copyTo(output) }
                    }
                }
                FileProvider.getUriForFile(
                    context, "${context.packageName}.fileprovider", outFile,
                )
            }.onSuccess { uri ->
                processVideo(uri, context, sample.exerciseType)
            }.onFailure { e ->
                _state.value = VideoTestState.Error(e.message ?: "Erro ao carregar vídeo de exemplo.")
            }
        }
    }

    fun processVideo(uri: Uri, context: Context, exerciseType: String) {
        viewModelScope.launch(Dispatchers.IO) {
            _state.value = VideoTestState.Processing(0, 1)

            runCatching {
                val retriever = MediaMetadataRetriever()
                retriever.setDataSource(context, uri)

                val durationMs = retriever
                    .extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                    ?.toLongOrNull() ?: 0L

                if (durationMs == 0L) {
                    _state.value = VideoTestState.Error("Não foi possível ler a duração do vídeo.")
                    retriever.release()
                    return@runCatching
                }

                val intervalMs = 200L
                val timestamps = (0 until durationMs step intervalMs).toList()
                val total = timestamps.size
                val frames = mutableListOf<FrameData>()
                val sessionId = "video-test-${System.currentTimeMillis()}"
                val academyId = ApiClient.getAcademyId() ?: "unknown"

                for ((idx, timestampMs) in timestamps.withIndex()) {
                    _state.value = VideoTestState.Processing(idx + 1, total)

                    val rawBitmap = retriever.getFrameAtTime(
                        timestampMs * 1_000L,
                        MediaMetadataRetriever.OPTION_CLOSEST,
                    )
                    if (rawBitmap == null) {
                        frames.add(FrameData(timestampMs, emptyList(), 0f, "UNKNOWN", emptyList(), false))
                        continue
                    }

                    val bitmap = scaleBitmap(rawBitmap, 640)
                    if (bitmap !== rawBitmap) rawBitmap.recycle()

                    val jpegBytes = ByteArrayOutputStream().use { out ->
                        bitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
                        bitmap.recycle()
                        out.toByteArray()
                    }

                    val framePart = MultipartBody.Part.createFormData(
                        "frame", "frame.jpg",
                        jpegBytes.toRequestBody("image/jpeg".toMediaTypeOrNull()),
                    )

                    val response = runCatching {
                        ApiClient.poseApi.analyze(
                            frame = framePart,
                            exerciseType = exerciseType.toRequestBody("text/plain".toMediaTypeOrNull()),
                            sessionId = sessionId.toRequestBody("text/plain".toMediaTypeOrNull()),
                            studentId = "video-student".toRequestBody("text/plain".toMediaTypeOrNull()),
                            frameSeq = idx.toString().toRequestBody("text/plain".toMediaTypeOrNull()),
                            academyId = academyId.toRequestBody("text/plain".toMediaTypeOrNull()),
                        )
                    }.getOrNull()

                    val body = response?.body()
                    if (response?.isSuccessful == true && body != null) {
                        val analysis = body.analysis
                        frames.add(
                            FrameData(
                                timestampMs = timestampMs,
                                landmarks = body.landmarks,
                                score = analysis?.score ?: 0f,
                                phase = analysis?.phase ?: "UNKNOWN",
                                errors = analysis?.errors ?: emptyList(),
                                hasAlert = analysis?.hasAlert ?: false,
                            )
                        )
                    } else {
                        frames.add(FrameData(timestampMs, emptyList(), 0f, "UNKNOWN", emptyList(), false))
                    }
                }

                retriever.release()
                _state.value = VideoTestState.Ready(uri, frames)

            }.onFailure { e ->
                _state.value = VideoTestState.Error(e.message ?: "Erro ao processar vídeo.")
            }
        }
    }

    fun reset() {
        _state.value = VideoTestState.Idle
    }

    private fun scaleBitmap(bitmap: Bitmap, maxSide: Int): Bitmap {
        val w = bitmap.width
        val h = bitmap.height
        if (w <= maxSide && h <= maxSide) return bitmap
        val scale = maxSide.toFloat() / maxOf(w, h)
        return Bitmap.createScaledBitmap(bitmap, (w * scale).toInt(), (h * scale).toInt(), true)
    }
}
