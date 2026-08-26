package com.gymvision.app.service

import android.util.Log
import com.google.gson.Gson
import com.gymvision.app.model.WsAlert
import com.gymvision.app.model.WsAnalysis
import io.socket.client.IO
import io.socket.client.Socket
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONObject

/**
 * WebSocket client para o Notification Service.
 * Recebe:
 *   - "alert"    → alerta de postura em tempo real
 *   - "analysis" → score e fase para feedback na tela do aluno
 */
object GymWebSocketService {

    private const val TAG = "GymWS"
    private val WS_URL = "http://${com.gymvision.app.BuildConfig.API_HOST}:8085"

    private val gson = Gson()
    private var socket: Socket? = null

    private val _alerts     = MutableSharedFlow<WsAlert>(extraBufferCapacity = 20)
    private val _analysis   = MutableSharedFlow<WsAnalysis>(extraBufferCapacity = 50)
    private val _isConnected = MutableStateFlow(false)

    val alerts:      SharedFlow<WsAlert>    = _alerts
    val analysis:    SharedFlow<WsAnalysis> = _analysis
    // Estado real do socket — não confundir com "algum alerta já chegou".
    // Uma sala pode estar corretamente conectada e nunca ter recebido
    // alerta nenhum (aluno sem erro de execução ainda), o que é bem
    // diferente de "o WebSocket nunca conseguiu conectar".
    val isConnected: StateFlow<Boolean>     = _isConnected

    fun connect(studentId: String, academyId: String) {
        connectInternal {
            socket!!.emit("join_student", JSONObject().apply {
                put("studentId", studentId)
                put("academyId", academyId)
            })
            Log.i(TAG, "Aluno entrou na sala studentId=$studentId academyId=$academyId")
        }
    }

    fun connectAsMonitor(userId: String, academyId: String, role: String) {
        connectInternal {
            socket!!.emit("join_academy", JSONObject().apply {
                put("userId", userId)
                put("academyId", academyId)
                put("role", role)
            })
            Log.i(TAG, "$role entrou na sala academia=$academyId")
        }
    }

    private fun connectInternal(onConnected: () -> Unit) {
        if (socket?.connected() == true) return
        try {
            // O `/ws` faz parte da URL (define o namespace Socket.IO do
            // AlertGateway, que usa `namespace: '/ws'`), não do path do
            // engine.io — igual ao dashboard (`io(`${WS_URL}/ws`, ...)`).
            // Setar path("/ws/socket.io") aqui troca o path de handshake do
            // engine.io para algo que o servidor nunca serviu (ele só
            // customiza o namespace, mantém o path padrão /socket.io/),
            // fazendo o handshake sempre falhar (404) e o socket nunca conectar
            // — mesmo com o resto do app (REST) reportando "online" normalmente.
            val opts = IO.Options.builder()
                .setTransports(arrayOf("websocket"))
                .build()

            socket = IO.socket("$WS_URL/ws", opts)

            socket!!.on(Socket.EVENT_CONNECT) {
                Log.i(TAG, "WebSocket conectado")
                _isConnected.value = true
                onConnected()
            }

            socket!!.on("alert") { args ->
                runCatching {
                    val alert = gson.fromJson(args[0].toString(), WsAlert::class.java)
                    _alerts.tryEmit(alert)
                    Log.w(TAG, "Alerta recebido: ${alert.riskLevel} — ${alert.description}")
                }
            }

            socket!!.on("analysis") { args ->
                runCatching {
                    val feedback = gson.fromJson(args[0].toString(), WsAnalysis::class.java)
                    _analysis.tryEmit(feedback)
                }
            }

            socket!!.on(Socket.EVENT_DISCONNECT) {
                Log.i(TAG, "WebSocket desconectado")
                _isConnected.value = false
            }
            socket!!.on(Socket.EVENT_CONNECT_ERROR) { args ->
                Log.e(TAG, "Erro de conexão WebSocket: ${args.firstOrNull()}")
                _isConnected.value = false
            }

            socket!!.connect()
        } catch (e: Exception) {
            Log.e(TAG, "Erro ao conectar WebSocket: ${e.message}")
        }
    }

    fun disconnect() {
        socket?.disconnect()
        socket?.off()
        socket = null
        _isConnected.value = false
    }
}
