package com.gymvision.app.ui.sessions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Repeat
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.SessionReport
import com.gymvision.app.ui.components.ErrorState
import com.gymvision.app.ui.components.LoadingState
import com.gymvision.app.ui.components.ScoreGauge
import com.gymvision.app.ui.components.StatCard
import com.gymvision.app.ui.components.errorDescription
import com.gymvision.app.ui.components.errorIcon
import com.gymvision.app.ui.components.exerciseIcon
import com.gymvision.app.ui.components.exerciseLabel
import com.gymvision.app.ui.theme.RiskLow
import com.gymvision.app.ui.theme.RiskMedium

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionDetailScreen(
    sessionId: String,
    onBack: () -> Unit,
    viewModel: SessionDetailViewModel = viewModel(),
) {
    val uiState = viewModel.uiState

    LaunchedEffect(sessionId) {
        viewModel.load(sessionId)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Relatório da sessão") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Voltar")
                    }
                },
            )
        },
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
                    onRetry = { viewModel.load(sessionId) },
                )
                uiState.report != null -> SessionReportContent(report = uiState.report)
            }
        }
    }
}

@Composable
private fun SessionReportContent(report: SessionReport) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = exerciseIcon(report.exerciseType),
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(40.dp),
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = exerciseLabel(report.exerciseType),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
        )

        Spacer(modifier = Modifier.height(24.dp))

        ScoreGauge(score = report.avgScore.toFloat(), size = 140.dp, strokeWidth = 12.dp)

        Spacer(modifier = Modifier.height(24.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            StatCard(
                icon = Icons.Filled.Repeat,
                label = "Repetições",
                value = report.totalReps.toString(),
                modifier = Modifier.weight(1f),
            )
            StatCard(
                icon = Icons.Filled.Warning,
                label = "Alertas",
                value = report.alertCount.toString(),
                modifier = Modifier.weight(1f),
                accentColor = if (report.alertCount > 0) RiskMedium else RiskLow,
            )
            StatCard(
                icon = Icons.Filled.Schedule,
                label = "Duração",
                value = formatDuration(report.durationMs),
                modifier = Modifier.weight(1f),
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "Erro mais frequente",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(8.dp))

                val dominantError = report.dominantError
                if (dominantError != null) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = errorIcon(dominantError),
                            contentDescription = null,
                            tint = RiskMedium,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(errorDescription(dominantError), style = MaterialTheme.typography.bodyMedium)
                    }
                } else {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = RiskLow)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Nenhum erro recorrente — ótima postura!", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                InfoRow(label = "Início", value = formatDateTime(report.startedAt))
                Spacer(modifier = Modifier.height(8.dp))
                InfoRow(label = "Fim", value = formatDateTime(report.endedAt))
            }
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium,
        )
    }
}

private fun formatDuration(ms: Long): String {
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return if (minutes > 0) "${minutes}min ${seconds}s" else "${seconds}s"
}

private fun formatDateTime(iso: String?): String {
    if (iso.isNullOrBlank()) return "—"
    return iso.replace("T", " ").take(16)
}
