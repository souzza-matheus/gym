package com.gymvision.app.ui.progress

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.EmojiEvents
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.SessionReport
import com.gymvision.app.model.StudentAnalyticsResponse
import com.gymvision.app.model.TopError
import com.gymvision.app.model.WeeklyProgress
import com.gymvision.app.ui.components.ErrorState
import com.gymvision.app.ui.components.LoadingState
import com.gymvision.app.ui.components.StatCard
import com.gymvision.app.ui.components.errorDescription
import com.gymvision.app.ui.components.exerciseIcon
import com.gymvision.app.ui.components.exerciseLabel
import com.gymvision.app.ui.theme.RiskHigh
import com.gymvision.app.ui.theme.RiskLow
import com.gymvision.app.ui.theme.RiskMedium

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProgressScreen(viewModel: ProgressViewModel = viewModel()) {
    val uiState = viewModel.uiState

    Scaffold(
        topBar = { TopAppBar(title = { Text("Progresso") }) },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            when {
                uiState.isLoading -> LoadingState()
                uiState.error != null -> ErrorState(
                    message = uiState.error,
                    onRetry = viewModel::load,
                )
                uiState.analytics != null -> ProgressContent(analytics = uiState.analytics)
            }
        }
    }
}

@Composable
private fun ProgressContent(analytics: StudentAnalyticsResponse) {
    val stats = analytics.overallStats

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                StatCard(
                    icon = Icons.Filled.FitnessCenter,
                    label = "Sessões",
                    value = stats.totalSessions.toString(),
                    modifier = Modifier.weight(1f),
                )
                StatCard(
                    icon = Icons.Filled.Repeat,
                    label = "Repetições",
                    value = stats.totalReps.toString(),
                    modifier = Modifier.weight(1f),
                )
            }
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                StatCard(
                    icon = Icons.Filled.TrendingUp,
                    label = "Score médio",
                    value = stats.avgScore.toInt().toString(),
                    modifier = Modifier.weight(1f),
                    accentColor = scoreColor(stats.avgScore.toFloat()),
                )
                StatCard(
                    icon = Icons.Filled.EmojiEvents,
                    label = "Melhor score",
                    value = stats.bestScore.toInt().toString(),
                    modifier = Modifier.weight(1f),
                    accentColor = RiskLow,
                )
            }
        }

        item {
            SectionCard(title = "Evolução semanal") {
                WeeklyProgressChart(analytics.weeklyProgress)
            }
        }

        item {
            SectionCard(title = "Erros mais frequentes") {
                TopErrorsList(analytics.topErrors)
            }
        }

        item {
            SectionCard(title = "Sessões recentes") {
                RecentSessionsList(analytics.recentSessions)
            }
        }
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(text = title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(12.dp))
            content()
        }
    }
}

@Composable
private fun WeeklyProgressChart(weeklyProgress: List<WeeklyProgress>) {
    if (weeklyProgress.isEmpty()) {
        Text(
            text = "Sem dados de progresso ainda",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        return
    }

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(140.dp),
    ) {
        val barCount = weeklyProgress.size
        val spacing = 8.dp.toPx()
        val barWidth = (size.width - spacing * (barCount - 1)) / barCount
        val cornerPx = 6.dp.toPx()

        weeklyProgress.forEachIndexed { index, week ->
            val fraction = (week.avgScore.toFloat() / 100f).coerceIn(0f, 1f)
            val barHeight = fraction * size.height
            val x = index * (barWidth + spacing)
            drawRoundRect(
                color = scoreColor(week.avgScore.toFloat()),
                topLeft = Offset(x, size.height - barHeight),
                size = Size(barWidth, barHeight),
                cornerRadius = CornerRadius(cornerPx, cornerPx),
            )
        }
    }

    Spacer(modifier = Modifier.height(8.dp))

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        weeklyProgress.forEach { week ->
            Text(
                text = week.week.takeLast(5),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun TopErrorsList(topErrors: List<TopError>) {
    if (topErrors.isEmpty()) {
        Text(
            text = "Nenhum erro recorrente registrado",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        return
    }

    val maxCount = topErrors.maxOf { it.count }.coerceAtLeast(1)

    Column {
        topErrors.forEach { error ->
            Column(modifier = Modifier.padding(vertical = 6.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(text = errorDescription(error.error), style = MaterialTheme.typography.bodyMedium)
                    Text(text = "${error.count}x", style = MaterialTheme.typography.labelMedium)
                }
                Spacer(modifier = Modifier.height(4.dp))
                LinearProgressIndicator(
                    progress = { error.count.toFloat() / maxCount },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(6.dp)
                        .clip(RoundedCornerShape(3.dp)),
                    color = RiskMedium,
                )
            }
        }
    }
}

@Composable
private fun RecentSessionsList(sessions: List<SessionReport>) {
    if (sessions.isEmpty()) {
        Text(
            text = "Nenhuma sessão concluída ainda",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        return
    }

    Column {
        sessions.forEachIndexed { index, session ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    imageVector = exerciseIcon(session.exerciseType),
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(24.dp),
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = exerciseLabel(session.exerciseType),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = "${session.totalReps} reps · ${session.alertCount} alertas",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = session.avgScore.toInt().toString(),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = scoreColor(session.avgScore.toFloat()),
                )
            }
            if (index < sessions.lastIndex) HorizontalDivider()
        }
    }
}

private fun scoreColor(score: Float): Color = when {
    score >= 80f -> RiskLow
    score >= 50f -> RiskMedium
    else -> RiskHigh
}
