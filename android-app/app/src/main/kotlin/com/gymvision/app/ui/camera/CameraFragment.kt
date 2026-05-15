package com.gymvision.app.ui.camera

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.lifecycleScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.service.GymWebSocketService
import kotlinx.coroutines.launch
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * Fragment principal da câmera.
 * Recebe args: exerciseType, sessionId, studentId, academyId via Bundle.
 *
 * UI esperada no layout (fragment_camera.xml):
 *   - previewView: PreviewView
 *   - tvScore: TextView
 *   - tvPhase: TextView
 *   - tvErrors: TextView
 *   - tvLandmarks: TextView
 *   - cardAlert: CardView (visível quando hasAlert=true)
 *   - btnEndSession: Button
 */
class CameraFragment : Fragment() {

    private val viewModel: CameraViewModel by viewModels()
    private lateinit var cameraExecutor: ExecutorService

    private val exerciseType by lazy { arguments?.getString("exerciseType") ?: "SQUAT" }
    private val sessionId    by lazy { arguments?.getString("sessionId")    ?: "" }
    private val studentId    by lazy { arguments?.getString("studentId")    ?: "" }
    private val academyId    by lazy { arguments?.getString("academyId")    ?: "" }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        return inflater.inflate(
            resources.getIdentifier("fragment_camera", "layout", requireContext().packageName),
            container, false
        )
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        cameraExecutor = Executors.newSingleThreadExecutor()

        if (hasCameraPermission()) startCamera(view) else requestPermissions(arrayOf(Manifest.permission.CAMERA), 100)

        GymWebSocketService.connect(studentId, academyId)

        // Observa estado de análise
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.state.collect { state ->
                updateUi(view, state)
            }
        }

        // Alertas via WebSocket (backup do loop da câmera)
        viewLifecycleOwner.lifecycleScope.launch {
            GymWebSocketService.alerts.collect { alert ->
                if (alert.studentId == studentId) {
                    showAlertBanner(view, alert.description, alert.riskLevel)
                }
            }
        }

        // Botão encerrar sessão
        view.findViewById<View>(
            resources.getIdentifier("btnEndSession", "id", requireContext().packageName)
        )?.setOnClickListener { endSession() }
    }

    private fun startCamera(view: View) {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(requireContext())
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            val previewViewId = resources.getIdentifier("previewView", "id", requireContext().packageName)
            val previewView = view.findViewById<androidx.camera.view.PreviewView>(previewViewId)

            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }

            val imageAnalysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            imageAnalysis.setAnalyzer(cameraExecutor) { imageProxy ->
                viewModel.onFrame(imageProxy, exerciseType, sessionId, studentId)
            }

            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    viewLifecycleOwner,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageAnalysis
                )
            } catch (e: Exception) {
                Toast.makeText(requireContext(), "Erro ao iniciar câmera: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }, ContextCompat.getMainExecutor(requireContext()))
    }

    private fun updateUi(view: View, state: AnalysisUiState) {
        fun id(name: String) = resources.getIdentifier(name, "id", requireContext().packageName)
        view.findViewById<android.widget.TextView>(id("tvScore"))?.text = "${state.score.toInt()}/100"
        view.findViewById<android.widget.TextView>(id("tvPhase"))?.text = state.phase
        view.findViewById<android.widget.TextView>(id("tvLandmarks"))?.text = "${state.landmarkCount} pts"
        view.findViewById<android.widget.TextView>(id("tvErrors"))?.text =
            if (state.errors.isEmpty()) "✅ Postura correta" else state.errors.joinToString("\n")
        view.findViewById<View>(id("cardAlert"))?.visibility =
            if (state.hasAlert) View.VISIBLE else View.GONE
    }

    private fun showAlertBanner(view: View, description: String, riskLevel: String) {
        requireActivity().runOnUiThread {
            Toast.makeText(requireContext(), "⚠️ $description", Toast.LENGTH_LONG).show()
        }
    }

    private fun endSession() {
        lifecycleScope.launch {
            runCatching {
                ApiClient.sessionApi.end(sessionId)
                GymWebSocketService.disconnect()
                requireActivity().onBackPressedDispatcher.onBackPressed()
            }
        }
    }

    private fun hasCameraPermission() =
        ContextCompat.checkSelfPermission(requireContext(), Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    override fun onDestroyView() {
        super.onDestroyView()
        cameraExecutor.shutdown()
        GymWebSocketService.disconnect()
    }
}
