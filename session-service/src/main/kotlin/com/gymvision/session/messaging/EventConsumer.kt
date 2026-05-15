package com.gymvision.session.messaging

import com.fasterxml.jackson.databind.ObjectMapper
import com.gymvision.session.service.RecordRepRequest
import com.gymvision.session.service.SessionService
import org.slf4j.LoggerFactory
import org.springframework.amqp.rabbit.annotation.RabbitListener
import org.springframework.stereotype.Component
import java.util.UUID

@Component
class SessionEventConsumer(
    private val sessionService: SessionService,
    private val objectMapper: ObjectMapper
) {
    private val log = LoggerFactory.getLogger(javaClass)

    /**
     * Consome gym.exercise.result publicado pelo Pose+Analyzer Service.
     * Registra a rep na sessão se a sessão existir e estiver ativa.
     */
    @RabbitListener(queues = ["gym.exercise.result"])
    fun onExerciseResult(message: String) {
        runCatching {
            val payload = objectMapper.readTree(message)
            val data = payload["data"]

            val sessionId = UUID.fromString(data["session_id"].asText())
            val score = data["score"].asDouble()
            val phase = data["phase"].asText()
            val errors = data["errors"].toString()
            val hasAlert = data["has_alert"].asBoolean(false)

            sessionService.recordRep(sessionId, RecordRepRequest(
                score = score,
                phase = phase,
                errors = errors,
                hasAlert = hasAlert
            ))

            log.debug("Rep registrada | session={} score={}", sessionId, score)
        }.onFailure { e ->
            log.error("Erro ao processar gym.exercise.result: {}", e.message)
        }
    }

    /**
     * Consome gym.alert.created publicado pelo Pose+Analyzer Service.
     * Salva referência do alerta na sessão para histórico.
     */
    @RabbitListener(queues = ["gym.alert.created"])
    fun onAlertCreated(message: String) {
        runCatching {
            val payload = objectMapper.readTree(message)
            val data = payload["data"]

            val sessionId = UUID.fromString(data["session_id"].asText())
            val errorType = data["error_type"].asText()
            val riskLevel = data["risk_level"].asText()
            val description = data["description"].asText()

            sessionService.saveAlert(sessionId, errorType, riskLevel, description)
            log.info("Alerta salvo | session={} type={} risk={}", sessionId, errorType, riskLevel)
        }.onFailure { e ->
            log.error("Erro ao processar gym.alert.created: {}", e.message)
        }
    }
}
