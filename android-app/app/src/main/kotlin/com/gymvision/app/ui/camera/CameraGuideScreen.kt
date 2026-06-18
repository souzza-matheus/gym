package com.gymvision.app.ui.camera

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gymvision.app.ui.components.exerciseLabel

@Composable
fun CameraGuideScreen(
    exerciseType: String,
    onStart: () -> Unit,
    onSkip: () -> Unit,
) {
    val infiniteTransition = rememberInfiniteTransition(label = "phone_anim")
    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = -90f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "phone_rotation",
    )

    val tips = when (exerciseType.uppercase()) {
        "SQUAT", "LUNGE"         -> listOf(
            "Posicione o celular de lado (horizontal)",
            "Câmera na altura do quadril, a ~2 metros",
            "Garanta que joelhos e tornozelos estejam visíveis",
            "Evite obstruções entre você e a câmera",
        )
        "DEADLIFT", "BENT_OVER_ROW" -> listOf(
            "Posicione o celular de lado (horizontal)",
            "Câmera na altura do quadril, a ~2 metros",
            "Perfil lateral dá a melhor visão do tronco",
            "Toda a coluna deve estar visível",
        )
        "BENCH_PRESS"            -> listOf(
            "Câmera pode ser frontal ou lateral",
            "Posicione a ~1,5 metros da bancada",
            "Certifique-se que ombros e cotovelos aparecem",
            "Evite ângulos de cima para baixo",
        )
        else                     -> listOf(
            "Posicione o celular lateralmente",
            "Câmera na altura do quadril",
            "Corpo inteiro deve estar visível",
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(modifier = Modifier.height(32.dp))
            Text(
                text = "Como posicionar a câmera",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )
            Text(
                text = exerciseLabel(exerciseType),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
        }

        // Ícone animado do celular girando para posição lateral
        Box(
            modifier = Modifier
                .size(160.dp)
                .background(MaterialTheme.colorScheme.primaryContainer, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Filled.PhoneAndroid,
                contentDescription = null,
                modifier = Modifier
                    .size(80.dp)
                    .rotate(rotation),
                tint = MaterialTheme.colorScheme.primary,
            )
        }

        // Dicas
        Surface(
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surfaceVariant,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                tips.forEach { tip ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Filled.CheckCircle,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(tip, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Button(
                onClick = onStart,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
            ) {
                Text("Entendido — Iniciar sessão", fontSize = 16.sp)
            }
            TextButton(onClick = onSkip) {
                Text("Pular", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
