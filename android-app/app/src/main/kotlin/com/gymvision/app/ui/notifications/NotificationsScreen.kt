package com.gymvision.app.ui.notifications

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.*
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.WsAlert
import com.gymvision.app.ui.components.exerciseLabel
import com.gymvision.app.ui.components.phaseLabel
import com.gymvision.app.ui.components.riskColor
import com.gymvision.app.ui.components.severityColor
import com.gymvision.app.ui.components.severityLabel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(
    viewModel: NotificationsViewModel = viewModel(),
) {
    val alerts by viewModel.alerts.collectAsStateWithLifecycle()
    val isConnected by viewModel.isConnected.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Alertas", style = MaterialTheme.typography.titleMedium)
                        Text(
                            text = when {
                                !isConnected      -> "Conectando…"
                                alerts.isEmpty()  -> "Conectado — nenhum alerta ainda"
                                else              -> "${alerts.size} alerta(s) recebido(s)"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                actions = {
                    if (alerts.isNotEmpty()) {
                        IconButton(onClick = viewModel::clearAlerts) {
                            Icon(Icons.Filled.DeleteSweep, contentDescription = "Limpar alertas")
                        }
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
            if (alerts.isEmpty()) {
                EmptyAlertsState()
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(alerts, key = { it.id }) { item ->
                        AlertItemCard(alert = item.alert)
                    }
                }
            }
        }
    }
}

@Composable
private fun AlertItemCard(alert: WsAlert) {
    val riskColor     = riskColor(alert.riskLevel)
    val severityColor = severityColor(alert.severity)

    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(14.dp)) {

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Surface(
                        shape = RoundedCornerShape(50),
                        color = severityColor.copy(alpha = 0.15f),
                    ) {
                        Text(
                            text = severityLabel(alert.severity).uppercase(),
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = severityColor,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    Surface(
                        shape = RoundedCornerShape(50),
                        color = riskColor.copy(alpha = 0.12f),
                    ) {
                        Text(
                            text = alert.riskLevel,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = riskColor,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
                Text(
                    text = formatTimestamp(alert.timestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Spacer(Modifier.height(8.dp))

            Text(
                text = alert.description,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )

            Spacer(Modifier.height(6.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                LabeledValue("Exercício", exerciseLabel(alert.exerciseType))
                LabeledValue("Fase", phaseLabel(alert.phase))
                LabeledValue("Score", "${(alert.score * 100).toInt()}%")
            }

            Spacer(Modifier.height(4.dp))

            Text(
                text = "Aluno: ${alert.studentId.take(8)}…",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun LabeledValue(label: String, value: String) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
private fun EmptyAlertsState() {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            imageVector = Icons.Filled.Notifications,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
        )
        Spacer(Modifier.height(16.dp))
        Text(
            text = "Sem alertas",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = "Os alertas dos alunos da academia\naparecerão aqui em tempo real.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
            textAlign = TextAlign.Center,
        )
    }
}

private fun formatTimestamp(timestamp: String): String {
    return try {
        // ISO 8601: "2024-01-15T14:30:00.000Z" → "14:30"
        val timePart = timestamp.substringAfter("T").substringBefore(".")
        timePart.take(5)
    } catch (e: Exception) {
        timestamp.take(16)
    }
}
