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
    /**
     * Envia frame JPEG + exercise_type e recebe landmarks + análise completa.
     * Um único endpoint — pose e analyzer integrados.
     */
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
