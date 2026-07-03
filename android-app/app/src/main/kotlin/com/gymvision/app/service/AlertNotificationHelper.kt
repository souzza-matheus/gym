package com.gymvision.app.service

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.gymvision.app.R
import com.gymvision.app.model.WsAlert
import com.gymvision.app.ui.components.exerciseLabel
import java.util.concurrent.atomic.AtomicInteger

/**
 * Gerencia notificações push e padrões de vibração para alertas de postura.
 *
 * Padrões de vibração por severidade/risco (todos sem repetição, -1 no repeat):
 *   CRITICAL           → 3 pulsos longos + máxima amplitude (risco imediato de lesão)
 *   WARNING + HIGH     → 2 pulsos médios
 *   WARNING + MEDIUM   → 2 pulsos curtos
 *   WARNING + LOW      → 1 toque leve
 */
object AlertNotificationHelper {

    private const val CHANNEL_CRITICAL = "gym_alert_critical"
    private const val CHANNEL_WARNING  = "gym_alert_warning"

    // Timings: [silêncio_inicial, vibra, pausa, vibra, pausa, vibra...]
    private val PATTERN_CRITICAL = longArrayOf(0, 450, 120, 450, 120, 800)
    private val AMP_CRITICAL     = intArrayOf(0, 255,   0, 255,   0, 255)

    private val PATTERN_HIGH     = longArrayOf(0, 280, 120, 280)
    private val AMP_HIGH         = intArrayOf(0, 200,   0, 200)

    private val PATTERN_MEDIUM   = longArrayOf(0, 160, 100, 160)
    private val AMP_MEDIUM       = intArrayOf(0, 150,   0, 150)

    private val PATTERN_LOW      = longArrayOf(0, 80)
    private val AMP_LOW          = intArrayOf(0, 100)

    private lateinit var appContext: Context
    private val notifId = AtomicInteger(2000)

    fun init(context: Context) {
        appContext = context.applicationContext
        createChannels()
    }

    private fun createChannels() {
        val nm = appContext.getSystemService(NotificationManager::class.java)

        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_CRITICAL,
                "Alertas Críticos",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Erros graves de postura — alto risco de lesão"
                enableVibration(false) // vibração controlada manualmente via VibrationEffect
                setShowBadge(true)
            }
        )

        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_WARNING,
                "Avisos de Postura",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Avisos e erros de risco moderado ou baixo"
                enableVibration(false)
                setShowBadge(true)
            }
        )
    }

    fun notify(alert: WsAlert) {
        val isCritical = alert.severity?.uppercase() == "CRITICAL"
        val channel    = if (isCritical) CHANNEL_CRITICAL else CHANNEL_WARNING
        val priority   = if (isCritical) NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT

        val title = if (isCritical) "Alerta CRÍTICO — ${exerciseLabel(alert.exerciseType)}"
                    else "Aviso — ${exerciseLabel(alert.exerciseType)}"
        val text  = "${alert.description} • score: ${(alert.score * 100).toInt()}%"

        val notification = NotificationCompat.Builder(appContext, channel)
            .setSmallIcon(R.drawable.ic_notification_alert)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(priority)
            .setAutoCancel(true)
            // Vibração desabilitada no builder — usamos VibrationEffect para padrão customizado
            .setVibrate(longArrayOf(0))
            .build()

        val nm = NotificationManagerCompat.from(appContext)
        val hasPermission = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ActivityCompat.checkSelfPermission(appContext, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED

        if (hasPermission) {
            nm.notify(notifId.getAndIncrement(), notification)
        }

        vibrate(alert.severity, alert.riskLevel)
    }

    private fun vibrate(severity: String?, riskLevel: String) {
        val vibrator = getVibrator() ?: return
        if (!vibrator.hasVibrator()) return

        val (timings, amplitudes) = when {
            severity?.uppercase() == "CRITICAL"   -> PATTERN_CRITICAL to AMP_CRITICAL
            riskLevel.uppercase() == "HIGH"        -> PATTERN_HIGH     to AMP_HIGH
            riskLevel.uppercase() == "MEDIUM"      -> PATTERN_MEDIUM   to AMP_MEDIUM
            else                                   -> PATTERN_LOW      to AMP_LOW
        }

        vibrator.vibrate(VibrationEffect.createWaveform(timings, amplitudes, -1))
    }

    private fun getVibrator(): Vibrator? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        appContext.getSystemService(VibratorManager::class.java)?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        appContext.getSystemService(Vibrator::class.java)
    }
}
