package com.gymvision.app.ui.notifications

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.WsAlert
import com.gymvision.app.service.AlertNotificationHelper
import com.gymvision.app.service.GymWebSocketService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class NotificationsViewModel : ViewModel() {

    private val _alerts = MutableStateFlow<List<WsAlert>>(emptyList())
    val alerts: StateFlow<List<WsAlert>> = _alerts

    init {
        val userId    = ApiClient.getUserId()
        val academyId = ApiClient.getAcademyId()
        val role      = ApiClient.getUserRole()

        if (userId != null && academyId != null && role != null) {
            GymWebSocketService.connectAsMonitor(userId, academyId, role)
            viewModelScope.launch {
                GymWebSocketService.alerts.collect { alert ->
                    _alerts.update { listOf(alert) + it }
                    AlertNotificationHelper.notify(alert)
                }
            }
        }
    }

    fun clearAlerts() {
        _alerts.value = emptyList()
    }
}
