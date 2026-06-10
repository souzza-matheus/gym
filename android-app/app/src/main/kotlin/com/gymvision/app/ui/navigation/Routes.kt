package com.gymvision.app.ui.navigation

object Routes {
    const val LOGIN = "login"
    const val MAIN = "main"

    const val SESSIONS = "sessions"
    const val PROGRESS = "progress"
    const val PROFILE = "profile"

    const val CAMERA = "camera/{sessionId}/{exerciseType}/{studentId}/{academyId}"
    const val SESSION_DETAIL = "session_detail/{sessionId}"

    fun camera(sessionId: String, exerciseType: String, studentId: String, academyId: String) =
        "camera/$sessionId/$exerciseType/$studentId/$academyId"

    fun sessionDetail(sessionId: String) = "session_detail/$sessionId"
}
