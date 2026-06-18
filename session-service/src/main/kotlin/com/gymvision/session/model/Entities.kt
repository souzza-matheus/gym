package com.gymvision.session.model

import jakarta.persistence.*
import java.time.Instant
import java.util.UUID

enum class ExerciseType { SQUAT, DEADLIFT, LUNGE, BENCH_PRESS, BENT_OVER_ROW, UNKNOWN }
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
    @Column(columnDefinition = "TEXT")
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

@Entity
@Table(name = "workout_plans")
data class WorkoutPlan(
    @Id val id: UUID = UUID.randomUUID(),
    @Column(name = "academy_id",   nullable = false) val academyId:   UUID,
    @Column(name = "student_id",   nullable = false) val studentId:   UUID,
    @Column(name = "professor_id", nullable = false) val professorId: UUID,
    @Column(nullable = false) val name: String,
    @Column(name = "day_of_week") val dayOfWeek: Int? = null,   // 1=Mon..7=Sun
    var active: Boolean = true,
    @Column(name = "created_at") val createdAt: Instant = Instant.now()
)

@Entity
@Table(name = "workout_plan_items")
data class WorkoutPlanItem(
    @Id val id: UUID = UUID.randomUUID(),
    @Column(name = "plan_id", nullable = false) val planId: UUID,
    @Column(name = "exercise_type", nullable = false) val exerciseType: String,
    val sets: Int = 3,
    @Column(name = "reps_per_set") val repsPerSet: Int = 10,
    @Column(name = "load_kg") val loadKg: Double? = null,
    val notes: String? = null,
    @Column(name = "order_index") val orderIndex: Int = 0
)
