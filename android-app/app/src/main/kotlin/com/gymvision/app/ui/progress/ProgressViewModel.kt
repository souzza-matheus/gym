package com.gymvision.app.ui.progress

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.StudentAnalyticsResponse
import kotlinx.coroutines.launch

data class ProgressUiState(
    val analytics: StudentAnalyticsResponse? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
)

class ProgressViewModel : ViewModel() {

    private val studentId: String = ApiClient.getUserId() ?: ""

    var uiState by mutableStateOf(ProgressUiState())
        private set

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            uiState = uiState.copy(isLoading = true, error = null)
            runCatching {
                ApiClient.analyticsApi.studentAnalytics(studentId, weeks = 8)
            }.onSuccess { response ->
                val body = response.body()
                if (response.isSuccessful && body != null) {
                    uiState = uiState.copy(analytics = body, isLoading = false)
                } else {
                    uiState = uiState.copy(isLoading = false, error = "Não foi possível carregar seu progresso")
                }
            }.onFailure { e ->
                uiState = uiState.copy(isLoading = false, error = "Erro de conexão: ${e.message}")
            }
        }
    }
}
