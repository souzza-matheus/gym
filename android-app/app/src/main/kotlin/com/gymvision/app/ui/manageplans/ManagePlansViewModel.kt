package com.gymvision.app.ui.manageplans

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.CreateWorkoutPlanItemRequest
import com.gymvision.app.model.CreateWorkoutPlanRequest
import com.gymvision.app.model.UserDto
import com.gymvision.app.model.WorkoutPlan
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ManagePlansState(
    val students: List<UserDto> = emptyList(),
    val selectedStudentId: String? = null,
    val plans: List<WorkoutPlan> = emptyList(),
    val isLoadingStudents: Boolean = false,
    val isLoadingPlans: Boolean = false,
    val isSaving: Boolean = false,
    val error: String? = null,
)

class ManagePlansViewModel : ViewModel() {

    private val _state = MutableStateFlow(ManagePlansState(isLoadingStudents = true))
    val state: StateFlow<ManagePlansState> = _state

    val professorId: String get() = ApiClient.getUserId()    ?: ""
    val academyId:   String get() = ApiClient.getAcademyId() ?: ""

    init { loadStudents() }

    fun loadStudents() {
        viewModelScope.launch {
            _state.update { it.copy(isLoadingStudents = true, error = null) }
            runCatching { ApiClient.userApi.listByRole("STUDENT") }
                .onSuccess { response ->
                    val students = response.body()?.data ?: emptyList()
                    _state.update { it.copy(students = students, isLoadingStudents = false) }
                }
                .onFailure { e ->
                    _state.update { it.copy(isLoadingStudents = false, error = e.message) }
                }
        }
    }

    fun selectStudent(studentId: String) {
        _state.update { it.copy(selectedStudentId = studentId, plans = emptyList(), error = null) }
        loadPlansForStudent(studentId)
    }

    private fun loadPlansForStudent(studentId: String) {
        viewModelScope.launch {
            _state.update { it.copy(isLoadingPlans = true, error = null) }
            runCatching { ApiClient.workoutPlanApi.listByStudent(studentId) }
                .onSuccess { response ->
                    val plans = response.body()?.data ?: emptyList()
                    _state.update { it.copy(plans = plans, isLoadingPlans = false) }
                }
                .onFailure { e ->
                    _state.update { it.copy(isLoadingPlans = false, error = e.message) }
                }
        }
    }

    fun createPlan(
        name: String,
        dayOfWeek: Int?,
        studentId: String,
        items: List<CreateWorkoutPlanItemRequest>,
        onSuccess: () -> Unit,
    ) {
        viewModelScope.launch {
            _state.update { it.copy(isSaving = true, error = null) }
            val request = CreateWorkoutPlanRequest(
                academyId   = academyId,
                studentId   = studentId,
                professorId = professorId,
                name        = name,
                dayOfWeek   = dayOfWeek,
                items       = items,
            )
            runCatching { ApiClient.workoutPlanApi.create(request) }
                .onSuccess { response ->
                    _state.update { it.copy(isSaving = false) }
                    if (response.isSuccessful) {
                        loadPlansForStudent(studentId)
                        onSuccess()
                    } else {
                        _state.update { it.copy(error = response.body()?.message ?: "Erro ao criar plano") }
                    }
                }
                .onFailure { e ->
                    _state.update { it.copy(isSaving = false, error = e.message) }
                }
        }
    }

    fun deletePlan(planId: String) {
        viewModelScope.launch {
            runCatching { ApiClient.workoutPlanApi.delete(planId) }
                .onSuccess {
                    _state.update { it.copy(plans = it.plans.filter { p -> p.id != planId }) }
                }
                .onFailure { e ->
                    _state.update { it.copy(error = e.message) }
                }
        }
    }

    fun dismissError() {
        _state.update { it.copy(error = null) }
    }
}
