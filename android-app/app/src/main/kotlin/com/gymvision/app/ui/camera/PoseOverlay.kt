package com.gymvision.app.ui.camera

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import com.gymvision.app.model.Landmark

/** Conexões do esqueleto BlazePose (índices conforme pose-service/models.py::LandmarkType). */
private val SKELETON_CONNECTIONS = listOf(
    11 to 12, // ombros
    11 to 13, 13 to 15, // braço esquerdo
    12 to 14, 14 to 16, // braço direito
    11 to 23, 12 to 24, 23 to 24, // tronco
    23 to 25, 25 to 27, // perna esquerda
    24 to 26, 26 to 28, // perna direita
    27 to 31, 28 to 32, // pés
)

private const val MIN_VISIBILITY = 0.4f
private val ConnectionColor = Color(0xFF00D4AA)

@Composable
fun PoseOverlay(landmarks: List<Landmark>, modifier: Modifier = Modifier) {
    if (landmarks.isEmpty()) return

    val byType = remember(landmarks) { landmarks.associateBy { it.landmarkType } }

    Canvas(modifier = modifier) {
        val w = size.width
        val h = size.height

        SKELETON_CONNECTIONS.forEach { (startIdx, endIdx) ->
            val start = byType[startIdx]
            val end = byType[endIdx]
            if (start != null && end != null &&
                start.visibility >= MIN_VISIBILITY && end.visibility >= MIN_VISIBILITY
            ) {
                drawLine(
                    color = ConnectionColor,
                    start = Offset(start.x * w, start.y * h),
                    end = Offset(end.x * w, end.y * h),
                    strokeWidth = 6f,
                )
            }
        }

        byType.values.forEach { landmark ->
            if (landmark.visibility >= MIN_VISIBILITY) {
                drawCircle(
                    color = visibilityColor(landmark.visibility),
                    radius = 8f,
                    center = Offset(landmark.x * w, landmark.y * h),
                )
            }
        }
    }
}

private fun visibilityColor(visibility: Float): Color = when {
    visibility >= 0.7f -> Color(0xFF22C55E)
    visibility >= 0.4f -> Color(0xFFF59E0B)
    else -> Color(0xFFEF4444)
}
