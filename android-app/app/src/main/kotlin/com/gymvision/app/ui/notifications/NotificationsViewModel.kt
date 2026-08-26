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
import java.util.UUID

/**
 * `id` gerado no cliente — o timestamp do backend só tem granularidade de
 * segundo (`time.strftime(...%SZ...)`), então dois alertas do mesmo session_id
 * no mesmo segundo (comum: erro no joelho esquerdo E direito no mesmo frame)
 * colidem se a key do LazyColumn depender só de sessionId+timestamp, travando
 * o Compose com "Key ... was already used".
 */
data class AlertItem(val id: String = UUID.randomUUID().toString(), val alert: WsAlert)

class NotificationsViewModel : ViewModel() {

    private val _alerts = MutableStateFlow<List<AlertItem>>(emptyList())
    val alerts: StateFlow<List<AlertItem>> = _alerts

    val isConnected: StateFlow<Boolean> = GymWebSocketService.isConnected

    init {
        val userId    = ApiClient.getUserId()
        val academyId = ApiClient.getAcademyId()
        val role      = ApiClient.getUserRole()

        if (userId != null && academyId != null && role != null) {
            GymWebSocketService.connectAsMonitor(userId, academyId, role)
            viewModelScope.launch {
                GymWebSocketService.alerts.collect { alert ->
                    _alerts.update { listOf(AlertItem(alert = alert)) + it }
                    AlertNotificationHelper.notify(alert)
                }
            }
        }
    }

    fun clearAlerts() {
        _alerts.value = emptyList()
    }
}
