package com.gymvision.session.service

import com.gymvision.session.model.*
import com.gymvision.session.repository.*
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.time.Instant
import java.util.UUID

// ── DTOs ──────────────────────────────────────────────────────────────────────

data class CreateSessionRequest(
    val studentId: UUID,
    val academyId: UUID,
    val exerciseType: String
)

data class RecordRepRequest(
    val score: Double,
    val phase: String,
    val errors: String = "[]",
    val hasAlert: Boolean = false
)

data class SessionSummary(
    val id: UUID,
    val studentId: UUID,
    val academyId: UUID,
    val exerciseType: String,
    val status: String,
    val avgScore: Double,
    val totalReps: Int,
    val alertCount: Int,
    val startedAt: Instant,
    val endedAt: Instant?
)

data class RepDto(
    val id: UUID,
    val sessionId: UUID,
    val repNumber: Int,
    val score: Double,
    val phase: String,
    val errors: String,
    val hasAlert: Boolean,
    val recordedAt: Instant
)

fun Session.toSummary() = SessionSummary(
    id = id, studentId = studentId, academyId = academyId,
    exerciseType = exerciseType.name, status = status.name,
    avgScore = avgScore, totalReps = totalReps, alertCount = alertCount,
    startedAt = startedAt, endedAt = endedAt
)

fun Rep.toDto() = RepDto(
    id = id, sessionId = sessionId, repNumber = repNumber,
    score = score, phase = phase, errors = errors,
    hasAlert = hasAlert, recordedAt = recordedAt
)

// ── SessionService ────────────────────────────────────────────────────────────

@Service
class SessionService(
    private val sessionRepo: SessionRepository,
    private val repRepo: RepRepository,
    private val alertRefRepo: AlertRefRepository
) {

    @Transactional
    fun createSession(req: CreateSessionRequest): SessionSummary {
        val type = runCatching { ExerciseType.valueOf(req.exerciseType.uppercase()) }
            .getOrDefault(ExerciseType.UNKNOWN)
        val session = sessionRepo.save(
            Session(studentId = req.studentId, academyId = req.academyId, exerciseType = type)
        )
        return session.toSummary()
    }

    fun getSession(id: UUID): SessionSummary =
        sessionRepo.findById(id).orElseThrow { NoSuchElementException("Sessão não encontrada: $id") }.toSummary()

    fun listByStudent(studentId: UUID): List<SessionSummary> =
        sessionRepo.findAllByStudentId(studentId).map { it.toSummary() }

    fun listByAcademy(academyId: UUID): List<SessionSummary> =
        sessionRepo.findAllByAcademyId(academyId).map { it.toSummary() }

    @Transactional
    fun recordRep(sessionId: UUID, req: RecordRepRequest): RepDto {
        val session = sessionRepo.findById(sessionId)
            .orElseThrow { NoSuchElementException("Sessão não encontrada: $sessionId") }
        if (session.status != SessionStatus.ACTIVE)
            throw IllegalStateException("Sessão não está ativa")

        val repNumber = (repRepo.countBySessionId(sessionId) + 1).toInt()
        val rep = repRepo.save(
            Rep(
                sessionId = sessionId,
                repNumber = repNumber,
                score = req.score,
                phase = req.phase,
                errors = req.errors,
                hasAlert = req.hasAlert
            )
        )

        // Atualiza estatísticas da sessão
        val newAvg = repRepo.avgScoreBySessionId(sessionId)
        sessionRepo.save(session.copy(
            avgScore = newAvg,
            totalReps = repNumber,
            alertCount = session.alertCount + if (req.hasAlert) 1 else 0
        ))

        return rep.toDto()
    }

    @Transactional
    fun endSession(sessionId: UUID): SessionSummary {
        val session = sessionRepo.findById(sessionId)
            .orElseThrow { NoSuchElementException("Sessão não encontrada: $sessionId") }
        val updated = sessionRepo.save(
            session.copy(status = SessionStatus.COMPLETED, endedAt = Instant.now())
        )
        return updated.toSummary()
    }

    fun getReps(sessionId: UUID): List<RepDto> =
        repRepo.findAllBySessionIdOrderByRepNumberAsc(sessionId).map { it.toDto() }

    fun getAlerts(sessionId: UUID): List<AlertRef> =
        alertRefRepo.findAllBySessionId(sessionId)

    @Transactional
    fun saveAlert(sessionId: UUID, errorType: String, riskLevel: String, description: String): AlertRef =
        alertRefRepo.save(AlertRef(
            sessionId = sessionId, errorType = errorType,
            riskLevel = riskLevel, description = description
        ))

    @Transactional
    fun acknowledgeAlert(alertId: UUID) {
        val alert = alertRefRepo.findById(alertId)
            .orElseThrow { NoSuchElementException("Alerta não encontrado: $alertId") }
        alertRefRepo.save(alert.copy(acknowledged = true))
    }
}
