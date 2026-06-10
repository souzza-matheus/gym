package com.gymvision.app.ui.sessions

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.SessionReport
import kotlinx.coroutines.launch

data class SessionDetailUiState(
    val report: SessionReport? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
)

class SessionDetailViewModel : ViewModel() {

    var uiState by mutableStateOf(SessionDetailUiState())
        private set

    fun load(sessionId: String) {
        viewModelScope.launch {
            uiState = uiState.copy(isLoading = true, error = null)
            runCatching {
                ApiClient.analyticsApi.sessionReport(sessionId)
            }.onSuccess { response ->
                val report = response.body()
                if (response.isSuccessful && report != null) {
                    uiState = uiState.copy(report = report, isLoading = false)
                } else {
                    uiState = uiState.copy(isLoading = false, error = "Não foi possível carregar o relatório")
                }
            }.onFailure { e ->
                uiState = uiState.copy(isLoading = false, error = "Erro de conexão: ${e.message}")
            }
        }
    }
}
