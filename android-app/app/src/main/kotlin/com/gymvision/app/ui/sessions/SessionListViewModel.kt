package com.gymvision.app.ui.sessions

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.CreateSessionRequest
import com.gymvision.app.model.SessionSummary
import kotlinx.coroutines.launch

data class SessionListUiState(
    val sessions: List<SessionSummary> = emptyList(),
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val isCreating: Boolean = false,
    val error: String? = null,
)

class SessionListViewModel : ViewModel() {

    val studentId: String = ApiClient.getUserId() ?: ""
    val academyId: String = ApiClient.getAcademyId() ?: ""
    val userName: String = ApiClient.getUserName() ?: ""

    var uiState by mutableStateOf(SessionListUiState())
        private set

    init {
        loadSessions()
    }

    fun loadSessions() {
        viewModelScope.launch {
            uiState = uiState.copy(error = null)
            runCatching {
                ApiClient.sessionApi.listByStudent(studentId)
            }.onSuccess { response ->
                if (response.isSuccessful && response.body()?.success == true) {
                    uiState = uiState.copy(
                        sessions = response.body()?.data ?: emptyList(),
                        isLoading = false,
                        isRefreshing = false,
                    )
                } else {
                    uiState = uiState.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = response.body()?.message ?: "Erro ao carregar sessões",
                    )
                }
            }.onFailure { e ->
                uiState = uiState.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Erro de conexão: ${e.message}",
                )
            }
        }
    }

    fun refresh() {
        uiState = uiState.copy(isRefreshing = true)
        loadSessions()
    }

    fun createSession(exerciseType: String, onCreated: (SessionSummary) -> Unit) {
        viewModelScope.launch {
            uiState = uiState.copy(isCreating = true, error = null)
            runCatching {
                ApiClient.sessionApi.create(CreateSessionRequest(studentId, academyId, exerciseType))
            }.onSuccess { response ->
                val session = response.body()?.data
                uiState = uiState.copy(isCreating = false)
                if (response.isSuccessful && session != null) {
                    onCreated(session)
                } else {
                    uiState = uiState.copy(error = response.body()?.message ?: "Erro ao criar sessão")
                }
            }.onFailure { e ->
                uiState = uiState.copy(isCreating = false, error = "Erro: ${e.message}")
            }
        }
    }
}
