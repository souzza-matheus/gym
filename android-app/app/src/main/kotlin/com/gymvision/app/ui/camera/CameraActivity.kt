package com.gymvision.app.ui.camera

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.os.bundleOf

class CameraActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(resources.getIdentifier("activity_camera", "layout", packageName))

        if (savedInstanceState == null) {
            val fragment = CameraFragment().apply {
                arguments = bundleOf(
                    "exerciseType" to (intent.getStringExtra("exerciseType") ?: "SQUAT"),
                    "sessionId"    to (intent.getStringExtra("sessionId")    ?: ""),
                    "studentId"    to (intent.getStringExtra("studentId")    ?: ""),
                    "academyId"    to (intent.getStringExtra("academyId")    ?: "")
                )
            }
            supportFragmentManager.beginTransaction()
                .replace(android.R.id.content, fragment)
                .commit()
        }
    }
}
