package com.gymvision.app.api

import com.gymvision.app.model.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface AuthApi {
    @POST("api/v1/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<ApiResponse<AuthResponse>>

    @POST("api/v1/auth/refresh")
    suspend fun refresh(@Body body: Map<String, String>): Response<ApiResponse<AuthResponse>>

    @POST("api/v1/auth/logout")
    suspend fun logout(): Response<ApiResponse<Unit>>
}

interface PoseApi {
    @Multipart
    @POST("api/v1/pose/analyze")
    suspend fun analyze(
        @Part frame: MultipartBody.Part,
        @Part("exercise_type") exerciseType: RequestBody,
        @Part("session_id") sessionId: RequestBody,
        @Part("student_id") studentId: RequestBody,
        @Part("frame_seq") frameSeq: RequestBody,
        @Part("academy_id") academyId: RequestBody
    ): Response<PoseAnalysisResponse>

    @Multipart
    @POST("api/v1/pose/detect-exercise")
    suspend fun detectExercise(
        @Part frame: MultipartBody.Part,
        @Part("session_id") sessionId: RequestBody,
        @Part("student_id") studentId: RequestBody,
    ): Response<ExerciseDetectionResponse>
}

interface SessionApi {
    @POST("api/v1/sessions")
    suspend fun create(@Body request: CreateSessionRequest): Response<ApiResponse<SessionSummary>>

    @GET("api/v1/sessions/{id}")
    suspend fun get(@Path("id") id: String): Response<ApiResponse<SessionSummary>>

    @GET("api/v1/sessions/student/{studentId}")
    suspend fun listByStudent(@Path("studentId") studentId: String): Response<ApiResponse<List<SessionSummary>>>

    @POST("api/v1/sessions/{id}/end")
    suspend fun end(@Path("id") id: String): Response<ApiResponse<SessionSummary>>

    @GET("api/v1/sessions/{id}/summary")
    suspend fun summary(@Path("id") id: String): Response<ApiResponse<SessionSummary>>
}

interface UserApi {
    @GET("api/v1/users/me")
    suspend fun me(): Response<ApiResponse<UserDto>>

    @POST("api/v1/users/join-academy")
    suspend fun joinAcademy(@Body body: Map<String, String>): Response<ApiResponse<UserDto>>

    @GET("api/v1/users/me/export")
    suspend fun exportMyData(): Response<ApiResponse<Map<String, Any?>>>

    @DELETE("api/v1/users/me")
    suspend fun deleteMyAccount(): Response<Void>
}

interface WorkoutPlanApi {
    @GET("api/v1/workout-plans/student/{studentId}")
    suspend fun listByStudent(@Path("studentId") studentId: String): Response<ApiResponse<List<WorkoutPlan>>>
}

interface AnalyticsApi {
    @GET("api/v1/analytics/student/{studentId}")
    suspend fun studentAnalytics(
        @Path("studentId") studentId: String,
        @Query("weeks") weeks: Int = 8
    ): Response<StudentAnalyticsResponse>

    @GET("api/v1/analytics/session/{sessionId}/report")
    suspend fun sessionReport(@Path("sessionId") sessionId: String): Response<SessionReport>

    @GET("api/v1/analytics/gamification/{studentId}")
    suspend fun gamification(@Path("studentId") studentId: String): Response<GamificationResponse>

    @GET("api/v1/analytics/academy/{academyId}/leaderboard")
    suspend fun leaderboard(
        @Path("academyId") academyId: String,
        @Query("limit") limit: Int = 10
    ): Response<LeaderboardResponse>
}
