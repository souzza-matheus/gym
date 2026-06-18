package com.gymvision.app.ui.workoutplan

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.WorkoutPlan
import com.gymvision.app.model.WorkoutPlanItem
import com.gymvision.app.ui.components.EmptyState
import com.gymvision.app.ui.components.ErrorState
import com.gymvision.app.ui.components.LoadingState
import com.gymvision.app.ui.components.exerciseIcon
import com.gymvision.app.ui.components.exerciseLabel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkoutPlanScreen(
    onNavigateToCamera: (sessionId: String, exerciseType: String, studentId: String, academyId: String) -> Unit,
    viewModel: WorkoutPlanViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var showAll by remember { mutableStateOf(false) }

    val displayedPlans = if (showAll) state.plans else state.todayPlans

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Meu Treino", style = MaterialTheme.typography.titleMedium)
                        Text(
                            text = if (showAll) "Todos os planos ativos" else "Plano de hoje",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                actions = {
                    TextButton(onClick = { showAll = !showAll }) {
                        Text(if (showAll) "Ver hoje" else "Ver todos", style = MaterialTheme.typography.labelMedium)
                    }
                },
            )
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            when {
                state.isLoading -> LoadingState()

                state.error != null && displayedPlans.isEmpty() -> ErrorState(
                    message = state.error ?: "Erro desconhecido",
                    onRetry = viewModel::loadPlans,
                )

                displayedPlans.isEmpty() && !showAll -> Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Spacer(Modifier.height(48.dp))
                    EmptyState(
                        icon = Icons.Filled.CalendarToday,
                        title = "Nenhum treino para hoje",
                        subtitle = "Peça ao seu professor para criar um plano,\nou veja todos os planos disponíveis.",
                    )
                    Spacer(Modifier.height(16.dp))
                    OutlinedButton(onClick = { showAll = true }) {
                        Text("Ver todos os planos")
                    }
                }

                displayedPlans.isEmpty() -> EmptyState(
                    icon = Icons.Filled.FitnessCenter,
                    title = "Nenhum plano ativo",
                    subtitle = "Peça ao seu professor para criar um plano de treino.",
                )

                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 96.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    items(displayedPlans, key = { it.id }) { plan ->
                        PlanCard(
                            plan = plan,
                            isCreating = state.isCreating,
                            onStartExercise = { exerciseType ->
                                viewModel.createSession(exerciseType) { session ->
                                    onNavigateToCamera(session.id, session.exerciseType, viewModel.studentId, viewModel.academyId)
                                }
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PlanCard(plan: WorkoutPlan, isCreating: Boolean, onStartExercise: (String) -> Unit) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.08f))
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = plan.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    if (plan.dayOfWeek != null) {
                        Text(
                            text = dayLabel(plan.dayOfWeek),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
                Surface(
                    shape = RoundedCornerShape(50),
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                ) {
                    Text(
                        text = "${plan.items.size} exerc.",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }

            HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)

            // Items
            plan.items.forEachIndexed { idx, item ->
                PlanItemRow(
                    item = item,
                    isCreating = isCreating,
                    onStart = { onStartExercise(item.exerciseType) },
                )
                if (idx < plan.items.lastIndex) {
                    HorizontalDivider(
                        thickness = 0.5.dp,
                        modifier = Modifier.padding(horizontal = 16.dp),
                        color = MaterialTheme.colorScheme.outlineVariant,
                    )
                }
            }

            if (plan.items.isEmpty()) {
                Text(
                    text = "Nenhum exercício neste plano.",
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun PlanItemRow(item: WorkoutPlanItem, isCreating: Boolean, onStart: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Index badge
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.secondaryContainer),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = exerciseIcon(item.exerciseType),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSecondaryContainer,
                modifier = Modifier.size(20.dp),
            )
        }

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = exerciseLabel(item.exerciseType),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Medium,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip("${item.sets}×${item.repsPerSet}", MaterialTheme.colorScheme.primary)
                if (item.loadKg != null) {
                    Chip("${item.loadKg.toInt()} kg", Color(0xFF2E7D32))
                }
            }
            if (!item.notes.isNullOrBlank()) {
                Text(
                    text = item.notes,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 2.dp),
                )
            }
        }

        FilledIconButton(
            onClick = onStart,
            enabled = !isCreating,
            modifier = Modifier.size(40.dp),
        ) {
            if (isCreating) {
                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary)
            } else {
                Icon(Icons.Filled.PlayArrow, contentDescription = "Iniciar ${item.exerciseType}", modifier = Modifier.size(20.dp))
            }
        }
    }
}

@Composable
private fun Chip(text: String, color: Color) {
    Surface(
        shape = RoundedCornerShape(50),
        color = color.copy(alpha = 0.12f),
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
            style = MaterialTheme.typography.labelSmall,
            color = color,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

private fun dayLabel(dow: Int) = when (dow) {
    1 -> "Segunda-feira"
    2 -> "Terça-feira"
    3 -> "Quarta-feira"
    4 -> "Quinta-feira"
    5 -> "Sexta-feira"
    6 -> "Sábado"
    7 -> "Domingo"
    else -> ""
}
