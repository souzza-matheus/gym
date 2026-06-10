package com.gymvision.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.gymvision.app.api.ApiClient
import com.gymvision.app.ui.auth.LoginScreen
import com.gymvision.app.ui.camera.CameraScreen
import com.gymvision.app.ui.sessions.SessionDetailScreen

@Composable
fun AppNavHost() {
    val navController = rememberNavController()
    val startDestination = if (ApiClient.getAccessToken() != null) Routes.MAIN else Routes.LOGIN

    LaunchedEffect(Unit) {
        ApiClient.sessionExpired.collect {
            navController.navigate(Routes.LOGIN) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Routes.MAIN) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.MAIN) {
            MainScreen(rootNavController = navController)
        }

        composable(
            route = Routes.CAMERA,
            arguments = listOf(
                navArgument("sessionId") { type = NavType.StringType },
                navArgument("exerciseType") { type = NavType.StringType },
                navArgument("studentId") { type = NavType.StringType },
                navArgument("academyId") { type = NavType.StringType },
            )
        ) { backStackEntry ->
            CameraScreen(
                sessionId = backStackEntry.arguments?.getString("sessionId") ?: "",
                exerciseType = backStackEntry.arguments?.getString("exerciseType") ?: "SQUAT",
                studentId = backStackEntry.arguments?.getString("studentId") ?: "",
                academyId = backStackEntry.arguments?.getString("academyId") ?: "",
                onFinish = { navController.popBackStack() }
            )
        }

        composable(
            route = Routes.SESSION_DETAIL,
            arguments = listOf(navArgument("sessionId") { type = NavType.StringType })
        ) { backStackEntry ->
            SessionDetailScreen(
                sessionId = backStackEntry.arguments?.getString("sessionId") ?: "",
                onBack = { navController.popBackStack() }
            )
        }
    }
}
