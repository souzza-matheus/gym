package com.gymvision.app.ui.profile

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.UserDto
import kotlinx.coroutines.launch

data class ProfileUiState(
    val user: UserDto? = null,
    val isLoading: Boolean = true,
    val isLoggingOut: Boolean = false,
    val error: String? = null,
)

class ProfileViewModel : ViewModel() {

    var uiState by mutableStateOf(ProfileUiState())
        private set

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            uiState = uiState.copy(isLoading = true, error = null)
            runCatching {
                ApiClient.userApi.me()
            }.onSuccess { response ->
                val body = response.body()
                if (response.isSuccessful && body?.success == true && body.data != null) {
                    uiState = uiState.copy(user = body.data, isLoading = false)
                } else {
                    uiState = uiState.copy(isLoading = false, error = "Não foi possível carregar seu perfil")
                }
            }.onFailure { e ->
                uiState = uiState.copy(isLoading = false, error = "Erro de conexão: ${e.message}")
            }
        }
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            uiState = uiState.copy(isLoggingOut = true)
            runCatching { ApiClient.authApi.logout() }
            ApiClient.clearTokens()
            uiState = uiState.copy(isLoggingOut = false)
            onLoggedOut()
        }
    }
}
