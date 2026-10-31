package org.cambridgeaudio.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.Density
import androidx.core.graphics.ColorUtils
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class PresentationTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun translationsShowThreeAndCollapseAfterChoosingAnAlternative() {
        val options =
            (1..7).map { index ->
                buildJsonObject {
                    put("id", "translation-$index")
                    put("texts", JsonArray(listOf(JsonPrimitive("Перевод $index"))))
                    put("definition", "Source meaning $index")
                }
            }
        val selected = mutableStateOf<String?>(null)
        compose.setContent {
            MaterialTheme {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    TranslationMenu(options, selected.value, "word-sense", "en") {
                        selected.value = it
                    }
                }
            }
        }
        compose.onAllNodesWithTag("translationOption").assertCountEquals(3)
        compose.onNodeWithText("Перевод 4").assertDoesNotExist()
        compose.onNodeWithTag("allTranslations").performScrollTo().performClick()
        compose.onAllNodesWithTag("translationOption").assertCountEquals(7)
        compose.onNodeWithText("Перевод 6").performScrollTo().performClick()
        assertEquals("translation-6", selected.value)
        compose.onAllNodesWithTag("translationOption").assertCountEquals(3)
    }

    @Test
    fun licensesRemainReadableAndNavigableAtDoubleFontSize() {
        var closed = false
        compose.setContent {
            val density = LocalDensity.current.density
            CompositionLocalProvider(LocalDensity provides Density(density, 2f)) {
                MaterialTheme { LicensesDialog("en") { closed = true } }
            }
        }
        compose.onNodeWithText("Close").assertIsDisplayed()
        compose.onNodeWithText("Apache License 2.0").performScrollTo().performClick()
        compose
            .onNodeWithText(
                "Apache License Version 2.0, January 2004 http://www.apache.org/licenses/"
            )
            .assertExists()
        compose.onNodeWithText("Close").assertIsDisplayed()
        compose
            .onNodeWithTag("licenseContent")
            .performScrollToNode(hasText("END OF TERMS AND CONDITIONS"))
        compose.onNodeWithText("END OF TERMS AND CONDITIONS").assertIsDisplayed()
        compose.onNodeWithText("All licenses").performClick()
        compose.onNodeWithText("MIT License").performScrollTo().performClick()
        compose.onNodeWithText("Copyright (c) 2023 Aliaksandr Melnichenka").assertExists()
        compose.onNodeWithText("Close").performClick()
        assertTrue(closed)
    }

    @Test
    fun meaningsStartWithThreeAndCollapseAfterChoosingFromAll() {
        val entries =
            (1..6).map { index ->
                buildJsonObject {
                    put("sense_id", "sense-$index")
                    put("part_of_speech", "noun")
                    put("definition", "Meaning $index")
                }
            }
        val selected = mutableStateOf<String?>(null)
        compose.setContent {
            MaterialTheme {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    MeaningMenu(entries, selected.value, "en") {
                        selected.value = it.str("sense_id")
                    }
                }
            }
        }
        compose.onAllNodesWithTag("meaningOption").assertCountEquals(3)
        compose.onNodeWithText("Meaning 4").assertDoesNotExist()
        compose.onNodeWithTag("allMeanings").performScrollTo().performClick()
        compose.onAllNodesWithTag("meaningOption").assertCountEquals(6)
        compose.onNodeWithText("Meaning 5").performScrollTo().performClick()
        compose.onAllNodesWithTag("meaningOption").assertCountEquals(3)
        assertEquals("sense-5", selected.value)
    }

    @Test
    fun oledSurfacesStayBlackWithDynamicColoursAndDesktopRedAdaptsToDarkMode() {
        val dynamic = darkColorScheme(surface = Color.Red, background = Color.Blue)
        val oled = mobileColorScheme(true, true, "blue", dynamic)
        assertEquals(Color.Black, oled.surface)
        assertEquals(Color.Black, oled.background)
        assertEquals(Color.Black, oled.surfaceContainer)
        assertEquals(Color.Black, oled.surfaceContainerHigh)
        assertEquals(Color.Black, oled.surfaceTint)
        assertEquals(Color(0xFFAF3448), mobileColorScheme(false, false, "red").primary)
        assertEquals(Color(0xFFE38494), mobileColorScheme(true, true, "red").primary)
        assertSame(dynamic, mobileColorScheme(true, false, "red", dynamic))
        assertEquals(
            mobileColorScheme(false, false, "red").background,
            mobileColorScheme(false, true, "red").background,
        )
        assertNotEquals(Color.Black, mobileColorScheme(false, true, "red").surface)
    }

    @Test
    fun manualAccentsStyleSelectionsAndSurfacesWithReadableText() {
        for (dark in listOf(false, true)) {
            val schemes =
                listOf("blue", "green", "purple", "orange", "red").map {
                    mobileColorScheme(dark, false, it)
                }
            // These are used by selected chips, navigation, switches and backgrounds.
            assertEquals(5, schemes.map { it.secondaryContainer }.distinct().size)
            assertEquals(5, schemes.map { it.surfaceContainer }.distinct().size)
            assertEquals(5, schemes.map { it.background }.distinct().size)
            for (scheme in schemes) {
                if (dark) {
                    assertTrue(
                        "Selected chips must remain visible on dark surfaces",
                        ColorUtils.calculateContrast(
                            scheme.secondaryContainer.toArgb(),
                            scheme.surface.toArgb(),
                        ) >= 2.0,
                    )
                }
                val pairs =
                    listOf(
                        scheme.onPrimary to scheme.primary,
                        scheme.onPrimaryContainer to scheme.primaryContainer,
                        scheme.onSecondary to scheme.secondary,
                        scheme.onSecondaryContainer to scheme.secondaryContainer,
                        scheme.onTertiary to scheme.tertiary,
                        scheme.onTertiaryContainer to scheme.tertiaryContainer,
                        scheme.onBackground to scheme.background,
                        scheme.onSurface to scheme.surface,
                        scheme.onSurfaceVariant to scheme.surfaceVariant,
                        scheme.inverseOnSurface to scheme.inverseSurface,
                        scheme.onPrimaryFixed to scheme.primaryFixedDim,
                        scheme.onPrimaryFixedVariant to scheme.primaryFixedDim,
                        scheme.onSecondaryFixedVariant to scheme.secondaryFixedDim,
                        scheme.onTertiaryFixedVariant to scheme.tertiaryFixedDim,
                    )
                for ((text, background) in pairs) {
                    val contrast = ColorUtils.calculateContrast(text.toArgb(), background.toArgb())
                    assertTrue(
                        "Text contrast $contrast in dark=$dark: $text on $background",
                        contrast >= 4.5,
                    )
                }
            }
        }
    }
}
