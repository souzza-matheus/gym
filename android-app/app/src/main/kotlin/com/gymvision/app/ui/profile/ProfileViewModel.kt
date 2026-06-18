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
    val isJoining: Boolean = false,
    val joinError: String? = null,
    val error: String? = null,
    val isExporting: Boolean = false,
    val exportedJson: String? = null,
    val isDeleting: Boolean = false,
    val deleteError: String? = null,
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

    fun joinAcademy(inviteCode: String) {
        viewModelScope.launch {
            uiState = uiState.copy(isJoining = true, joinError = null)
            runCatching {
                ApiClient.userApi.joinAcademy(mapOf("inviteCode" to inviteCode.uppercase()))
            }.onSuccess { response ->
                val user = response.body()?.data
                if (response.isSuccessful && user != null) {
                    uiState = uiState.copy(isJoining = false, user = user)
                    // Persist new academyId in prefs so CameraViewModel picks it up
                    ApiClient.saveUserInfo(user.id, user.name, user.role, user.academyId)
                } else {
                    uiState = uiState.copy(isJoining = false, joinError = "Código inválido ou expirado.")
                }
            }.onFailure { e ->
                uiState = uiState.copy(isJoining = false, joinError = e.message)
            }
        }
    }

    fun exportData() {
        viewModelScope.launch {
            uiState = uiState.copy(isExporting = true, exportedJson = null)
            runCatching {
                ApiClient.userApi.exportMyData()
            }.onSuccess { response ->
                val json = response.body()?.data?.let {
                    com.google.gson.GsonBuilder().setPrettyPrinting().create().toJson(it)
                }
                uiState = uiState.copy(isExporting = false, exportedJson = json)
            }.onFailure {
                uiState = uiState.copy(isExporting = false)
            }
        }
    }

    fun deleteAccount(onDeleted: () -> Unit) {
        viewModelScope.launch {
            uiState = uiState.copy(isDeleting = true, deleteError = null)
            runCatching {
                ApiClient.userApi.deleteMyAccount()
            }.onSuccess { response ->
                if (response.code() == 204) {
                    ApiClient.clearTokens()
                    onDeleted()
                } else {
                    uiState = uiState.copy(isDeleting = false, deleteError = "Erro ao excluir conta.")
                }
            }.onFailure { e ->
                uiState = uiState.copy(isDeleting = false, deleteError = e.message)
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
