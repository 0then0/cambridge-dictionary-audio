package org.cambridgeaudio.app

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp

internal fun mobileColorScheme(
    dark: Boolean,
    pureBlack: Boolean,
    color: String,
    dynamic: ColorScheme? = null,
): ColorScheme {
    // Material's unspecified roles keep its default purple palette. Supply every
    // accent and neutral role together; system colours remain a complete scheme.
    val seed =
        when (color) {
            "green" -> Color(0xFF386A20)
            "purple" -> Color(0xFF6750A4)
            "orange" -> Color(0xFF8B5000)
            "red" -> Color(0xFFAF3448)
            else -> Color(0xFF215FA6)
        }
    fun pale(amount: Float) = lerp(Color.White, seed, amount)
    fun deep(amount: Float) = lerp(Color.Black, seed, amount)
    fun neutral(base: Long, amount: Float) = lerp(Color(base), seed, amount)
    val bright = if (color == "red") Color(0xFFE38494) else pale(.40f)
    val primary = if (dark) bright else seed
    val ink = neutral(0xFF171717, .08f)
    val paper = pale(.025f)
    val background = if (dark) neutral(0xFF121212, .06f) else paper
    val onSurface = if (dark) pale(.06f) else ink
    val container = if (dark) deep(.85f) else pale(.15f)
    val onContainer = if (dark) pale(.12f) else deep(.25f)
    val secondary = if (dark) lerp(bright, Color(0xFFCCCCCC), .20f) else neutral(0xFF444444, .65f)
    val tertiary = if (dark) pale(.30f) else neutral(0xFF444444, .85f)
    val secondaryContainer = if (dark) deep(.95f) else pale(.11f)
    val tertiaryContainer = if (dark) deep(.80f) else pale(.20f)
    var scheme =
        dynamic
            ?: (if (dark) darkColorScheme() else lightColorScheme()).copy(
                primary = primary,
                onPrimary = if (dark) ink else Color.White,
                primaryContainer = container,
                onPrimaryContainer = onContainer,
                inversePrimary = if (dark) seed else bright,
                secondary = secondary,
                onSecondary = if (dark) ink else Color.White,
                secondaryContainer = secondaryContainer,
                onSecondaryContainer = onContainer,
                tertiary = tertiary,
                onTertiary = if (dark) ink else Color.White,
                tertiaryContainer = tertiaryContainer,
                onTertiaryContainer = onContainer,
                background = background,
                onBackground = onSurface,
                surface = background,
                onSurface = onSurface,
                surfaceVariant = if (dark) neutral(0xFF303030, .15f) else pale(.10f),
                onSurfaceVariant = if (dark) pale(.20f) else neutral(0xFF444444, .18f),
                surfaceTint = primary,
                inverseSurface = if (dark) paper else ink,
                inverseOnSurface = if (dark) ink else paper,
                outline = neutral(if (dark) 0xFFAAAAAA else 0xFF707070, .15f),
                outlineVariant = if (dark) neutral(0xFF404040, .15f) else pale(.28f),
                surfaceDim = if (dark) background else pale(.12f),
                surfaceBright = if (dark) neutral(0xFF383838, .10f) else paper,
                surfaceContainerLowest = if (dark) neutral(0xFF0C0C0C, .04f) else Color.White,
                surfaceContainerLow = if (dark) neutral(0xFF191919, .07f) else pale(.04f),
                surfaceContainer = if (dark) neutral(0xFF202020, .08f) else pale(.06f),
                surfaceContainerHigh = if (dark) neutral(0xFF282828, .10f) else pale(.08f),
                surfaceContainerHighest = if (dark) neutral(0xFF303030, .12f) else pale(.10f),
                primaryFixed = pale(.15f),
                primaryFixedDim = pale(.30f),
                onPrimaryFixed = ink,
                onPrimaryFixedVariant = deep(.50f),
                secondaryFixed = pale(.11f),
                secondaryFixedDim = pale(.25f),
                onSecondaryFixed = ink,
                onSecondaryFixedVariant = deep(.40f),
                tertiaryFixed = pale(.20f),
                tertiaryFixedDim = pale(.35f),
                onTertiaryFixed = ink,
                onTertiaryFixedVariant = deep(.60f),
            )
    if (dark && pureBlack)
        scheme =
            scheme.copy(
                background = Color.Black,
                surface = Color.Black,
                surfaceVariant = Color.Black,
                surfaceDim = Color.Black,
                surfaceBright = Color.Black,
                surfaceTint = Color.Black,
                surfaceContainer = Color.Black,
                surfaceContainerLow = Color.Black,
                surfaceContainerLowest = Color.Black,
                surfaceContainerHigh = Color.Black,
                surfaceContainerHighest = Color.Black,
            )
    return scheme
}
