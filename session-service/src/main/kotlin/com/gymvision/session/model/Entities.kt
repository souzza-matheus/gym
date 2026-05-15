package com.gymvision.session.model

import jakarta.persistence.*
import java.time.Instant
import java.util.UUID

enum class ExerciseType { SQUAT, DEADLIFT, LUNGE, UNKNOWN }
enum class SessionStatus { ACTIVE, COMPLETED, CANCELLED }

@Entity
@Table(name = "sessions")
data class Session(
    @Id val id: UUID = UUID.randomUUID(),
    @Column(name = "student_id", nullable = false) val studentId: UUID,
    @Column(name = "academy_id", nullable = false) val academyId: UUID,
    @Enumerated(EnumType.STRING) val exerciseType: ExerciseType = ExerciseType.UNKNOWN,
    @Enumerated(EnumType.STRING) var status: SessionStatus = SessionStatus.ACTIVE,
    var avgScore: Double = 0.0,
    var totalReps: Int = 0,
    var alertCount: Int = 0,
    @Column(name = "started_at") val startedAt: Instant = Instant.now(),
    @Column(name = "ended_at") var endedAt: Instant? = null
)

@Entity
@Table(name = "reps")
data class Rep(
    @Id val id: UUID = UUID.randomUUID(),
    @Column(name = "session_id", nullable = false) val sessionId: UUID,
    val repNumber: Int,
    val score: Double,
    val phase: String,
    val errors: String = "[]",   // JSON
    val hasAlert: Boolean = false,
    @Column(name = "recorded_at") val recordedAt: Instant = Instant.now()
)

@Entity
@Table(name = "alerts_ref")
data class AlertRef(
    @Id val id: UUID = UUID.randomUUID(),
    @Column(name = "session_id") val sessionId: UUID,
    val errorType: String,
    val riskLevel: String,
    val description: String,
    var acknowledged: Boolean = false,
    @Column(name = "created_at") val createdAt: Instant = Instant.now()
)
