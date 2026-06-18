package com.gymvision.app.ui.sessions

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshContainer
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.SessionSummary
import com.gymvision.app.ui.components.EmptyState
import com.gymvision.app.ui.components.ErrorState
import com.gymvision.app.ui.components.LoadingState
import com.gymvision.app.ui.components.exerciseIcon
import com.gymvision.app.ui.components.exerciseLabel
import com.gymvision.app.ui.components.statusColor
import com.gymvision.app.ui.components.statusLabel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionListScreen(
    onOpenCamera: (sessionId: String, exerciseType: String, studentId: String, academyId: String) -> Unit,
    onOpenSessionDetail: (sessionId: String) -> Unit,
    viewModel: SessionListViewModel = viewModel(),
) {
    val uiState = viewModel.uiState
    var showNewSessionSheet by remember { mutableStateOf(false) }
    val pullState = rememberPullToRefreshState()

    if (pullState.isRefreshing) {
        LaunchedEffect(Unit) {
            viewModel.refresh()
        }
    }

    LaunchedEffect(uiState.isRefreshing) {
        if (!uiState.isRefreshing && pullState.isRefreshing) {
            pullState.endRefresh()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Olá, ${viewModel.userName}", style = MaterialTheme.typography.titleMedium)
                        Text(
                            text = "Suas sessões de treino",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { showNewSessionSheet = true },
                icon = { Icon(Icons.Filled.Add, contentDescription = null) },
                text = { Text("Nova sessão") },
            )
        },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .nestedScroll(pullState.nestedScrollConnection),
        ) {
            when {
                uiState.isLoading -> LoadingState()

                uiState.error != null && uiState.sessions.isEmpty() -> ErrorState(
                    message = uiState.error,
                    onRetry = viewModel::loadSessions,
                )

                uiState.sessions.isEmpty() -> EmptyState(
                    icon = Icons.Filled.FitnessCenter,
                    title = "Nenhuma sessão ainda",
                    subtitle = "Toque em \"Nova sessão\" para começar a treinar",
                )

                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 96.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(uiState.sessions, key = { it.id }) { session ->
                        SessionCard(
                            session = session,
                            onClick = {
                                if (session.status == "ACTIVE") {
                                    onOpenCamera(session.id, session.exerciseType, viewModel.studentId, viewModel.academyId)
                                } else {
                                    onOpenSessionDetail(session.id)
                                }
                            },
                        )
                    }
                }
            }

            PullToRefreshContainer(
                state = pullState,
                modifier = Modifier.align(Alignment.TopCenter),
            )
        }
    }

    if (showNewSessionSheet) {
        NewSessionSheet(
            isCreating = uiState.isCreating,
            onDismiss = { showNewSessionSheet = false },
            onSelectExercise = { exerciseType ->
                viewModel.createSession(exerciseType) { session ->
                    showNewSessionSheet = false
                    // Passa o tipo original (pode ser "AUTO") para que CameraViewModel inicie detecção
                    onOpenCamera(session.id, exerciseType, viewModel.studentId, viewModel.academyId)
                }
            },
        )
    }
}

@Composable
private fun SessionCard(session: SessionSummary, onClick: () -> Unit) {
    ElevatedCard(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = exerciseIcon(session.exerciseType),
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
            }

            Spacer(modifier = Modifier.width(16.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = exerciseLabel(session.exerciseType),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Score ${session.avgScore.toInt()} · ${session.totalReps} reps · ${session.alertCount} alertas",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            StatusChip(status = session.status)
        }
    }
}

@Composable
private fun StatusChip(status: String) {
    val color = statusColor(status)
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.15f))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (status == "ACTIVE") {
            val infiniteTransition = rememberInfiniteTransition(label = "pulse")
            val alpha by infiniteTransition.animateFloat(
                initialValue = 0.3f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(
                    animation = tween(durationMillis = 800),
                    repeatMode = RepeatMode.Reverse,
                ),
                label = "pulseAlpha",
            )
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(color.copy(alpha = alpha)),
            )
            Spacer(modifier = Modifier.width(6.dp))
        }
        Text(
            text = statusLabel(status),
            style = MaterialTheme.typography.labelSmall,
            color = color,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NewSessionSheet(
    isCreating: Boolean,
    onDismiss: () -> Unit,
    onSelectExercise: (String) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState()

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 32.dp),
        ) {
            Text(
                text = "Escolha o exercício",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )

            Spacer(modifier = Modifier.height(16.dp))

            listOf("AUTO", "SQUAT", "DEADLIFT", "LUNGE", "BENCH_PRESS", "BENT_OVER_ROW").forEach { exerciseType ->
                ExerciseOption(
                    exerciseType = exerciseType,
                    enabled = !isCreating,
                    onClick = { onSelectExercise(exerciseType) },
                )
                Spacer(modifier = Modifier.height(8.dp))
            }

            if (isCreating) {
                Spacer(modifier = Modifier.height(8.dp))
                Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
        }
    }
}

@Composable
private fun ExerciseOption(exerciseType: String, enabled: Boolean, onClick: () -> Unit) {
    ElevatedCard(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = exerciseIcon(exerciseType),
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
            }

            Spacer(modifier = Modifier.width(16.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(text = exerciseLabel(exerciseType), style = MaterialTheme.typography.titleMedium)
                Text(
                    text = exerciseDescription(exerciseType),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Icon(
                imageVector = Icons.Filled.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun exerciseDescription(exerciseType: String): String = when (exerciseType) {
    "AUTO"          -> "Detectamos automaticamente em ~2 segundos"
    "SQUAT"         -> "Agachamento livre"
    "DEADLIFT"      -> "Levantamento terra"
    "LUNGE"         -> "Avanço alternado"
    "BENCH_PRESS"   -> "Supino com barra ou haltere"
    "BENT_OVER_ROW" -> "Remada curvada bilateral"
    else -> ""
}
