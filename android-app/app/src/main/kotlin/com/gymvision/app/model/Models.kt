package com.gymvision.app.model

import com.google.gson.annotations.SerializedName

// ── Auth ──────────────────────────────────────────────────────────────────────

data class LoginRequest(val email: String, val password: String)

data class AuthResponse(
    val accessToken: String,
    val refreshToken: String,
    val tokenType: String = "Bearer",
    val expiresIn: Long = 900,
    val user: UserDto
)

data class UserDto(
    val id: String,
    val name: String,
    val email: String,
    val role: String,
    val academyId: String?,
    val academyName: String? = null,
)

data class ApiResponse<T>(
    val success: Boolean,
    val data: T?,
    val message: String?
)

// ── Pose + Analyzer ───────────────────────────────────────────────────────────

data class Landmark(
    @SerializedName("landmark_type") val landmarkType: Int,
    val x: Float,
    val y: Float,
    val z: Float,
    val visibility: Float
)

data class JointAngles(
    @SerializedName("left_knee")     val leftKnee: Float?,
    @SerializedName("right_knee")    val rightKnee: Float?,
    @SerializedName("left_hip")      val leftHip: Float?,
    @SerializedName("right_hip")     val rightHip: Float?,
    @SerializedName("back_angle")    val backAngle: Float?,
    @SerializedName("hip_hinge_angle") val hipHingeAngle: Float?
)

data class DetectedError(
    @SerializedName("error_type")  val errorType: String,
    @SerializedName("risk_level")  val riskLevel: String,   // LOW | MEDIUM | HIGH
    val description: String,
    @SerializedName("joint_angle") val jointAngle: Float? = null
)

data class ExerciseAnalysis(
    @SerializedName("exercise_type") val exerciseType: String,
    val phase: String,
    val score: Float,
    @SerializedName("joint_angles")  val jointAngles: JointAngles,
    val errors: List<DetectedError>,
    @SerializedName("has_alert")     val hasAlert: Boolean,
    @SerializedName("analysis_ms")   val analysisMs: Float
)

data class PoseAnalysisResponse(
    val landmarks: List<Landmark>,
    @SerializedName("landmark_count") val landmarkCount: Int,
    @SerializedName("inference_ms")   val inferenceMs: Float,
    @SerializedName("frame_width")    val frameWidth: Int,
    @SerializedName("frame_height")   val frameHeight: Int,
    val analysis: ExerciseAnalysis?
)

data class ExerciseDetectionResponse(
    @SerializedName("exercise_type") val exerciseType: String,
    val confidence: Float,
    val reason: String,
    val landmarks: List<Landmark>,
    @SerializedName("landmark_count") val landmarkCount: Int,
)

// ── Session ───────────────────────────────────────────────────────────────────

data class CreateSessionRequest(
    val studentId: String,
    val academyId: String,
    val exerciseType: String
)

data class SessionSummary(
    val id: String,
    val studentId: String,
    val academyId: String,
    val exerciseType: String,
    val status: String,
    val avgScore: Double,
    val totalReps: Int,
    val alertCount: Int,
    val startedAt: String,
    val endedAt: String?
)

// ── WebSocket ─────────────────────────────────────────────────────────────────

data class WsAlert(
    val sessionId: String,
    val studentId: String,
    val exerciseType: String,
    val errorType: String,
    val riskLevel: String,
    val description: String,
    val score: Float,
    val phase: String,
    val timestamp: String
)

data class WsAnalysis(
    val studentId: String,
    val score: Float,
    val phase: String,
    val frameSeq: Int
)

// ── Analytics ─────────────────────────────────────────────────────────────────

data class WeeklyProgress(
    val week: String,
    @SerializedName("avg_score")      val avgScore: Double,
    @SerializedName("dominant_error") val dominantError: String?,
    @SerializedName("sessions_count") val sessionsCount: Int
)

data class OverallStats(
    @SerializedName("total_sessions") val totalSessions: Int,
    @SerializedName("total_reps")     val totalReps: Int,
    @SerializedName("avg_score")      val avgScore: Double,
    @SerializedName("best_score")     val bestScore: Double
)

data class TopError(
    val error: String,
    val count: Int
)

data class SessionReport(
    @SerializedName("session_id")    val sessionId: String,
    @SerializedName("student_id")    val studentId: String,
    @SerializedName("academy_id")    val academyId: String,
    @SerializedName("exercise_type") val exerciseType: String,
    @SerializedName("avg_score")     val avgScore: Double,
    @SerializedName("total_reps")    val totalReps: Int,
    @SerializedName("alert_count")   val alertCount: Int,
    @SerializedName("dominant_error") val dominantError: String?,
    @SerializedName("duration_ms")   val durationMs: Long,
    @SerializedName("started_at")    val startedAt: String?,
    @SerializedName("ended_at")      val endedAt: String?
)

data class StudentAnalyticsResponse(
    @SerializedName("student_id")      val studentId: String,
    @SerializedName("weekly_progress") val weeklyProgress: List<WeeklyProgress>,
    @SerializedName("recent_sessions") val recentSessions: List<SessionReport>,
    @SerializedName("overall_stats")   val overallStats: OverallStats,
    @SerializedName("top_errors")      val topErrors: List<TopError>
)

// ── Gamificação ───────────────────────────────────────────────────────────────

data class Achievement(
    val key: String,
    val name: String,
    val description: String,
    val icon: String
)

data class LeaderboardEntry(
    val rank: Int,
    @SerializedName("student_id") val studentId: String,
    @SerializedName("avg_score")  val avgScore: Double,
    val sessions: Int,
    @SerializedName("total_reps") val totalReps: Int
)

data class LeaderboardResponse(
    @SerializedName("academy_id")  val academyId: String,
    val leaderboard: List<LeaderboardEntry>
)

data class GamificationResponse(
    @SerializedName("student_id")        val studentId: String,
    val points: Int,
    val level: Int,
    @SerializedName("next_level_points") val nextLevelPoints: Int,
    @SerializedName("streak_days")       val streakDays: Int,
    @SerializedName("total_sessions")    val totalSessions: Int,
    @SerializedName("clean_sessions")    val cleanSessions: Int,
    @SerializedName("total_reps")        val totalReps: Int,
    @SerializedName("best_score")        val bestScore: Double,
    val achievements: List<Achievement>
)

// ── Plano de treino ───────────────────────────────────────────────────────────

data class WorkoutPlanItem(
    val id: String,
    @SerializedName("exercise_type") val exerciseType: String,
    val sets: Int,
    @SerializedName("reps_per_set")  val repsPerSet: Int,
    @SerializedName("load_kg")       val loadKg: Double?,
    val notes: String?,
    @SerializedName("order_index")   val orderIndex: Int,
)

data class WorkoutPlan(
    val id: String,
    @SerializedName("student_id")   val studentId: String,
    @SerializedName("academy_id")   val academyId: String,
    @SerializedName("professor_id") val professorId: String,
    val name: String,
    @SerializedName("day_of_week")  val dayOfWeek: Int?,
    val active: Boolean,
    val items: List<WorkoutPlanItem>,
)

data class WorkoutPlanListResponse(val data: List<WorkoutPlan>)
