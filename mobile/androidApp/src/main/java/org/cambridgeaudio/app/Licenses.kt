package org.cambridgeaudio.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.window.DialogWindowProvider
import androidx.core.view.WindowCompat

@Composable
internal fun LicensesDialog(russian: Boolean, dismiss: () -> Unit) {
    fun t(en: String, ru: String) = if (russian) ru else en
    var document by rememberSaveable { mutableStateOf<String?>(null) }
    val documents =
        mapOf(
            "LICENSE" to "Apache License 2.0",
            "LICENSE-MIT" to "MIT License",
            "NOTICE" to t("Attribution (NOTICE)", "Авторство (NOTICE)"),
        )
    val context = LocalContext.current
    val uri = LocalUriHandler.current
    Dialog(
        onDismissRequest = dismiss,
        properties =
            DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
    ) {
        BackHandler(enabled = document != null) { document = null }
        val view = LocalView.current
        val lightBars = MaterialTheme.colorScheme.surface.luminance() > .5f
        SideEffect {
            (view.parent as? DialogWindowProvider)?.window?.let { window ->
                WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = lightBars
                    isAppearanceLightNavigationBars = lightBars
                }
            }
        }
        Scaffold(
            modifier = Modifier.fillMaxSize().testTag("licensesScreen"),
            topBar = {
                Surface {
                    Column(Modifier.statusBarsPadding().padding(horizontal = 16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                document
                                    ?.let { documents[it] }
                                    .orEmpty()
                                    .ifEmpty {
                                        t("Licenses and sources", "Лицензии и источники")
                                    },
                                Modifier.weight(1f).padding(vertical = 16.dp).semantics {
                                    heading()
                                },
                                style = MaterialTheme.typography.titleLarge,
                            )
                            TextButton(onClick = dismiss) { Text(t("Close", "Закрыть")) }
                        }
                        if (document != null)
                            TextButton(onClick = { document = null }) {
                                Text(t("All licenses", "Все лицензии"))
                            }
                    }
                }
            },
        ) { padding ->
            key(document) {
                SelectionContainer {
                    LazyColumn(
                        Modifier.fillMaxSize().padding(padding).testTag("licenseContent"),
                        contentPadding = PaddingValues(20.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        val selected = document
                        if (selected != null) {
                            // Reflow the printed license without changing its words or bundled
                            // file.
                            val paragraphs =
                                context.assets.open(selected).bufferedReader().use {
                                    it.readText().trim().split(Regex("\\n\\s*\\n")).map { paragraph
                                        ->
                                        paragraph.trim().replace(Regex("\\s+"), " ")
                                    }
                                }
                            items(paragraphs) { paragraph ->
                                Text(
                                    paragraph,
                                    Modifier.fillMaxWidth(),
                                    style = MaterialTheme.typography.bodyLarge,
                                    textAlign = TextAlign.Start,
                                )
                            }
                        } else {
                            item {
                                LicenseSection(
                                    "Cambridge Dictionary Audio",
                                    t(
                                        "Application: Apache-2.0. Inherited code: MIT.",
                                        "Приложение: Apache-2.0. Унаследованный код: MIT.",
                                    ),
                                )
                            }
                            item {
                                LicenseSection(
                                    t("Libraries", "Библиотеки"),
                                    "Kotlin, Okio, AndroidX · Apache-2.0\nKsoup · MIT\nLAME · LGPL-2.0-or-later",
                                )
                                Text(
                                    t(
                                        "Source, build and relinking materials accompany releases.",
                                        "Исходники и материалы для сборки и перелинковки поставляются с релизами.",
                                    )
                                )
                                TextButton(
                                    onClick = { uri.openUri("https://lame.sourceforge.io/") }
                                ) {
                                    Text(t("LAME sources", "Исходники LAME"))
                                }
                            }
                            item {
                                LicenseSection(
                                    "Cambridge Dictionary",
                                    t(
                                        "Audio, IPA and definitions retain their owners’ rights.",
                                        "Права на аудио, транскрипции и определения принадлежат правообладателям.",
                                    ),
                                )
                                TextButton(
                                    onClick = {
                                        uri.openUri("https://dictionary.cambridge.org/terms-of-use")
                                    }
                                ) {
                                    Text(t("Terms of use", "Условия использования"))
                                }
                            }
                            item {
                                LicenseSection(
                                    "WikDict / Wiktionary / DBnary",
                                    t(
                                        "WikDict by Karl Bartel · CC BY-SA 4.0. Wiki markup and duplicate translations are removed.",
                                        "WikDict: Карл Бартель · CC BY-SA 4.0. Вики-разметка и повторяющиеся переводы удалены.",
                                    ),
                                )
                                TextButton(
                                    onClick = {
                                        uri.openUri(
                                            "https://creativecommons.org/licenses/by-sa/4.0/"
                                        )
                                    }
                                ) {
                                    Text(t("CC BY-SA 4.0 license", "Лицензия CC BY-SA 4.0"))
                                }
                            }
                            item {
                                LicenseSection(
                                    t("Full texts", "Полные тексты"),
                                    t(
                                        "Original licenses and attribution are available offline.",
                                        "Оригинальные лицензии и сведения об авторстве доступны без сети.",
                                    ),
                                )
                                documents.forEach { (file, title) ->
                                    TextButton(onClick = { document = file }) { Text(title) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun LicenseSection(title: String, description: String) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium)
        Text(description, style = MaterialTheme.typography.bodyLarge)
    }
}
