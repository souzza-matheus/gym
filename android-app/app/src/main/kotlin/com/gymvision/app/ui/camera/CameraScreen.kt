package com.gymvision.app.ui.camera

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.AnimatedVisibility
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.DetectedError
import com.gymvision.app.model.WsAlert
import com.gymvision.app.service.GymWebSocketService
import com.gymvision.app.ui.components.ScoreGauge
import com.gymvision.app.ui.components.errorIcon
import com.gymvision.app.ui.components.phaseLabel
import com.gymvision.app.ui.components.riskColor
import com.gymvision.app.ui.theme.RiskLow
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.concurrent.Executors

@Composable
fun CameraScreen(
    sessionId: String,
    exerciseType: String,
    studentId: String,
    academyId: String,
    onFinish: () -> Unit,
    viewModel: CameraViewModel = viewModel(),
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val state by viewModel.state.collectAsStateWithLifecycle()

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted -> hasCameraPermission = granted }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
        GymWebSocketService.connect(studentId, academyId)
    }

    DisposableEffect(Unit) {
        onDispose { GymWebSocketService.disconnect() }
    }

    var showEndDialog by remember { mutableStateOf(false) }
    var alertBanner by remember { mutableStateOf<WsAlert?>(null) }

    LaunchedEffect(Unit) {
        GymWebSocketService.alerts.collect { alert ->
            if (alert.studentId == studentId) {
                alertBanner = alert
            }
        }
    }

    LaunchedEffect(alertBanner) {
        if (alertBanner != null) {
            delay(4000)
            alertBanner = null
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        if (hasCameraPermission) {
            CameraPreviewWithOverlay(
                landmarks = state.landmarks,
                onFrame = { imageProxy ->
                    viewModel.onFrame(imageProxy, exerciseType, sessionId, studentId, academyId)
                },
            )
        } else {
            PermissionRequest(onRequest = { permissionLauncher.launch(Manifest.permission.CAMERA) })
        }

        Row(
            modifier = Modifier
                .align(Alignment.TopStart)
                .statusBarsPadding()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ScoreGaugeBadge(score = state.score)
            Spacer(modifier = Modifier.width(12.dp))
            PhaseChip(phase = state.phase)
        }

        FloatingActionButton(
            onClick = { showEndDialog = true },
            modifier = Modifier
                .align(Alignment.TopEnd)
                .statusBarsPadding()
                .padding(16.dp),
            containerColor = MaterialTheme.colorScheme.error,
            contentColor = Color.White,
        ) {
            Icon(Icons.Filled.Stop, contentDescription = "Encerrar sessão")
        }

        AnimatedVisibility(
            visible = alertBanner != null,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .statusBarsPadding()
                .padding(top = 96.dp, start = 16.dp, end = 16.dp),
            enter = slideInVertically { -it } + fadeIn(),
            exit = slideOutVertically { -it } + fadeOut(),
        ) {
            alertBanner?.let { AlertBanner(it) }
        }

        ErrorsCard(
            errors = state.errors,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(16.dp),
        )
    }

    if (showEndDialog) {
        AlertDialog(
            onDismissRequest = { showEndDialog = false },
            title = { Text("Encerrar sessão?") },
            text = { Text("Você poderá ver o relatório completo na lista de sessões.") },
            confirmButton = {
                TextButton(onClick = {
                    showEndDialog = false
                    scope.launch {
                        runCatching { ApiClient.sessionApi.end(sessionId) }
                        onFinish()
                    }
                }) { Text("Encerrar") }
            },
            dismissButton = {
                TextButton(onClick = { showEndDialog = false }) { Text("Cancelar") }
            },
        )
    }
}

@Composable
private fun CameraPreviewWithOverlay(
    landmarks: List<com.gymvision.app.model.Landmark>,
    onFrame: (androidx.camera.core.ImageProxy) -> Unit,
) {
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }

    DisposableEffect(Unit) {
        onDispose { cameraExecutor.shutdown() }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                val previewView = PreviewView(ctx).apply {
                    scaleType = PreviewView.ScaleType.FILL_CENTER
                }

                val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                cameraProviderFuture.addListener({
                    val cameraProvider = cameraProviderFuture.get()

                    val preview = Preview.Builder().build().also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }

                    val imageAnalysis = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()

                    imageAnalysis.setAnalyzer(cameraExecutor) { imageProxy -> onFrame(imageProxy) }

                    runCatching {
                        cameraProvider.unbindAll()
                        cameraProvider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            imageAnalysis,
                        )
                    }
                }, ContextCompat.getMainExecutor(ctx))

                previewView
            },
        )

        PoseOverlay(landmarks = landmarks, modifier = Modifier.fillMaxSize())
    }
}

@Composable
private fun PermissionRequest(onRequest: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            imageVector = Icons.Filled.CameraAlt,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.primary,
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Precisamos da câmera para analisar seu movimento",
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(16.dp))
        Button(onClick = onRequest) {
            Text("Permitir acesso à câmera")
        }
    }
}

@Composable
private fun ScoreGaugeBadge(score: Float) {
    Box(
        modifier = Modifier
            .clip(CircleShape)
            .background(Color.Black.copy(alpha = 0.4f))
            .padding(6.dp),
    ) {
        ScoreGauge(score = score, size = 64.dp, strokeWidth = 6.dp)
    }
}

@Composable
private fun PhaseChip(phase: String) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(Color.Black.copy(alpha = 0.4f))
            .padding(horizontal = 14.dp, vertical = 8.dp),
    ) {
        Text(
            text = phaseLabel(phase),
            color = Color.White,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
private fun AlertBanner(alert: WsAlert) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = riskColor(alert.riskLevel),
        shadowElevation = 8.dp,
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Filled.Warning, contentDescription = null, tint = Color.White)
            Spacer(modifier = Modifier.width(12.dp))
            Text(alert.description, color = Color.White, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun ErrorsCard(errors: List<DetectedError>, modifier: Modifier = Modifier) {
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
                    Spacer(modifier = Modifier.width(8.dp))
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
                Spacer(modifier = Modifier.height(8.dp))
                errors.forEach { error ->
                    Row(
                        modifier = Modifier.padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            imageVector = errorIcon(error.errorType),
                            contentDescription = null,
                            tint = riskColor(error.riskLevel),
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(text = error.description, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}
