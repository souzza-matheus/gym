package com.gymvision.app.ui.navigation

object Routes {
    const val LOGIN = "login"
    const val MAIN = "main"

    const val SESSIONS       = "sessions"
    const val PROGRESS       = "progress"
    const val ACHIEVEMENTS   = "achievements"
    const val PROFILE        = "profile"
    const val VIDEO_TEST     = "video_test"
    const val WORKOUT_PLAN   = "workout_plan"

    // Rotas exclusivas de professor / admin
    const val NOTIFICATIONS  = "notifications"
    const val MANAGE_PLANS   = "manage_plans"

    const val CAMERA       = "camera/{sessionId}/{exerciseType}/{studentId}/{academyId}"
    const val CAMERA_GUIDE = "camera_guide/{sessionId}/{exerciseType}/{studentId}/{academyId}"
    const val SESSION_DETAIL = "session_detail/{sessionId}"

    fun camera(sessionId: String, exerciseType: String, studentId: String, academyId: String) =
        "camera/$sessionId/$exerciseType/$studentId/$academyId"

    fun cameraGuide(sessionId: String, exerciseType: String, studentId: String, academyId: String) =
        "camera_guide/$sessionId/$exerciseType/$studentId/$academyId"

    fun sessionDetail(sessionId: String) = "session_detail/$sessionId"
}
