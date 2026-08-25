package com.ikegami99.krprnews

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.ikegami99.krprnews.data.ApiFreeNewsRepository
import com.ikegami99.krprnews.ui.KiraparaApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { KiraparaApp(repository = ApiFreeNewsRepository) }
    }
}
