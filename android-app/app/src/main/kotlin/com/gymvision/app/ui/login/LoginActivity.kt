package com.gymvision.app.ui.login

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.gymvision.app.api.ApiClient
import com.gymvision.app.model.LoginRequest
import com.gymvision.app.ui.session.SessionListActivity
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(resources.getIdentifier("activity_login", "layout", packageName))

        // Se já tem token, vai direto para a lista de sessões
        if (ApiClient.getAccessToken() != null) {
            goToMain()
            return
        }

        val etEmail    = findViewById<EditText>(R.id.etEmail)
        val etPassword = findViewById<EditText>(R.id.etPassword)
        val btnLogin   = findViewById<Button>(R.id.btnLogin)
        val progress   = findViewById<ProgressBar>(R.id.progressBar)
        val tvError    = findViewById<TextView>(R.id.tvError)

        btnLogin.setOnClickListener {
            val email = etEmail.text.toString().trim()
            val password = etPassword.text.toString()

            if (email.isEmpty() || password.isEmpty()) {
                tvError.text = "Preencha e-mail e senha"
                tvError.visibility = View.VISIBLE
                return@setOnClickListener
            }

            progress.visibility = View.VISIBLE
            btnLogin.isEnabled = false
            tvError.visibility = View.GONE

            lifecycleScope.launch {
                runCatching {
                    val response = ApiClient.authApi.login(LoginRequest(email, password))
                    if (response.isSuccessful && response.body()?.success == true) {
                        val data = response.body()!!.data!!
                        ApiClient.saveTokens(data.accessToken, data.refreshToken)
                        // Salva userId e academyId nas prefs
                        getSharedPreferences("gymvision_prefs", MODE_PRIVATE).edit()
                            .putString("user_id", data.user.id)
                            .putString("user_name", data.user.name)
                            .putString("user_role", data.user.role)
                            .putString("academy_id", data.user.academyId ?: "")
                            .apply()
                        goToMain()
                    } else {
                        tvError.text = response.body()?.message ?: "Credenciais inválidas"
                        tvError.visibility = View.VISIBLE
                    }
                }.onFailure { e ->
                    tvError.text = "Erro de conexão: ${e.message}"
                    tvError.visibility = View.VISIBLE
                }

                progress.visibility = View.GONE
                btnLogin.isEnabled = true
            }
        }
    }

    private fun goToMain() {
        startActivity(Intent(this, SessionListActivity::class.java))
        finish()
    }
}
