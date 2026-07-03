package com.gymvision.app.api

import android.content.Context
import android.content.SharedPreferences
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.gymvision.app.model.AuthResponse
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {

    private val BASE_URL = "http://${com.gymvision.app.BuildConfig.API_HOST}:8090/"

    private lateinit var prefs: SharedPreferences
    private val gson = Gson()

    // Emitido quando o refresh token também expira — a UI deve voltar para o login.
    private val _sessionExpired = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val sessionExpired: SharedFlow<Unit> = _sessionExpired

    fun init(context: Context) {
        prefs = context.getSharedPreferences("gymvision_prefs", Context.MODE_PRIVATE)
    }

    fun saveTokens(accessToken: String, refreshToken: String) {
        prefs.edit()
            .putString("access_token", accessToken)
            .putString("refresh_token", refreshToken)
            .apply()
    }

    fun getAccessToken(): String? = prefs.getString("access_token", null)
    fun getRefreshToken(): String? = prefs.getString("refresh_token", null)
    fun clearTokens() = prefs.edit().clear().apply()

    fun saveUserInfo(userId: String, userName: String, userRole: String, academyId: String?) {
        prefs.edit()
            .putString("user_id", userId)
            .putString("user_name", userName)
            .putString("user_role", userRole)
            .putString("academy_id", academyId ?: "")
            .apply()
    }

    fun getUserId(): String? = prefs.getString("user_id", null)
    fun getUserName(): String? = prefs.getString("user_name", null)
    fun getUserRole(): String? = prefs.getString("user_role", null)
    fun getAcademyId(): String? = prefs.getString("academy_id", null)

    /** Cliente "puro", sem auth interceptor/authenticator — usado só para o /auth/refresh. */
    private val refreshHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .build()
    }

    /** Renova o access token automaticamente quando uma chamada retorna 401. */
    private val tokenAuthenticator = Authenticator { _, response ->
        if (responseCount(response) >= 2) return@Authenticator null

        synchronized(this) {
            val failedToken = response.request.header("Authorization")?.removePrefix("Bearer ")
            val currentAccess = getAccessToken()

            // Outra requisição já renovou o token enquanto esperávamos o lock.
            if (currentAccess != null && currentAccess != failedToken) {
                return@synchronized response.request.newBuilder()
                    .header("Authorization", "Bearer $currentAccess")
                    .build()
            }

            val refreshToken = getRefreshToken() ?: return@synchronized null

            val body = """{"refreshToken":"$refreshToken"}"""
                .toRequestBody("application/json".toMediaTypeOrNull())
            val request = Request.Builder()
                .url(BASE_URL + "api/v1/auth/refresh")
                .post(body)
                .build()

            return@synchronized runCatching {
                refreshHttpClient.newCall(request).execute().use { resp ->
                    if (!resp.isSuccessful) return@use null
                    val json = resp.body?.string() ?: return@use null
                    val data = JsonParser.parseString(json).asJsonObject.getAsJsonObject("data")
                        ?: return@use null
                    val auth = gson.fromJson(data, AuthResponse::class.java)
                    saveTokens(auth.accessToken, auth.refreshToken)
                    response.request.newBuilder()
                        .header("Authorization", "Bearer ${auth.accessToken}")
                        .build()
                }
            }.getOrNull().also { renewed ->
                if (renewed == null) {
                    clearTokens()
                    _sessionExpired.tryEmit(Unit)
                }
            }
        }
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }

    private val httpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val token = getAccessToken()
                val request = if (token != null) {
                    chain.request().newBuilder()
                        .header("Authorization", "Bearer $token")
                        .build()
                } else chain.request()
                chain.proceed(request)
            }
            .authenticator(tokenAuthenticator)
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            })
            .build()
    }

    private val retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
    }

    val authApi: AuthApi by lazy { retrofit.create(AuthApi::class.java) }
    val poseApi: PoseApi by lazy { retrofit.create(PoseApi::class.java) }
    val sessionApi: SessionApi by lazy { retrofit.create(SessionApi::class.java) }
    val userApi: UserApi by lazy { retrofit.create(UserApi::class.java) }
    val analyticsApi: AnalyticsApi by lazy { retrofit.create(AnalyticsApi::class.java) }
    val workoutPlanApi: WorkoutPlanApi by lazy { retrofit.create(WorkoutPlanApi::class.java) }
}
