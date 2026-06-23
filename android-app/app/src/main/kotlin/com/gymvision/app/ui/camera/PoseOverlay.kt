package com.gymvision.app.ui.camera

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
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

/**
 * Desenha o esqueleto sobre [modifier]. Por padrão assume que o Canvas cobre
 * exatamente a área de conteúdo visível (caso de CameraScreen, cuja PreviewView
 * usa FILL_CENTER). Quando o conteúdo é desenhado em letterbox dentro de um
 * container maior (ex.: VideoView preservando aspect ratio em VideoTestScreen),
 * passe [contentOffset]/[contentSize] com o retângulo real ocupado pelo vídeo —
 * caso contrário os landmarks (normalizados 0-1 em relação ao frame original)
 * são mapeados para a área errada e aparecem deslocados/fora da tela.
 */
@Composable
fun PoseOverlay(
    landmarks: List<Landmark>,
    modifier: Modifier = Modifier,
    contentOffset: Offset = Offset.Zero,
    contentSize: Size? = null,
) {
    if (landmarks.isEmpty()) return

    val byType = remember(landmarks) { landmarks.associateBy { it.landmarkType } }

    Canvas(modifier = modifier) {
        val w = contentSize?.width ?: size.width
        val h = contentSize?.height ?: size.height
        val offX = contentOffset.x
        val offY = contentOffset.y

        SKELETON_CONNECTIONS.forEach { (startIdx, endIdx) ->
            val start = byType[startIdx]
            val end = byType[endIdx]
            if (start != null && end != null &&
                start.visibility >= MIN_VISIBILITY && end.visibility >= MIN_VISIBILITY
            ) {
                drawLine(
                    color = ConnectionColor,
                    start = Offset(offX + start.x * w, offY + start.y * h),
                    end = Offset(offX + end.x * w, offY + end.y * h),
                    strokeWidth = 6f,
                )
            }
        }

        byType.values.forEach { landmark ->
            if (landmark.visibility >= MIN_VISIBILITY) {
                drawCircle(
                    color = visibilityColor(landmark.visibility),
                    radius = 8f,
                    center = Offset(offX + landmark.x * w, offY + landmark.y * h),
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
