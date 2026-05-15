package com.gymvision.app.ui.session

import android.content.Intent
import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.CreateSessionRequest
import com.gymvision.app.model.SessionSummary
import com.gymvision.app.ui.camera.CameraActivity
import kotlinx.coroutines.launch

class SessionListActivity : AppCompatActivity() {

    private val prefs by lazy { getSharedPreferences("gymvision_prefs", MODE_PRIVATE) }
    private val studentId get() = prefs.getString("user_id", "") ?: ""
    private val academyId get() = prefs.getString("academy_id", "") ?: ""
    private val sessions = mutableListOf<SessionSummary>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(resources.getIdentifier("activity_session_list", "layout", packageName))

        title = "Minhas Sessões — ${prefs.getString("user_name", "")}"

        val recyclerView = findViewById<RecyclerView>(R.id.rvSessions)
        recyclerView.layoutManager = LinearLayoutManager(this)

        val adapter = SessionAdapter(sessions) { session ->
            // Retomar sessão ativa
            openCamera(session.exerciseType, session.id)
        }
        recyclerView.adapter = adapter

        findViewById<Button>(R.id.btnNewSession).setOnClickListener {
            showNewSessionDialog { exerciseType ->
                lifecycleScope.launch {
                    runCatching {
                        val response = ApiClient.sessionApi.create(
                            CreateSessionRequest(studentId, academyId, exerciseType)
                        )
                        if (response.isSuccessful) {
                            val session = response.body()?.data!!
                            openCamera(exerciseType, session.id)
                        }
                    }.onFailure { e ->
                        Toast.makeText(this@SessionListActivity, "Erro: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }

        loadSessions(adapter)
    }

    private fun loadSessions(adapter: SessionAdapter) {
        lifecycleScope.launch {
            runCatching {
                val response = ApiClient.sessionApi.listByStudent(studentId)
                if (response.isSuccessful) {
                    sessions.clear()
                    sessions.addAll(response.body()?.data ?: emptyList())
                    adapter.notifyDataSetChanged()
                }
            }
        }
    }

    private fun showNewSessionDialog(onConfirm: (String) -> Unit) {
        val exercises = arrayOf("SQUAT", "DEADLIFT", "LUNGE")
        AlertDialog.Builder(this)
            .setTitle("Qual exercício?")
            .setItems(exercises) { _, which -> onConfirm(exercises[which]) }
            .show()
    }

    private fun openCamera(exerciseType: String, sessionId: String) {
        startActivity(Intent(this, CameraActivity::class.java).apply {
            putExtra("exerciseType", exerciseType)
            putExtra("sessionId", sessionId)
            putExtra("studentId", studentId)
            putExtra("academyId", academyId)
        })
    }
}

class SessionAdapter(
    private val items: List<SessionSummary>,
    private val onClick: (SessionSummary) -> Unit
) : RecyclerView.Adapter<SessionAdapter.VH>() {

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val tvTitle: TextView = view.findViewById(android.R.id.text1)
        val tvSub:   TextView = view.findViewById(android.R.id.text2)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val view = LayoutInflater.from(parent.context)
            .inflate(android.R.layout.simple_list_item_2, parent, false)
        return VH(view)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val s = items[position]
        holder.tvTitle.text = "${s.exerciseType} — ${s.status}"
        holder.tvSub.text = "Score: ${String.format("%.0f", s.avgScore)} | ${s.totalReps} reps | ${s.alertCount} alertas"
        if (s.status == "ACTIVE") holder.itemView.setOnClickListener { onClick(s) }
    }

    override fun getItemCount() = items.size
}
