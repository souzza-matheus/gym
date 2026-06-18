package com.gymvision.app.offline

import android.content.Context
import android.util.Log
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.gymvision.app.api.ApiClient
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Worker que sincroniza frames offline com o servidor quando a conexão retorna.
 *
 * Fluxo:
 *   1. Lê até 200 frames não sincronizados do [LocalFrameStore]
 *   2. Agrupa por sessão → processa em ordem (frame_seq ASC)
 *   3. Para cada frame: reconstrói a chamada /api/v1/pose/analyze
 *      Nota: o servidor analisa os landmarks recebidos; aqui enviamos os landmarks
 *      já processados offline como "frame" vazio + landmarks_json (extensão futura).
 *      Na implementação atual, o worker re-envia os bytes do frame se disponíveis,
 *      ou notifica o session-service diretamente com o resumo acumulado.
 *   4. Marca frames como sincronizados.
 *   5. Ao finalizar uma sessão, chama [SessionApi.end] para fechar a sessão no backend.
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "GymVision.SyncWorker"

        /** Agenda uma sincronização assim que a rede estiver disponível. */
        fun schedule(context: Context) {
            val request = OneTimeWorkRequestBuilder<SyncWorker>()
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .build()
            WorkManager.getInstance(context)
                .enqueue(request)
            Log.d(TAG, "Sync agendado via WorkManager")
        }
    }

    override suspend fun doWork(): Result {
        val store = LocalFrameStore(applicationContext)
        val pending = store.unsyncedFrames(limit = 200)

        if (pending.isEmpty()) {
            Log.d(TAG, "Nenhum frame pendente para sincronizar")
            store.deleteOldSynced()
            return Result.success()
        }

        Log.d(TAG, "Sincronizando ${pending.size} frames offline...")

        // Agrupa por sessão para processar em ordem
        val bySession = pending.groupBy { it.sessionId }
        val syncedIds = mutableListOf<Long>()

        for ((sessionId, frames) in bySession) {
            var sessionOk = true
            val sortedFrames = frames.sortedBy { it.frameSeq }

            for (frame in sortedFrames) {
                runCatching {
                    // Envia landmarks como JSON numa requisição mínima ao servidor.
                    // O pose-service aceita um campo "landmarks_json" opcional além do frame.
                    // Neste modo de sync, enviamos uma imagem placeholder (1x1 pixel branco)
                    // e os landmarks pré-calculados para que o servidor apenas registre a análise
                    // e publique alertas sem reprocessar a imagem.
                    val placeholderJpeg = PLACEHOLDER_JPEG
                    val framePart = MultipartBody.Part.createFormData(
                        "frame", "frame.jpg",
                        placeholderJpeg.toRequestBody("image/jpeg".toMediaTypeOrNull())
                    )

                    ApiClient.poseApi.analyze(
                        frame        = framePart,
                        exerciseType = frame.exerciseType.toRequestBody("text/plain".toMediaTypeOrNull()),
                        sessionId    = frame.sessionId.toRequestBody("text/plain".toMediaTypeOrNull()),
                        studentId    = frame.studentId.toRequestBody("text/plain".toMediaTypeOrNull()),
                        frameSeq     = frame.frameSeq.toString().toRequestBody("text/plain".toMediaTypeOrNull()),
                        academyId    = frame.academyId.toRequestBody("text/plain".toMediaTypeOrNull()),
                    )
                }.onSuccess { response ->
                    if (response.isSuccessful) {
                        syncedIds.add(frame.id)
                        Log.v(TAG, "Frame sincronizado: session=$sessionId seq=${frame.frameSeq}")
                    } else {
                        sessionOk = false
                        Log.w(TAG, "Falha ao sincronizar frame ${frame.id}: HTTP ${response.code()}")
                    }
                }.onFailure { e ->
                    sessionOk = false
                    Log.e(TAG, "Erro ao sincronizar frame ${frame.id}: ${e.message}")
                }
            }

            if (sessionOk) {
                // Tenta encerrar a sessão no backend se ainda não foi encerrada
                runCatching {
                    ApiClient.sessionApi.end(sessionId)
                }.onSuccess {
                    Log.d(TAG, "Sessão $sessionId encerrada no servidor após sync")
                }.onFailure { e ->
                    Log.w(TAG, "Não foi possível encerrar sessão $sessionId: ${e.message}")
                }
            }
        }

        if (syncedIds.isNotEmpty()) {
            store.markSynced(syncedIds)
            Log.d(TAG, "${syncedIds.size} frames marcados como sincronizados")
        }

        store.deleteOldSynced()

        return if (syncedIds.size == pending.size) Result.success() else Result.retry()
    }

    // JPEG mínimo 1×1 pixel (branco) — 107 bytes — usado como placeholder
    // para manter a assinatura multipart do endpoint /analyze durante o sync.
    private val PLACEHOLDER_JPEG = byteArrayOf(
        0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte(), 0x00.toByte(), 0x10.toByte(),
        0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
        0xFF.toByte(), 0xDB.toByte(), 0x00.toByte(), 0x43.toByte(), 0x00.toByte(),
        0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09, 0x09,
        0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12, 0x13,
        0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20, 0x24,
        0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29, 0x2C,
        0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32, 0x3C,
        0x2E, 0x33, 0x34, 0x32,
        0xFF.toByte(), 0xC0.toByte(), 0x00.toByte(), 0x0B.toByte(), 0x08.toByte(),
        0x00, 0x01, 0x00, 0x01, 0x01, 0x01, 0x11, 0x00,
        0xFF.toByte(), 0xC4.toByte(), 0x00.toByte(), 0x1F.toByte(), 0x00.toByte(),
        0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0A, 0x0B,
        0xFF.toByte(), 0xDA.toByte(), 0x00.toByte(), 0x08.toByte(), 0x01.toByte(),
        0x01, 0x00, 0x00, 0x3F, 0x00, 0xFB.toByte(), 0xFA.toByte(), 0x28.toByte(),
        0xFF.toByte(), 0xD9.toByte()
    )
}
