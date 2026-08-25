package com.ikegami99.krprnews.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import com.ikegami99.krprnews.prefs.ThemeMode

private val LightColors = lightColorScheme(
    primary = Color(0xFF9A4FC5),
    onPrimary = Color.White,
    secondary = Color(0xFFE76CA9),
    tertiary = Color(0xFF5D91D8),
    background = Color(0xFFFFF9FF),
    surface = Color(0xFFFFFBFF),
    onBackground = Color(0xFF302538),
    onSurface = Color(0xFF302538)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFE3B6FF),
    onPrimary = Color(0xFF4C1969),
    secondary = Color(0xFFFFAED2),
    tertiary = Color(0xFFAEC9FF),
    background = Color(0xFF171020),
    surface = Color(0xFF21172D),
    onBackground = Color(0xFFF8EDFF),
    onSurface = Color(0xFFF8EDFF)
)

@Composable
fun KiraparaTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    MaterialTheme(colorScheme = if (dark) DarkColors else LightColors, content = content)
}
