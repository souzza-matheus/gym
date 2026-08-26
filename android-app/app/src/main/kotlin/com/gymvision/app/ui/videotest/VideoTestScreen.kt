package com.gymvision.app.ui.videotest

import android.content.Intent
import android.net.Uri
import android.widget.VideoView
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.DetectedError
import com.gymvision.app.ui.camera.PoseOverlay
import com.gymvision.app.ui.components.ScoreGauge
import com.gymvision.app.ui.components.errorDescription
import com.gymvision.app.ui.components.errorIcon
import com.gymvision.app.ui.components.exerciseLabel
import com.gymvision.app.ui.components.isCriticalSeverity
import com.gymvision.app.ui.components.phaseLabel
import com.gymvision.app.ui.components.severityColor
import com.gymvision.app.ui.theme.RiskLow
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlin.math.abs

private val EXERCISES = listOf("SQUAT", "DEADLIFT", "LUNGE", "BENCH_PRESS", "BENT_OVER_ROW")

@Composable
fun VideoTestScreen(viewModel: VideoTestViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var exerciseType by remember { mutableStateOf("SQUAT") }

    val videoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { uri: Uri? ->
        if (uri != null) {
            runCatching {
                context.contentResolver.takePersistableUriPermission(
                    uri, Intent.FLAG_GRANT_READ_URI_PERMISSION,
                )
            }
            viewModel.processVideo(uri, context, exerciseType)
        }
    }

    when (val s = state) {
        is VideoTestState.Idle -> SetupUI(
            exerciseType = exerciseType,
            onExerciseChange = { exerciseType = it },
            onPickVideo = { videoPickerLauncher.launch(arrayOf("video/*")) },
            onPickSample = { sample -> viewModel.processSampleVideo(sample, context) },
        )

        is VideoTestState.Processing -> ProcessingUI(progress = s.progress, total = s.total)

        is VideoTestState.Ready -> PlaybackUI(
            videoUri = s.videoUri,
            frames = s.frames,
            onBack = { viewModel.reset() },
        )

        is VideoTestState.Error -> ErrorUI(
            message = s.message,
            onRetry = { viewModel.reset() },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SetupUI(
    exerciseType: String,
    onExerciseChange: (String) -> Unit,
    onPickVideo: () -> Unit,
    onPickSample: (SampleVideo) -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Testar com Vídeo", style = MaterialTheme.typography.titleMedium)
                        Text(
                            text = "Simula o pipeline da câmera ao vivo",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
            )
        },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "Escolha o exercício",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )

            Spacer(Modifier.height(16.dp))

            EXERCISES.forEach { ex ->
                val selected = ex == exerciseType
                ElevatedCard(
                    onClick = { onExerciseChange(ex) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    colors = CardDefaults.elevatedCardColors(
                        containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer
                        else MaterialTheme.colorScheme.surface,
                    ),
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = exerciseLabel(ex),
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyLarge,
                            color = if (selected) MaterialTheme.colorScheme.onPrimaryContainer
                            else MaterialTheme.colorScheme.onSurface,
                        )
                        if (selected) {
                            Icon(
                                imageVector = Icons.Filled.CheckCircle,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(32.dp))

            Button(
                onClick = onPickVideo,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
            ) {
                Icon(Icons.Filled.VideoLibrary, contentDescription = null)
                Spacer(Modifier.width(12.dp))
                Text("Escolher vídeo (.mp4, .mov, .avi)")
            }

            Spacer(Modifier.height(16.dp))

            Text(
                text = "O app enviará cada frame ao servidor de análise de pose e exibirá o esqueleto sincronizado com o vídeo — exatamente como acontece com a câmera ao vivo.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(32.dp))

            Text(
                text = "Ou use um vídeo de exemplo",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )

            Spacer(Modifier.height(16.dp))

            SAMPLE_VIDEOS.forEach { sample ->
                ElevatedCard(
                    onClick = { onPickSample(sample) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Filled.VideoLibrary, contentDescription = null)
                        Spacer(Modifier.width(12.dp))
                        Text(text = sample.label, modifier = Modifier.weight(1f))
                    }
                }
            }
        }
    }
}

@Composable
private fun ProcessingUI(progress: Int, total: Int) {
    val fraction = if (total > 0) progress.toFloat() / total else 0f
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp),
        ) {
            CircularProgressIndicator(
                progress = { fraction },
                modifier = Modifier.size(80.dp),
                strokeWidth = 6.dp,
            )
            Spacer(Modifier.height(24.dp))
            Text(
                text = "Analisando vídeo",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Frame $progress de $total",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { fraction },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Enviando frames para o servidor de pose…",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PlaybackUI(
    videoUri: Uri,
    frames: List<FrameData>,
    onBack: () -> Unit,
) {
    var videoViewRef by remember { mutableStateOf<VideoView?>(null) }
    var currentFrame by remember { mutableStateOf<FrameData?>(null) }
    var isPlaying by remember { mutableStateOf(false) }
    var containerSize by remember { mutableStateOf(IntSize.Zero) }
    var videoIntrinsicSize by remember { mutableStateOf<IntSize?>(null) }

    // Poll video position every 100ms to sync overlay with playback
    LaunchedEffect(videoViewRef) {
        while (isActive) {
            delay(100)
            val vv = videoViewRef ?: continue
            isPlaying = vv.isPlaying
            val posMs = vv.currentPosition.toLong()
            if (frames.isNotEmpty()) {
                currentFrame = frames.minByOrNull { abs(it.timestampMs - posMs) }
            }
        }
    }

    // VideoView preserva o aspect ratio do vídeo (letterbox) em vez de
    // esticar para preencher o container — calcula o retângulo real onde o
    // vídeo é desenhado para que o overlay de landmarks (normalizados em
    // relação ao frame original) caia no lugar certo, e não na área de
    // letterbox/full container.
    val (contentOffset, contentSize) = remember(containerSize, videoIntrinsicSize) {
        val vs = videoIntrinsicSize
        if (vs == null || vs.width <= 0 || vs.height <= 0 ||
            containerSize.width <= 0 || containerSize.height <= 0
        ) {
            Offset.Zero to null
        } else {
            val scale = minOf(
                containerSize.width.toFloat() / vs.width,
                containerSize.height.toFloat() / vs.height,
            )
            val drawW = vs.width * scale
            val drawH = vs.height * scale
            Offset(
                (containerSize.width - drawW) / 2f,
                (containerSize.height - drawH) / 2f,
            ) to Size(drawW, drawH)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .onSizeChanged { containerSize = it },
    ) {
        // Video player
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                VideoView(ctx).also { vv ->
                    vv.setVideoURI(videoUri)
                    vv.setOnPreparedListener { mp ->
                        mp.isLooping = false
                        videoIntrinsicSize = IntSize(mp.videoWidth, mp.videoHeight)
                        vv.start()
                    }
                    videoViewRef = vv
                }
            },
        )

        // Skeleton overlay — same PoseOverlay used in CameraScreen, mapeado
        // para o retângulo real do vídeo (ver contentOffset/contentSize acima).
        PoseOverlay(
            landmarks = currentFrame?.landmarks ?: emptyList(),
            modifier = Modifier.fillMaxSize(),
            contentOffset = contentOffset,
            contentSize = contentSize,
        )

        // Score gauge + phase chip (top-left, mirroring CameraScreen layout)
        Row(
            modifier = Modifier
                .align(Alignment.TopStart)
                .statusBarsPadding()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Color.Black.copy(alpha = 0.4f))
                    .padding(6.dp),
            ) {
                ScoreGauge(score = currentFrame?.score ?: 0f, size = 64.dp, strokeWidth = 6.dp)
            }
            Spacer(Modifier.width(12.dp))
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(50))
                    .background(Color.Black.copy(alpha = 0.4f))
                    .padding(horizontal = 14.dp, vertical = 8.dp),
            ) {
                Text(
                    text = phaseLabel(currentFrame?.phase ?: "UNKNOWN"),
                    color = Color.White,
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }

        // Close / back button (top-right)
        IconButton(
            onClick = onBack,
            modifier = Modifier
                .align(Alignment.TopEnd)
                .statusBarsPadding()
                .padding(8.dp),
        ) {
            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Color.Black.copy(alpha = 0.5f))
                    .padding(4.dp),
            ) {
                Icon(Icons.Filled.Close, contentDescription = "Sair", tint = Color.White)
            }
        }

        // Play / Pause button (bottom-right corner, above the errors card)
        FilledIconButton(
            onClick = {
                videoViewRef?.let { vv ->
                    if (vv.isPlaying) vv.pause() else vv.start()
                }
            },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .navigationBarsPadding()
                .padding(end = 16.dp, bottom = 148.dp),
        ) {
            Icon(
                imageVector = if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                contentDescription = if (isPlaying) "Pausar" else "Reproduzir",
            )
        }

        // Alert banner for current error — prioriza GRAVE (risco de lesão) sobre Aviso
        val alertError = currentFrame?.errors?.firstOrNull { isCriticalSeverity(it.severity) }
            ?: currentFrame?.errors?.firstOrNull { it.riskLevel in listOf("HIGH", "MEDIUM") }
        AnimatedVisibility(
            visible = alertError != null,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .statusBarsPadding()
                .padding(top = 96.dp, start = 16.dp, end = 16.dp),
            enter = slideInVertically { -it } + fadeIn(),
            exit = slideOutVertically { -it } + fadeOut(),
        ) {
            alertError?.let { err ->
                val critical = isCriticalSeverity(err.severity)
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    color = severityColor(err.severity),
                    shadowElevation = 8.dp,
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (critical) {
                            PulsingWarningIcon()
                        } else {
                            Icon(Icons.Filled.Warning, contentDescription = null, tint = Color.White)
                        }
                        Spacer(Modifier.width(12.dp))
                        Text(
                            text = errorDescription(err.errorType),
                            color = Color.White,
                            style = if (critical) MaterialTheme.typography.titleMedium else MaterialTheme.typography.bodyMedium,
                            fontWeight = if (critical) FontWeight.Bold else FontWeight.Normal,
                        )
                    }
                }
            }
        }

        // Errors card at bottom — mirrors CameraScreen.ErrorsCard
        VideoErrorsCard(
            errors = currentFrame?.errors ?: emptyList(),
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(16.dp),
        )
    }
}

