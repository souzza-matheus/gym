package com.gymvision.app.ui.profile

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Business
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.VpnKey
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.UserDto
import com.gymvision.app.ui.components.ErrorState
import com.gymvision.app.ui.components.LoadingState
import com.gymvision.app.ui.components.roleLabel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    onLoggedOut: () -> Unit,
    viewModel: ProfileViewModel = viewModel(),
) {
    val uiState = viewModel.uiState

    Scaffold(
        topBar = { TopAppBar(title = { Text("Perfil") }) },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            when {
                uiState.isLoading -> LoadingState()
                uiState.error != null -> ProfileErrorContent(
                    message = uiState.error,
                    isLoggingOut = uiState.isLoggingOut,
                    onRetry = viewModel::load,
                    onLogout = { viewModel.logout(onLoggedOut) },
                )
                uiState.user != null -> ProfileContent(
                    user = uiState.user,
                    isLoggingOut = uiState.isLoggingOut,
                    isJoining = uiState.isJoining,
                    joinError = uiState.joinError,
                    isExporting = uiState.isExporting,
                    exportedJson = uiState.exportedJson,
                    isDeleting = uiState.isDeleting,
                    deleteError = uiState.deleteError,
                    onLogout = { viewModel.logout(onLoggedOut) },
                    onJoinAcademy = viewModel::joinAcademy,
                    onExportData = viewModel::exportData,
                    onDeleteAccount = { viewModel.deleteAccount(onLoggedOut) },
                )
            }
        }
    }
}

@Composable
private fun ProfileErrorContent(
    message: String,
    isLoggingOut: Boolean,
    onRetry: () -> Unit,
    onLogout: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(modifier = Modifier.weight(1f)) {
            ErrorState(message = message, onRetry = onRetry)
        }

        OutlinedButton(
            onClick = onLogout,
            enabled = !isLoggingOut,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error),
        ) {
            if (isLoggingOut) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.error,
                )
            } else {
                Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Sair")
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
    }
}

@Composable
private fun ProfileContent(
    user: UserDto,
    isLoggingOut: Boolean,
    isJoining: Boolean,
    joinError: String?,
    isExporting: Boolean,
    exportedJson: String?,
    isDeleting: Boolean,
    deleteError: String?,
    onLogout: () -> Unit,
    onJoinAcademy: (String) -> Unit,
    onExportData: () -> Unit,
    onDeleteAccount: () -> Unit,
) {
    var showDeleteDialog by remember { mutableStateOf(false) }
    var showExportDialog by remember { mutableStateOf(false) }

    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Excluir conta") },
            text = { Text("Esta ação é permanente. Todos os seus dados de perfil serão removidos imediatamente. Deseja continuar?") },
            confirmButton = {
                TextButton(
                    onClick = { showDeleteDialog = false; onDeleteAccount() },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
                ) { Text("Excluir definitivamente") }
            },
            dismissButton = { TextButton(onClick = { showDeleteDialog = false }) { Text("Cancelar") } },
        )
    }

    if (showExportDialog && exportedJson != null) {
        AlertDialog(
            onDismissRequest = { showExportDialog = false },
            title = { Text("Seus dados (JSON)") },
            text = {
                Text(
                    text = exportedJson,
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                )
            },
            confirmButton = { TextButton(onClick = { showExportDialog = false }) { Text("Fechar") } },
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(modifier = Modifier.height(24.dp))

        Box(
            modifier = Modifier
                .size(96.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primary),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = initials(user.name),
                fontSize = 36.sp,
                color = MaterialTheme.colorScheme.onPrimary,
                fontWeight = FontWeight.Bold,
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(text = user.name, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = user.email,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(modifier = Modifier.height(12.dp))

        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f))
                .padding(horizontal = 14.dp, vertical = 6.dp),
        ) {
            Text(
                text = roleLabel(user.role),
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.SemiBold,
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        val academyId = user.academyId
        if (!academyId.isNullOrBlank()) {
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Filled.Business, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Academia",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            text = user.academyName ?: academyId,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                }
            }
        } else {
            JoinAcademyCard(isJoining = isJoining, error = joinError, onJoin = onJoinAcademy)
        }

        Spacer(modifier = Modifier.height(24.dp))

        // ── Privacidade e dados (LGPD) ────────────────────────────────────
        ElevatedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                Text(
                    text = "Privacidade e Dados",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(12.dp))

                OutlinedButton(
                    onClick = {
                        onExportData()
                        showExportDialog = true
                    },
                    enabled = !isExporting,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (isExporting) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text("Exportando…")
                    } else {
                        Icon(Icons.Filled.Download, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Exportar meus dados")
                    }
                }

                Spacer(Modifier.height(8.dp))

                OutlinedButton(
                    onClick = { showDeleteDialog = true },
                    enabled = !isDeleting,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.error),
                ) {
                    if (isDeleting) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp), strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.error,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("Excluindo…")
                    } else {
                        Icon(Icons.Filled.Delete, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Excluir minha conta")
                    }
                }

                if (deleteError != null) {
                    Spacer(Modifier.height(4.dp))
                    Text(deleteError, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                }

                Spacer(Modifier.height(4.dp))
                Text(
                    text = "Conforme a LGPD (Lei nº 13.709/2018), você pode exportar ou excluir seus dados a qualquer momento.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedButton(
            onClick = onLogout,
            enabled = !isLoggingOut,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error),
        ) {
            if (isLoggingOut) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.error,
                )
            } else {
                Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Sair")
            }
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun JoinAcademyCard(isJoining: Boolean, error: String?, onJoin: (String) -> Unit) {
    var code by remember { mutableStateOf("") }

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.VpnKey, contentDescription = null, tint = MaterialTheme.colorScheme.secondary)
                Spacer(Modifier.width(10.dp))
                Text("Entrar em uma academia", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(12.dp))
            Text(
                text = "Solicite o código de convite ao seu professor.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = code,
                onValueChange = { code = it.uppercase().take(12) },
                label = { Text("Código de convite") },
                placeholder = { Text("ex: GYMVIS8412") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { if (code.isNotBlank()) onJoin(code) }),
            )
            if (error != null) {
                Spacer(Modifier.height(4.dp))
                Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
            Spacer(Modifier.height(12.dp))
            Button(
                onClick = { onJoin(code) },
                enabled = code.length >= 6 && !isJoining,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (isJoining) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                } else {
                    Text("Entrar na academia")
                }
            }
        }
    }
}

private fun initials(name: String): String {
    val parts = name.trim().split(" ").filter { it.isNotBlank() }
    return when {
        parts.isEmpty() -> "?"
        parts.size == 1 -> parts[0].take(2).uppercase()
        else -> "${parts.first().first()}${parts.last().first()}".uppercase()
    }
}
