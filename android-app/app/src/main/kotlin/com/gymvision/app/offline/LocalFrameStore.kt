package com.gymvision.app.offline

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.google.gson.Gson
import com.gymvision.app.model.Landmark

/**
 * Armazenamento local de frames pendentes de sincronização.
 * Usa SQLite diretamente (sem Room) para evitar processamento de annotations.
 *
 * Schema:
 *   pending_frames(id, session_id, student_id, academy_id, exercise_type,
 *                  frame_seq, landmarks_json, score, phase, created_at, synced)
 */
class LocalFrameStore(context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {

    private val gson = Gson()

    data class PendingFrame(
        val id: Long = 0,
        val sessionId: String,
        val studentId: String,
        val academyId: String,
        val exerciseType: String,
        val frameSeq: Int,
        val landmarks: List<Landmark>,
        val score: Float,
        val phase: String,
        val createdAt: Long = System.currentTimeMillis(),
        val synced: Boolean = false,
    )

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE IF NOT EXISTS pending_frames (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    TEXT    NOT NULL,
                student_id    TEXT    NOT NULL,
                academy_id    TEXT    NOT NULL,
                exercise_type TEXT    NOT NULL,
                frame_seq     INTEGER NOT NULL,
                landmarks_json TEXT   NOT NULL,
                score         REAL    NOT NULL DEFAULT 0,
                phase         TEXT    NOT NULL DEFAULT 'UNKNOWN',
                created_at    INTEGER NOT NULL,
                synced        INTEGER NOT NULL DEFAULT 0
            )
        """.trimIndent())
        db.execSQL("CREATE INDEX idx_session ON pending_frames(session_id, synced)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS pending_frames")
        onCreate(db)
    }

    fun insert(frame: PendingFrame) {
        val cv = ContentValues().apply {
            put("session_id",     frame.sessionId)
            put("student_id",     frame.studentId)
            put("academy_id",     frame.academyId)
            put("exercise_type",  frame.exerciseType)
            put("frame_seq",      frame.frameSeq)
            put("landmarks_json", gson.toJson(frame.landmarks))
            put("score",          frame.score)
            put("phase",          frame.phase)
            put("created_at",     frame.createdAt)
            put("synced",         0)
        }
        writableDatabase.insert("pending_frames", null, cv)
    }

    /** Retorna frames não sincronizados ordenados por sessão e sequência. */
    fun unsyncedFrames(limit: Int = 200): List<PendingFrame> {
        val result = mutableListOf<PendingFrame>()
        val cursor = readableDatabase.rawQuery(
            "SELECT * FROM pending_frames WHERE synced = 0 ORDER BY session_id, frame_seq LIMIT ?",
            arrayOf(limit.toString()),
        )
        cursor.use {
            while (it.moveToNext()) {
                val landmarksType = object : com.google.gson.reflect.TypeToken<List<Landmark>>() {}.type
                result.add(PendingFrame(
                    id           = it.getLong(it.getColumnIndexOrThrow("id")),
                    sessionId    = it.getString(it.getColumnIndexOrThrow("session_id")),
                    studentId    = it.getString(it.getColumnIndexOrThrow("student_id")),
                    academyId    = it.getString(it.getColumnIndexOrThrow("academy_id")),
                    exerciseType = it.getString(it.getColumnIndexOrThrow("exercise_type")),
                    frameSeq     = it.getInt(it.getColumnIndexOrThrow("frame_seq")),
                    landmarks    = gson.fromJson(it.getString(it.getColumnIndexOrThrow("landmarks_json")), landmarksType),
                    score        = it.getFloat(it.getColumnIndexOrThrow("score")),
                    phase        = it.getString(it.getColumnIndexOrThrow("phase")),
                    createdAt    = it.getLong(it.getColumnIndexOrThrow("created_at")),
                ))
            }
        }
        return result
    }

    fun markSynced(ids: List<Long>) {
        if (ids.isEmpty()) return
        val placeholders = ids.joinToString(",") { "?" }
        writableDatabase.execSQL(
            "UPDATE pending_frames SET synced = 1 WHERE id IN ($placeholders)",
            ids.map { it.toString() }.toTypedArray(),
        )
    }

    fun pendingCount(): Int {
        val cursor = readableDatabase.rawQuery(
            "SELECT COUNT(*) FROM pending_frames WHERE synced = 0", null
        )
        return cursor.use { if (it.moveToFirst()) it.getInt(0) else 0 }
    }

    fun deleteOldSynced(olderThanMs: Long = 7 * 24 * 60 * 60 * 1000L) {
        val cutoff = System.currentTimeMillis() - olderThanMs
        writableDatabase.execSQL(
            "DELETE FROM pending_frames WHERE synced = 1 AND created_at < ?",
            arrayOf(cutoff.toString()),
        )
    }

    companion object {
        private const val DB_NAME    = "gymvision_offline.db"
        private const val DB_VERSION = 1
    }
}
