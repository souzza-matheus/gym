package com.gymvision.app.ui.workoutplan

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.CreateSessionRequest
import com.gymvision.app.model.SessionSummary
import com.gymvision.app.model.WorkoutPlan
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.util.Calendar

data class WorkoutPlanUiState(
    val plans: List<WorkoutPlan> = emptyList(),
    val todayPlans: List<WorkoutPlan> = emptyList(),
    val isLoading: Boolean = false,
    val isCreating: Boolean = false,
    val error: String? = null,
)

class WorkoutPlanViewModel : ViewModel() {

    private val _state = MutableStateFlow(WorkoutPlanUiState(isLoading = true))
    val state: StateFlow<WorkoutPlanUiState> = _state

    val studentId: String get() = ApiClient.getUserId() ?: ""
    val academyId: String get() = ApiClient.getAcademyId() ?: ""

    init { loadPlans() }

    fun loadPlans() {
        val id = ApiClient.getUserId() ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = null)
            runCatching { ApiClient.workoutPlanApi.listByStudent(id) }
                .onSuccess { response ->
                    val plans = response.body()?.data ?: emptyList()
                    val todayDow = todayDayOfWeek()
                    val today = plans.filter { it.dayOfWeek == null || it.dayOfWeek == todayDow }
                    _state.value = WorkoutPlanUiState(plans = plans, todayPlans = today, isLoading = false)
                }
                .onFailure { e ->
                    _state.value = _state.value.copy(isLoading = false, error = e.message)
                }
        }
    }

    fun createSession(exerciseType: String, onCreated: (SessionSummary) -> Unit) {
        val sid = ApiClient.getUserId() ?: return
        val aid = ApiClient.getAcademyId() ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(isCreating = true, error = null)
            runCatching {
                ApiClient.sessionApi.create(CreateSessionRequest(sid, aid, exerciseType))
            }.onSuccess { response ->
                val session = response.body()?.data
                _state.value = _state.value.copy(isCreating = false)
                if (response.isSuccessful && session != null) onCreated(session)
                else _state.value = _state.value.copy(error = response.body()?.message ?: "Erro ao criar sessão")
            }.onFailure { e ->
                _state.value = _state.value.copy(isCreating = false, error = e.message)
            }
        }
    }

    // Returns 1=Mon..7=Sun matching the backend convention
    private fun todayDayOfWeek(): Int {
        val cal = Calendar.getInstance()
        return when (cal.get(Calendar.DAY_OF_WEEK)) {
            Calendar.MONDAY    -> 1
            Calendar.TUESDAY   -> 2
            Calendar.WEDNESDAY -> 3
            Calendar.THURSDAY  -> 4
            Calendar.FRIDAY    -> 5
            Calendar.SATURDAY  -> 6
            Calendar.SUNDAY    -> 7
            else               -> 1
        }
    }
}
