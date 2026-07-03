package com.gymvision.app.ui.manageplans

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gymvision.app.model.CreateWorkoutPlanItemRequest
import com.gymvision.app.model.UserDto
import com.gymvision.app.model.WorkoutPlan
import com.gymvision.app.ui.components.ErrorState
import com.gymvision.app.ui.components.LoadingState
import com.gymvision.app.ui.components.exerciseLabel

private val EXERCISES = listOf("SQUAT", "DEADLIFT", "LUNGE", "BENCH_PRESS", "BENT_OVER_ROW")

private val DAY_LABELS = mapOf(
    0 to "Qualquer dia", 1 to "Segunda-feira", 2 to "Terça-feira",
    3 to "Quarta-feira", 4 to "Quinta-feira", 5 to "Sexta-feira",
    6 to "Sábado", 7 to "Domingo",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ManagePlansScreen(
    viewModel: ManagePlansViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var showCreateForm by remember { mutableStateOf(false) }

    if (showCreateForm) {
        CreatePlanDialog(
            students     = state.students,
            isSaving     = state.isSaving,
            onDismiss    = { showCreateForm = false },
            onConfirm    = { name, day, studentId, items ->
                viewModel.createPlan(name, day, studentId, items) { showCreateForm = false }
            },
        )
    }

    if (state.error != null) {
        AlertDialog(
            onDismissRequest = viewModel::dismissError,
            title  = { Text("Erro") },
            text   = { Text(state.error ?: "") },
            confirmButton = { TextButton(onClick = viewModel::dismissError) { Text("OK") } },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Planos de Treino", style = MaterialTheme.typography.titleMedium)
                        Text(
                            text = "Crie e gerencie planos por aluno",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showCreateForm = true }) {
                Icon(Icons.Filled.Add, contentDescription = "Novo plano")
            }
        },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            when {
                state.isLoadingStudents -> LoadingState()

                else -> Column(modifier = Modifier.fillMaxSize()) {
                    StudentSelector(
                        students   = state.students,
                        selectedId = state.selectedStudentId,
                        onSelect   = viewModel::selectStudent,
                        modifier   = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                    )

                    HorizontalDivider()

                    when {
                        state.selectedStudentId == null -> EmptySelectionState()
                        state.isLoadingPlans -> LoadingState()
                        state.plans.isEmpty() -> EmptyPlansState(
                            onCreatePlan = { showCreateForm = true }
                        )
                        else -> LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp, ),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            items(state.plans, key = { it.id }) { plan ->
                                PlanCard(
                                    plan       = plan,
                                    onDelete   = { viewModel.deletePlan(plan.id) },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StudentSelector(
    students: List<UserDto>,
    selectedId: String?,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedStudent = students.find { it.id == selectedId }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded },
        modifier = modifier.fillMaxWidth(),
    ) {
        OutlinedTextField(
            value = selectedStudent?.let { "${it.name} — ${it.email}" } ?: "Selecione um aluno…",
            onValueChange = {},
            readOnly = true,
            label = { Text("Aluno") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(/* menuAnchor sem args: compatível com M3 < 1.3 */),
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            students.forEach { student ->
                DropdownMenuItem(
                    text = {
                        Column {
                            Text(student.name, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                            Text(student.email, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    },
                    onClick = {
                        onSelect(student.id)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Composable
private fun PlanCard(plan: WorkoutPlan, onDelete: () -> Unit) {
    var showDeleteDialog by remember { mutableStateOf(false) }

    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Remover plano?") },
            text  = { Text("O plano \"${plan.name}\" será removido permanentemente.") },
            confirmButton = {
                TextButton(
                    onClick = { showDeleteDialog = false; onDelete() },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error),
                ) { Text("Remover") }
            },
            dismissButton = { TextButton(onClick = { showDeleteDialog = false }) { Text("Cancelar") } },
        )
    }

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(plan.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    Text(
                        text = DAY_LABELS[plan.dayOfWeek ?: 0] ?: "Qualquer dia",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                IconButton(onClick = { showDeleteDialog = true }) {
                    Icon(Icons.Filled.Delete, contentDescription = "Remover plano", tint = MaterialTheme.colorScheme.error)
                }
            }

            HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)

            plan.items.forEachIndexed { idx, item ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        text = "${idx + 1}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.width(20.dp),
                    )
                    Column(modifier = Modifier.weight(1f)) {
                        Text(exerciseLabel(item.exerciseType), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                        if (!item.notes.isNullOrBlank()) {
                            Text(item.notes, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = "${item.sets}×${item.repsPerSet}",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        if (item.loadKg != null) {
                            Text("${item.loadKg.toInt()} kg", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                if (idx < plan.items.lastIndex) {
                    HorizontalDivider(thickness = 0.5.dp, modifier = Modifier.padding(horizontal = 14.dp), color = MaterialTheme.colorScheme.outlineVariant)
                }
            }

            if (plan.items.isEmpty()) {
                Text(
                    text = "Nenhum exercício neste plano.",
                    modifier = Modifier.padding(14.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

// ── Formulário de criação ──────────────────────────────────────────────────────

private data class PlanItemDraft(
    val exerciseType: String = "SQUAT",
    val sets: String = "3",
    val repsPerSet: String = "10",
    val loadKg: String = "",
    val notes: String = "",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CreatePlanDialog(
    students: List<UserDto>,
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (name: String, dayOfWeek: Int?, studentId: String, items: List<CreateWorkoutPlanItemRequest>) -> Unit,
) {
    var planName       by remember { mutableStateOf("") }
    var selectedDay    by remember { mutableStateOf(0) }
    var selectedStudent by remember { mutableStateOf(students.firstOrNull()?.id ?: "") }
    var items          by remember { mutableStateOf(listOf(PlanItemDraft())) }
    var dayExpanded    by remember { mutableStateOf(false) }
    var studentExpanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Novo Plano de Treino") },
        text = {
            Column(
                modifier = Modifier
                    .verticalScroll(rememberScrollState())
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                // Aluno
                ExposedDropdownMenuBox(expanded = studentExpanded, onExpandedChange = { studentExpanded = !studentExpanded }) {
                    OutlinedTextField(
                        value = students.find { it.id == selectedStudent }?.name ?: "Selecione…",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Aluno *") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(studentExpanded) },
                        modifier = Modifier.fillMaxWidth().menuAnchor(/* menuAnchor sem args: compatível com M3 < 1.3 */),
                    )
                    ExposedDropdownMenu(expanded = studentExpanded, onDismissRequest = { studentExpanded = false }) {
                        students.forEach { s ->
                            DropdownMenuItem(
                                text = { Text(s.name) },
                                onClick = { selectedStudent = s.id; studentExpanded = false },
                            )
                        }
                    }
                }

                // Nome do plano
                OutlinedTextField(
                    value = planName,
                    onValueChange = { planName = it },
                    label = { Text("Nome do plano *") },
                    placeholder = { Text("ex: Treino A — Membros Inferiores") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )

                // Dia da semana
                ExposedDropdownMenuBox(expanded = dayExpanded, onExpandedChange = { dayExpanded = !dayExpanded }) {
                    OutlinedTextField(
                        value = DAY_LABELS[selectedDay] ?: "Qualquer dia",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Dia da semana") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(dayExpanded) },
                        modifier = Modifier.fillMaxWidth().menuAnchor(/* menuAnchor sem args: compatível com M3 < 1.3 */),
                    )
                    ExposedDropdownMenu(expanded = dayExpanded, onDismissRequest = { dayExpanded = false }) {
                        DAY_LABELS.entries.sortedBy { it.key }.forEach { (k, v) ->
                            DropdownMenuItem(
                                text = { Text(v) },
                                onClick = { selectedDay = k; dayExpanded = false },
                            )
                        }
                    }
                }

                // Exercícios
                Text("Exercícios", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)

                items.forEachIndexed { idx, item ->
                    PlanItemEditor(
                        index      = idx,
                        draft      = item,
                        showRemove = items.size > 1,
                        onChange   = { updated -> items = items.toMutableList().also { it[idx] = updated } },
                        onRemove   = { items = items.toMutableList().also { it.removeAt(idx) } },
                    )
                }

                TextButton(
                    onClick = { items = items + PlanItemDraft() },
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                ) {
                    Icon(Icons.Filled.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Adicionar exercício")
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (planName.isBlank() || selectedStudent.isBlank()) return@Button
                    val planItems = items.mapIndexed { idx, d ->
                        CreateWorkoutPlanItemRequest(
                            exerciseType = d.exerciseType,
                            sets         = d.sets.toIntOrNull() ?: 3,
                            repsPerSet   = d.repsPerSet.toIntOrNull() ?: 10,
                            loadKg       = d.loadKg.toDoubleOrNull(),
                            notes        = d.notes.ifBlank { null },
                            orderIndex   = idx,
                        )
                    }
                    onConfirm(planName, if (selectedDay == 0) null else selectedDay, selectedStudent, planItems)
                },
                enabled = planName.isNotBlank() && selectedStudent.isNotBlank() && !isSaving,
            ) {
                if (isSaving) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                    Spacer(Modifier.width(6.dp))
                    Text("Salvando…")
                } else {
                    Text("Criar plano")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isSaving) { Text("Cancelar") }
        },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlanItemEditor(
    index: Int,
    draft: PlanItemDraft,
    showRemove: Boolean,
    onChange: (PlanItemDraft) -> Unit,
    onRemove: () -> Unit,
) {
    var exerciseExpanded by remember { mutableStateOf(false) }

    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("#${index + 1}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                if (showRemove) {
                    TextButton(onClick = onRemove, contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp)) {
                        Text("remover", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelSmall)
                    }
                }
            }

            ExposedDropdownMenuBox(expanded = exerciseExpanded, onExpandedChange = { exerciseExpanded = !exerciseExpanded }) {
                OutlinedTextField(
                    value = exerciseLabel(draft.exerciseType),
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Exercício") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(exerciseExpanded) },
                    modifier = Modifier.fillMaxWidth().menuAnchor(/* menuAnchor sem args: compatível com M3 < 1.3 */),
                    textStyle = MaterialTheme.typography.bodySmall,
                )
                ExposedDropdownMenu(expanded = exerciseExpanded, onDismissRequest = { exerciseExpanded = false }) {
                    EXERCISES.forEach { ex ->
                        DropdownMenuItem(
                            text = { Text(exerciseLabel(ex)) },
                            onClick = { onChange(draft.copy(exerciseType = ex)); exerciseExpanded = false },
                        )
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = draft.sets,
                    onValueChange = { onChange(draft.copy(sets = it.take(2))) },
                    label = { Text("Séries") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                    textStyle = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = draft.repsPerSet,
                    onValueChange = { onChange(draft.copy(repsPerSet = it.take(3))) },
                    label = { Text("Reps") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                    textStyle = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = draft.loadKg,
                    onValueChange = { onChange(draft.copy(loadKg = it.take(5))) },
                    label = { Text("Carga kg") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                    textStyle = MaterialTheme.typography.bodySmall,
                )
            }

            OutlinedTextField(
                value = draft.notes,
                onValueChange = { onChange(draft.copy(notes = it)) },
                label = { Text("Observações (opcional)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                textStyle = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

// ── Estados vazios ─────────────────────────────────────────────────────────────

@Composable
private fun EmptySelectionState() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Icon(Icons.Filled.Assignment, contentDescription = null, modifier = Modifier.size(56.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f))
            Spacer(Modifier.height(12.dp))
            Text("Selecione um aluno", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun EmptyPlansState(onCreatePlan: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Icon(Icons.Filled.Assignment, contentDescription = null, modifier = Modifier.size(56.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f))
            Spacer(Modifier.height(12.dp))
            Text("Nenhum plano ativo", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = onCreatePlan) { Text("Criar primeiro plano") }
        }
    }
}
