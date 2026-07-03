package com.gymvision.app.service

import android.util.Log
import com.google.gson.Gson
import com.gymvision.app.model.WsAlert
import com.gymvision.app.model.WsAnalysis
import io.socket.client.IO
import io.socket.client.Socket
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import org.json.JSONObject

/**
 * WebSocket client para o Notification Service.
 * Recebe:
 *   - "alert"    → alerta de postura em tempo real
 *   - "analysis" → score e fase para feedback na tela do aluno
 */
object GymWebSocketService {

    private const val TAG = "GymWS"
    private const val WS_URL = "http://10.0.2.2:8085"   // emulador

    private val gson = Gson()
    private var socket: Socket? = null

    private val _alerts   = MutableSharedFlow<WsAlert>(extraBufferCapacity = 20)
    private val _analysis = MutableSharedFlow<WsAnalysis>(extraBufferCapacity = 50)

    val alerts:   SharedFlow<WsAlert>    = _alerts
    val analysis: SharedFlow<WsAnalysis> = _analysis

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
            val opts = IO.Options.builder()
                .setTransports(arrayOf("websocket"))
                .setPath("/ws/socket.io")
                .build()

            socket = IO.socket(WS_URL, opts)

            socket!!.on(Socket.EVENT_CONNECT) {
                Log.i(TAG, "WebSocket conectado")
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
    }
}
