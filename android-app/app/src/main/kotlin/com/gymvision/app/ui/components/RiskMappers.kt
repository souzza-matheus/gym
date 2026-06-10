package com.gymvision.app.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccessibilityNew
import androidx.compose.material.icons.filled.DirectionsRun
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material.icons.filled.Warning
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import com.gymvision.app.ui.theme.NeutralGray
import com.gymvision.app.ui.theme.RiskHigh
import com.gymvision.app.ui.theme.RiskLow
import com.gymvision.app.ui.theme.RiskMedium

/** Mapeamentos de enums do backend (em inglês) para rótulos/ícones/cores em PT-BR. */

fun riskColor(riskLevel: String): Color = when (riskLevel.uppercase()) {
    "LOW" -> RiskLow
    "MEDIUM" -> RiskMedium
    "HIGH" -> RiskHigh
    else -> NeutralGray
}

fun phaseLabel(phase: String): String = when (phase.uppercase()) {
    "STANDING" -> "Em pé"
    "DESCENDING" -> "Descendo"
    "BOTTOM" -> "Base"
    "ASCENDING" -> "Subindo"
    else -> "—"
}

fun exerciseLabel(exerciseType: String): String = when (exerciseType.uppercase()) {
    "SQUAT" -> "Agachamento"
    "DEADLIFT" -> "Levantamento Terra"
    "LUNGE" -> "Avanço"
    else -> exerciseType
}

fun exerciseIcon(exerciseType: String): ImageVector = when (exerciseType.uppercase()) {
    "SQUAT" -> Icons.Filled.FitnessCenter
    "DEADLIFT" -> Icons.Filled.AccessibilityNew
    "LUNGE" -> Icons.Filled.DirectionsRun
    else -> Icons.Filled.FitnessCenter
}

fun statusLabel(status: String): String = when (status.uppercase()) {
    "ACTIVE" -> "Em andamento"
    "COMPLETED" -> "Concluída"
    "CANCELLED" -> "Cancelada"
    else -> status
}

fun statusColor(status: String): Color = when (status.uppercase()) {
    "ACTIVE" -> RiskMedium
    "COMPLETED" -> RiskLow
    "CANCELLED" -> NeutralGray
    else -> NeutralGray
}

fun roleLabel(role: String): String = when (role.uppercase()) {
    "STUDENT" -> "Aluno"
    "TEACHER" -> "Professor"
    "ADMIN" -> "Administrador"
    else -> role
}

fun errorDescription(errorType: String): String = when (errorType.uppercase()) {
    "KNEE_CAVE_LEFT" -> "Joelho esquerdo caindo para dentro"
    "KNEE_CAVE_RIGHT" -> "Joelho direito caindo para dentro"
    "KNEE_OVER_TOE_LEFT" -> "Joelho esquerdo passando da ponta do pé"
    "KNEE_OVER_TOE_RIGHT" -> "Joelho direito passando da ponta do pé"
    "BACK_NOT_STRAIGHT" -> "Costas não estão retas"
    "DEPTH_INSUFFICIENT" -> "Profundidade insuficiente no movimento"
    "HEELS_OFF_GROUND" -> "Calcanhares saindo do chão"
    "BACK_ROUNDED" -> "Costas arredondadas"
    "HIPS_TOO_HIGH" -> "Quadril subindo muito rápido"
    "BAR_PATH_DRIFT" -> "Barra se afastando do corpo"
    "LANDMARK_MISSING" -> "Pontos do corpo não detectados"
    "LOW_CONFIDENCE" -> "Baixa confiança na detecção"
    else -> errorType.replace("_", " ").lowercase()
        .replaceFirstChar { it.uppercase() }
}

fun errorIcon(errorType: String): ImageVector = when (errorType.uppercase()) {
    "LANDMARK_MISSING", "LOW_CONFIDENCE" -> Icons.Filled.VisibilityOff
    else -> Icons.Filled.Warning
}
