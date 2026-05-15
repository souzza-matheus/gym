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
    val academyId: String?
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
    @SerializedName("joint_angle") val jointAngle: Float?
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