/** Ícone que pulsa (alpha) enquanto exibido — usado para alertas GRAVE (risco de lesão). */
@Composable
private fun PulsingWarningIcon(modifier: Modifier = Modifier, tint: Color = Color.White) {
    val transition = rememberInfiniteTransition(label = "alert-pulse")
    val alpha by transition.animateFloat(
        initialValue = 1f,
        targetValue = 0.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 600),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "alert-pulse-alpha",
    )
    Icon(
        Icons.Filled.Warning,
        contentDescription = null,
        tint = tint,
        modifier = modifier.alpha(alpha),
    )
}

@Composable
private fun VideoErrorsCard(errors: List<DetectedError>, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.94f),
        shadowElevation = 8.dp,
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            if (errors.isEmpty()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = RiskLow)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "Postura correta",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            } else {
                Text(
                    text = "Pontos de atenção",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(8.dp))
                errors.forEach { error ->
                    val critical = isCriticalSeverity(error.severity)
                    Row(
                        modifier = Modifier.padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (critical) {
                            PulsingWarningIcon(
                                modifier = Modifier.size(22.dp),
                                tint = severityColor(error.severity),
                            )
                        } else {
                            Icon(
                                imageVector = errorIcon(error.errorType),
                                contentDescription = null,
                                tint = severityColor(error.severity),
                                modifier = Modifier.size(20.dp),
                            )
                        }
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = errorDescription(error.errorType),
                            style = if (critical) MaterialTheme.typography.titleSmall else MaterialTheme.typography.bodyMedium,
                            fontWeight = if (critical) FontWeight.Bold else FontWeight.Normal,
                            color = if (critical) severityColor(error.severity) else MaterialTheme.colorScheme.onSurface,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ErrorUI(message: String, onRetry: () -> Unit) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.Error,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.error,
            )
            Spacer(Modifier.height(16.dp))
            Text(
                text = "Erro ao processar vídeo",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = message,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(24.dp))
            Button(onClick = onRetry) {
                Text("Tentar novamente")
            }
        }
    }
}
