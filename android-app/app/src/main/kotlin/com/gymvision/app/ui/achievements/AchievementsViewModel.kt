package com.gymvision.app.ui.achievements

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.GamificationResponse
import com.gymvision.app.model.LeaderboardResponse
import kotlinx.coroutines.launch

data class AchievementsUiState(
    val gamification: GamificationResponse? = null,
    val leaderboard: LeaderboardResponse? = null,
    val isLoading: Boolean = true,
    val error: String? = null,
)

class AchievementsViewModel : ViewModel() {

    private val studentId: String = ApiClient.getUserId() ?: ""
    private val academyId: String = ApiClient.getAcademyId() ?: ""

    var uiState by mutableStateOf(AchievementsUiState())
        private set

    init { load() }

    fun load() {
        viewModelScope.launch {
            uiState = uiState.copy(isLoading = true, error = null)
            runCatching {
                val gamification = ApiClient.analyticsApi.gamification(studentId)
                val leaderboard  = ApiClient.analyticsApi.leaderboard(academyId)
                Pair(gamification, leaderboard)
            }.onSuccess { (gamRes, lbRes) ->
                uiState = uiState.copy(
                    gamification = gamRes.body(),
                    leaderboard  = lbRes.body(),
                    isLoading    = false,
                )
            }.onFailure { e ->
                uiState = uiState.copy(isLoading = false, error = "Erro: ${e.message}")
            }
        }
    }
}
