package com.gymvision.app.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.EmojiEvents
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.gymvision.app.ui.achievements.AchievementsScreen
import com.gymvision.app.ui.profile.ProfileScreen
import com.gymvision.app.ui.progress.ProgressScreen
import com.gymvision.app.ui.sessions.SessionListScreen
import com.gymvision.app.ui.videotest.VideoTestScreen
import com.gymvision.app.ui.workoutplan.WorkoutPlanScreen

private data class BottomNavItem(val route: String, val label: String, val icon: ImageVector)

private val bottomNavItems = listOf(
    BottomNavItem(Routes.SESSIONS,      "Sessões",    Icons.Filled.FitnessCenter),
    BottomNavItem(Routes.WORKOUT_PLAN,  "Treino",     Icons.Filled.CalendarMonth),
    BottomNavItem(Routes.PROGRESS,      "Progresso",  Icons.Filled.TrendingUp),
    BottomNavItem(Routes.ACHIEVEMENTS,  "Conquistas", Icons.Filled.EmojiEvents),
    BottomNavItem(Routes.VIDEO_TEST,    "Testar",     Icons.Filled.VideoLibrary),
    BottomNavItem(Routes.PROFILE,       "Perfil",     Icons.Filled.Person),
)

@Composable
fun MainScreen(rootNavController: NavHostController) {
    val tabNavController = rememberNavController()

    Scaffold(
        bottomBar = {
            NavigationBar {
                val backStackEntry by tabNavController.currentBackStackEntryAsState()
                val currentRoute = backStackEntry?.destination?.route

                bottomNavItems.forEach { item ->
                    NavigationBarItem(
                        selected = currentRoute == item.route,
                        onClick = {
                            tabNavController.navigate(item.route) {
                                popUpTo(tabNavController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(item.icon, contentDescription = item.label) },
                        label = { Text(item.label) },
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = tabNavController,
            startDestination = Routes.SESSIONS,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Routes.SESSIONS) {
                SessionListScreen(
                    onOpenCamera = { sessionId, exerciseType, studentId, academyId ->
                        rootNavController.navigate(
                            Routes.cameraGuide(sessionId, exerciseType, studentId, academyId)
                        )
                    },
                    onOpenSessionDetail = { sessionId ->
                        rootNavController.navigate(Routes.sessionDetail(sessionId))
                    },
                )
            }
            composable(Routes.WORKOUT_PLAN) {
                WorkoutPlanScreen(
                    onNavigateToCamera = { sessionId, exerciseType, studentId, academyId ->
                        rootNavController.navigate(
                            Routes.cameraGuide(sessionId, exerciseType, studentId, academyId)
                        )
                    }
                )
            }
            composable(Routes.PROGRESS)      { ProgressScreen() }
            composable(Routes.ACHIEVEMENTS)  { AchievementsScreen() }
            composable(Routes.PROFILE) {
                ProfileScreen(
                    onLoggedOut = {
                        rootNavController.navigate(Routes.LOGIN) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                )
            }
            composable(Routes.VIDEO_TEST)   { VideoTestScreen() }
        }
    }
}
