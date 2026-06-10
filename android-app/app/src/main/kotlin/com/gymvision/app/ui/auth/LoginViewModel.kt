package com.gymvision.app.ui.auth

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.LoginRequest
import kotlinx.coroutines.launch

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val passwordVisible: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null,
)

class LoginViewModel : ViewModel() {

    var uiState by mutableStateOf(LoginUiState())
        private set

    fun onEmailChange(value: String) {
        uiState = uiState.copy(email = value, error = null)
    }

    fun onPasswordChange(value: String) {
        uiState = uiState.copy(password = value, error = null)
    }

    fun togglePasswordVisibility() {
        uiState = uiState.copy(passwordVisible = !uiState.passwordVisible)
    }

    fun login(onSuccess: () -> Unit) {
        val email = uiState.email.trim()
        val password = uiState.password

        if (email.isEmpty() || password.isEmpty()) {
            uiState = uiState.copy(error = "Preencha e-mail e senha")
            return
        }

        uiState = uiState.copy(isLoading = true, error = null)

        viewModelScope.launch {
            runCatching {
                ApiClient.authApi.login(LoginRequest(email, password))
            }.onSuccess { response ->
                val body = response.body()
                if (response.isSuccessful && body?.success == true && body.data != null) {
                    val data = body.data
                    ApiClient.saveTokens(data.accessToken, data.refreshToken)
                    ApiClient.saveUserInfo(
                        userId = data.user.id,
                        userName = data.user.name,
                        userRole = data.user.role,
                        academyId = data.user.academyId,
                    )
                    uiState = uiState.copy(isLoading = false)
                    onSuccess()
                } else {
                    uiState = uiState.copy(
                        isLoading = false,
                        error = body?.message ?: "Credenciais inválidas",
                    )
                }
            }.onFailure { e ->
                uiState = uiState.copy(
                    isLoading = false,
                    error = "Erro de conexão: ${e.message}",
                )
            }
        }
    }
}
