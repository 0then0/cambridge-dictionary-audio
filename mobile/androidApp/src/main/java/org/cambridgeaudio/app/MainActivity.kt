package org.cambridgeaudio.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.core.view.WindowCompat
import java.io.File
import kotlinx.serialization.json.*
import org.cambridgeaudio.core.stableId

class MainActivity : ComponentActivity() {
    private val model: AppModel by viewModels()
    private val importPicker =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) model.importDocument(uri)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MobileApp(
                model,
                {
                    importPicker.launch(
                        arrayOf("application/zip", "application/octet-stream", "*/*")
                    )
                },
                ::share,
            )
        }
    }

    private fun share(file: File) {
        val uri = FileProvider.getUriForFile(this, "$packageName.files", file)
        val intent =
            Intent(Intent.ACTION_SEND)
                .setType(if (file.extension == "apkg") "application/apkg" else "application/zip")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(
            Intent.createChooser(intent, model.t("Export collection", "Экспорт коллекции"))
        )
    }

    override fun onStop() {
        if (!isChangingConfigurations) model.background()
        super.onStop()
    }
}

@Composable
fun MobileApp(model: AppModel, importFile: () -> Unit, share: (File) -> Unit) {
    val context = LocalContext.current
    val dark =
        when (model.theme) {
            "dark" -> true
            "light" -> false
            else -> isSystemInDarkTheme()
        }
    val pureBlack = dark && model.pureBlack
    val dynamic =
        if (model.dynamicColor && android.os.Build.VERSION.SDK_INT >= 31) {
            if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        } else null
    val scheme = mobileColorScheme(dark, pureBlack, model.color, dynamic)
    val view = LocalView.current
    SideEffect {
        (context as? android.app.Activity)?.window?.let { window ->
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = !dark
                isAppearanceLightNavigationBars = !dark
            }
        }
    }
    MaterialTheme(colorScheme = scheme) {
        var tab by rememberSaveable { mutableIntStateOf(0) }
        var edit by remember { mutableStateOf(false) }
        var text by remember { mutableStateOf("") }
        var replacement by remember { mutableStateOf(false) }
        var deletion by remember { mutableStateOf(false) }
        var collectionId by rememberSaveable { mutableStateOf<String?>(null) }
        val closeCollection = {
            collectionId = null
            model.collectionSearchSelection?.let(model::restoreSelection)
            model.collectionSearchSelection = null
        }
        BackHandler(enabled = tab == 1 && collectionId != null) { closeCollection() }
        LaunchedEffect(model.selected?.str("variant_id"), collectionId) {
            if (collectionId != null && model.selected?.str("variant_id") != collectionId)
                closeCollection()
        }
        Scaffold(
            topBar = {
                Surface(tonalElevation = if (pureBlack) 0.dp else 2.dp) {
                    Column(Modifier.fillMaxWidth().statusBarsPadding().padding(16.dp)) {
                        if (tab == 1 && collectionId != null) {
                            TextButton(
                                onClick = closeCollection,
                                modifier = Modifier.testTag("collectionBack"),
                            ) {
                                Text(model.t("‹ Collection", "‹ Коллекция"))
                            }
                        }
                        Text(
                            "Cambridge Dictionary Audio",
                            style = MaterialTheme.typography.titleLarge,
                        )
                        if (model.busy) {
                            LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
                            TextButton(onClick = model::cancel) {
                                Text(model.t("Cancel operation", "Отменить операцию"))
                            }
                        }
                    }
                }
            },
            bottomBar = {
                NavigationBar(
                    containerColor = if (pureBlack) Color.Black else scheme.surfaceContainer
                ) {
                    listOf(
                            model.t("Search", "Поиск"),
                            model.t("Collection", "Коллекция"),
                            model.t("Settings", "Настройки"),
                        )
                        .forEachIndexed { index, label ->
                            NavigationBarItem(
                                selected = tab == index,
                                modifier = Modifier.testTag("tab$index"),
                                onClick = {
                                    if (index == 0 && collectionId != null) closeCollection()
                                    tab = index
                                },
                                icon = { Text(listOf("Aa", "≡", "⚙")[index]) },
                                label = { Text(label) },
                            )
                        }
                }
            },
        ) { insets ->
            BoxWithConstraints(Modifier.fillMaxSize().padding(insets).imePadding()) {
                val wide = maxWidth > 840.dp
                Row(Modifier.fillMaxSize()) {
                    Column(Modifier.weight(1f).widthIn(max = if (wide) 600.dp else 900.dp)) {
                        if (model.error != null) ErrorCard(model)
                        if (model.message.isNotEmpty())
                            Text(
                                model.message,
                                Modifier.padding(16.dp),
                                color = MaterialTheme.colorScheme.primary,
                            )
                        when (tab) {
                            0 ->
                                LazyColumn(
                                    Modifier.fillMaxSize(),
                                    contentPadding = PaddingValues(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(12.dp),
                                ) {
                                    item {
                                        OutlinedTextField(
                                            value = model.query,
                                            onValueChange = { model.query = it },
                                            label = {
                                                Text(
                                                    model.t(
                                                        "English word or phrase",
                                                        "Английское слово или фраза",
                                                    )
                                                )
                                            },
                                            modifier = Modifier.fillMaxWidth(),
                                            singleLine = true,
                                            keyboardOptions =
                                                KeyboardOptions(imeAction = ImeAction.Search),
                                            keyboardActions =
                                                KeyboardActions(onSearch = { model.search() }),
                                        )
                                    }
                                    item {
                                        FlowRow(
                                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                                        ) {
                                            Button(
                                                onClick = model::search,
                                                enabled = model.query.isNotBlank(),
                                            ) {
                                                Text(model.t("Find", "Найти"))
                                            }
                                            OutlinedButton(
                                                onClick = model::synthesize,
                                                enabled = model.query.trim().contains(' '),
                                            ) {
                                                Text(model.t("Build phrase", "Собрать фразу"))
                                            }
                                        }
                                    }
                                    item { AccentPicker(model) }
                                    if (
                                        model.entries.isEmpty() &&
                                            model.selected == null &&
                                            !model.busy
                                    )
                                        item {
                                            Text(
                                                model.t(
                                                    "Search Cambridge, choose a meaning, preview and save its recording.",
                                                    "Найдите слово в Cambridge, выберите значение, прослушайте и сохраните запись.",
                                                )
                                            )
                                        }
                                    item {
                                        MeaningMenu(
                                            model.entries,
                                            model.selected?.str("sense_id"),
                                            model.language,
                                            model::selectEntry,
                                        )
                                    }
                                    if (!wide && model.selected != null)
                                        item {
                                            Detail(
                                                model,
                                                {
                                                    text =
                                                        translationTexts(model.translation)
                                                            .joinToString("; ")
                                                    edit = true
                                                },
                                                { replacement = true },
                                                { deletion = true },
                                                share,
                                            )
                                        }
                                }
                            1 -> {
                                if (!wide && collectionId != null) {
                                    LazyColumn(
                                        Modifier.fillMaxSize().testTag("collectionDetail"),
                                        contentPadding = PaddingValues(16.dp),
                                    ) {
                                        item {
                                            Detail(
                                                model,
                                                {
                                                    text =
                                                        translationTexts(model.translation)
                                                            .joinToString("; ")
                                                    edit = true
                                                },
                                                { replacement = true },
                                                { deletion = true },
                                                share,
                                            )
                                        }
                                    }
                                } else
                                    CollectionList(model) {
                                        if (collectionId == null)
                                            model.collectionSearchSelection =
                                                model.captureSelection()
                                        model.selectSaved(it)
                                        collectionId = it.str("variant_id")
                                    }
                            }
                            2 -> Settings(model, importFile, model::requestWikdict, share)
                        }
                    }
                    if (
                        wide &&
                            model.selected != null &&
                            (tab == 0 || (tab == 1 && collectionId != null))
                    ) {
                        VerticalDivider()
                        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(24.dp)) {
                            item {
                                Detail(
                                    model,
                                    {
                                        text =
                                            translationTexts(model.translation).joinToString("; ")
                                        edit = true
                                    },
                                    { replacement = true },
                                    { deletion = true },
                                    share,
                                )
                            }
                        }
                    }
                }
            }
        }
        if (edit)
            AlertDialog(
                onDismissRequest = { edit = false },
                title = {
                    Text(model.t("Personal Russian translation", "Личный перевод на русский"))
                },
                text = {
                    OutlinedTextField(
                        value = text,
                        onValueChange = { text = it },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                    )
                },
                confirmButton = {
                    TextButton(
                        onClick = {
                            model.personalTranslation(text, false)
                            edit = false
                        }
                    ) {
                        Text(model.t("Save", "Сохранить"))
                    }
                },
                dismissButton = {
                    TextButton(
                        onClick = {
                            model.personalTranslation("", true)
                            edit = false
                        }
                    ) {
                        Text(model.t("Reset personal translation", "Сбросить личный перевод"))
                    }
                },
            )
        if (replacement)
            Confirm(
                model.t("Replace recording?", "Заменить запись?"),
                model.t(
                    "Shared audio is replaced for every meaning that uses it. Your translations are kept.",
                    "Общее аудио будет заменено для всех использующих его значений. Ваши переводы сохранятся.",
                ),
                { replacement = false },
                {
                    replacement = false
                    model.save(true)
                },
                model,
            )
        if (deletion)
            Confirm(
                model.t("Delete this meaning?", "Удалить это значение?"),
                model.t(
                    "Other meanings keep their shared audio.",
                    "Общее аудио сохранится для других значений.",
                ),
                { deletion = false },
                {
                    deletion = false
                    model.deleteSelected()
                },
                model,
            )
        model.wikdictPrompt?.let { status ->
            AlertDialog(
                onDismissRequest = model::dismissWikdictPrompt,
                title = {
                    Text(
                        if (status == "missing") model.t("Install WikDict", "Установить WikDict")
                        else model.t("Download WikDict again", "Скачать WikDict заново")
                    )
                },
                text = {
                    Text(
                        when (status) {
                            "ready" ->
                                model.t(
                                    "WikDict is already installed and verified. Download it again?",
                                    "WikDict уже установлен и проверен. Скачать его заново?",
                                )
                            "corrupt" ->
                                model.t(
                                    "The installed WikDict is damaged. Download it again?",
                                    "Установленный WikDict повреждён. Скачать его заново?",
                                )
                            else ->
                                model.t(
                                    "Install the English–Russian WikDict package?",
                                    "Установить англо-русский словарь WikDict?",
                                )
                        } +
                            "\n\n" +
                            model.t(
                                "2_2026-06 · 20.9 MB · CC BY-SA 4.0. WikDict by Karl Bartel; Wiktionary via DBnary. The download is verified before replacement.",
                                "2_2026-06 · 20,9 МБ · CC BY-SA 4.0. WikDict: Карл Бартель; Wiktionary через DBnary. Загрузка проверяется до замены словаря.",
                            )
                    )
                },
                confirmButton = {
                    TextButton(onClick = model::installWikdict) {
                        Text(
                            if (status == "missing") model.t("Install", "Установить")
                            else model.t("Download again", "Скачать заново")
                        )
                    }
                },
                dismissButton = {
                    TextButton(onClick = model::dismissWikdictPrompt) {
                        Text(model.t("Cancel", "Отмена"))
                    }
                },
            )
        }
        model.importPreview?.let { ImportDialog(model, it) }
        if (model.phrasePlans.isNotEmpty()) PhraseDialog(model)
    }
}

@Composable
internal fun MeaningMenu(
    entries: List<JsonObject>,
    selectedId: String?,
    language: String,
    onSelect: (JsonObject) -> Unit,
) {
    fun t(en: String, ru: String) = Locales.text(language, en, ru)
    if (entries.isEmpty()) return
    var expanded by rememberSaveable(entries) { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            t("Meanings (${entries.size})", "Значения (${entries.size})"),
            style = MaterialTheme.typography.titleSmall,
        )
        val visible = if (expanded) entries else entries.take(3)
        visible.forEach { entry ->
            OutlinedCard(
                onClick = {
                    onSelect(entry)
                    expanded = false
                },
                modifier = Modifier.fillMaxWidth().testTag("meaningOption"),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(entry.str("part_of_speech"), style = MaterialTheme.typography.labelMedium)
                    Text(entry.str("definition"), maxLines = 2, overflow = TextOverflow.Ellipsis)
                    if (selectedId == entry.str("sense_id"))
                        Text(
                            t("Selected", "Выбрано"),
                            color = MaterialTheme.colorScheme.primary,
                        )
                }
            }
        }
        if (entries.size > 3)
            TextButton(
                onClick = { expanded = !expanded },
                modifier = Modifier.testTag("allMeanings"),
            ) {
                Text(
                    if (expanded) t("Collapse meanings", "Свернуть значения")
                    else
                        t(
                            "Show all meanings (${entries.size})",
                            "Все значения (${entries.size})",
                        )
                )
            }
    }
}

@Composable
internal fun TranslationMenu(
    options: List<JsonObject>,
    selectedId: String?,
    selectionKey: String,
    language: String,
    choose: (String) -> Unit,
) {
    if (options.isEmpty()) return
    fun t(en: String, ru: String) = Locales.text(language, en, ru)
    var expanded by rememberSaveable(selectionKey, options) { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            t("Translation choices (${options.size})", "Варианты перевода (${options.size})"),
            style = MaterialTheme.typography.titleSmall,
        )
        (if (expanded) options else options.take(3)).forEach { option ->
            OutlinedCard(
                onClick = {
                    choose(option.str("id"))
                    expanded = false
                },
                modifier = Modifier.fillMaxWidth().testTag("translationOption"),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        option["texts"]?.jsonArray.orEmpty().joinToString("; ") {
                            it.jsonPrimitive.content
                        },
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (option.str("definition").isNotEmpty())
                        Text(
                            option.str("definition"),
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    if (selectedId == option.str("id"))
                        Text(t("Selected", "Выбрано"), color = MaterialTheme.colorScheme.primary)
                }
            }
        }
        if (options.size > 3)
            TextButton(
                onClick = { expanded = !expanded },
                modifier = Modifier.testTag("allTranslations"),
            ) {
                Text(
                    if (expanded) t("Collapse translations", "Свернуть переводы")
                    else t("All translations (${options.size})", "Все переводы (${options.size})")
                )
            }
    }
}

@Composable
private fun AccentPicker(model: AppModel) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf("us", "uk", "both").forEach { accent ->
            FilterChip(
                selected = model.accent == accent,
                onClick = { model.preference("accent", accent) },
                label = {
                    Text(if (accent == "both") model.t("Both", "Оба") else accent.uppercase())
                },
            )
        }
    }
}

@Composable
private fun Detail(
    model: AppModel,
    edit: () -> Unit,
    replace: () -> Unit,
    delete: () -> Unit,
    share: (File) -> Unit,
) {
    val item = model.selected ?: return
    val saved = item.str("variant_id").isNotEmpty()
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            item.str("word"),
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.semantics { heading() },
        )
        Text(item.str("part_of_speech"), style = MaterialTheme.typography.labelLarge)
        Text(item.str("definition"), style = MaterialTheme.typography.bodyLarge)
        if (saved) {
            Text("${item.str("accent").uppercase()} · /${item.str("ipa")}/")
            if (!item.bool("media_valid") && "media_valid" in item)
                Text(
                    model.t(
                        "Audio missing or corrupt. Use Repair.",
                        "Аудио отсутствует или повреждено. Восстановите запись.",
                    ),
                    color = MaterialTheme.colorScheme.error,
                )
        } else {
            val audio = item["pronunciations"]?.jsonArray.orEmpty().map { it.jsonObject }
            for (region in
                if (model.accent == "both") listOf("us", "uk") else listOf(model.accent)) {
                val choices = audio.filter { it.str("accent") == region }
                if (choices.isEmpty())
                    Text(
                        model.t("No $region recording", "Нет записи $region"),
                        color = MaterialTheme.colorScheme.error,
                    )
                choices.forEach { pronunciation ->
                    val id =
                        stableId(
                            "cambridge-audio",
                            pronunciation.str("accent"),
                            pronunciation.str("url"),
                        )
                    Row(
                        Modifier.fillMaxWidth()
                            .heightIn(min = 48.dp)
                            .selectable(
                                selected = model.selectedAudio[region] == id,
                                role = Role.RadioButton,
                                onClick = { model.chooseAudio(region, id) },
                            ),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        RadioButton(selected = model.selectedAudio[region] == id, onClick = null)
                        Text(
                            "${region.uppercase()} · /${pronunciation.str("ipa")}/",
                            Modifier.padding(vertical = 12.dp),
                        )
                    }
                }
            }
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (model.preparingAudio) {
                OutlinedButton(
                    onClick = model::cancel,
                    modifier = Modifier.testTag("preparingAudio"),
                ) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text(model.t("Cancel audio", "Отменить загрузку аудио"))
                }
            } else if (model.playing)
                Button(onClick = model::stopPlayback) { Text(model.t("Stop", "Остановить")) }
            else if (!saved && model.accent == "both") {
                OutlinedButton(onClick = { model.play("us") }) {
                    Text(model.t("Play US", "Слушать US"))
                }
                OutlinedButton(onClick = { model.play("uk") }) {
                    Text(model.t("Play UK", "Слушать UK"))
                }
            } else Button(onClick = { model.play() }) { Text(model.t("Play", "Слушать")) }
            if (!saved)
                Button(onClick = { model.save() }) {
                    Text(model.t("Save meaning", "Сохранить значение"))
                }
            if (saved) {
                OutlinedButton(onClick = replace) {
                    Text(model.t("Repair / download again", "Восстановить / загрузить заново"))
                }
                TextButton(onClick = delete) { Text(model.t("Delete", "Удалить")) }
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(model.t("Russian translation", "Русский перевод"), Modifier.weight(1f))
            Switch(checked = model.showTranslation, onCheckedChange = model::setTranslations)
        }
        if (model.showTranslation) {
            val texts = translationTexts(model.translation)
            Text(
                if (texts.isNotEmpty()) texts.joinToString("; ")
                else
                    model.t(
                        "No confirmed translation for this meaning.",
                        "Нет подтверждённого перевода этого значения.",
                    )
            )
            model.translation?.let { result ->
                Text(result.str("source"), style = MaterialTheme.typography.labelMedium)
                TranslationMenu(
                    result["options"]?.jsonArray.orEmpty().map { it.jsonObject },
                    result.str("selected_id"),
                    item.str("variant_id").ifEmpty { item.str("sense_id") },
                    model.language,
                    model::chooseTranslation,
                )
            }
            FlowRow {
                TextButton(onClick = model::translateSelected) {
                    Text(model.t("Find translation", "Найти перевод"))
                }
                TextButton(onClick = edit) { Text(model.t("Edit translation", "Изменить перевод")) }
            }
        }
        if (saved)
            FlowRow {
                OutlinedButton(onClick = { model.export("apkg", false, share) }) {
                    Text(model.t("Export this to Anki", "Экспорт в Anki"))
                }
                TextButton(onClick = { model.export("tsv", false, share) }) { Text("TSV") }
            }
    }
}

private fun translationTexts(result: JsonObject?): List<String> {
    if (result == null) return emptyList()
    val options = result["options"]?.jsonArray.orEmpty().map { it.jsonObject }
    val selected = options.find { it.str("id") == result.str("selected_id") }
    val matches =
        if (selected != null) listOf(selected)
        else
            options
                .filter { it.bool("matched") }
                .ifEmpty {
                    if (result.str("alignment") != "unmatched" && options.size == 1) options
                    else emptyList()
                }
    return matches
        .flatMap { it["texts"]?.jsonArray.orEmpty().map { it.jsonPrimitive.content } }
        .distinct()
}

@Composable
private fun CollectionList(model: AppModel, select: (JsonObject) -> Unit) {
    var filter by rememberSaveable { mutableStateOf("") }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            OutlinedTextField(
                filter,
                { filter = it },
                label = { Text(model.t("Search saved entries", "Поиск в коллекции")) },
                modifier = Modifier.fillMaxWidth(),
            )
            TextButton(onClick = model::refresh) { Text(model.t("Refresh", "Обновить")) }
        }
        if (model.recordings.isEmpty())
            item {
                Text(
                    model.t(
                        "No saved entries. Search and save a meaning first.",
                        "Нет сохранённых записей. Найдите и сохраните значение.",
                    )
                )
            }
        items(
            model.recordings.filter {
                filter.isBlank() ||
                    it.str("word").contains(filter, true) ||
                    it.str("definition").contains(filter, true)
            },
            key = { it.str("variant_id") },
        ) { record ->
            OutlinedCard(onClick = { select(record) }, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text(record.str("word"), style = MaterialTheme.typography.titleMedium)
                    Text(record.str("definition"))
                    Text(
                        record.str("accent").uppercase() +
                            if (!record.bool("media_valid"))
                                model.t(" · needs repair", " · требуется восстановление")
                            else ""
                    )
                }
            }
        }
    }
}

@Composable
private fun Settings(
    model: AppModel,
    importFile: () -> Unit,
    install: () -> Unit,
    share: (File) -> Unit,
) {
    val context = LocalContext.current
    var licenses by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { model.refreshWikdictStatus() }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Text(model.t("Language", "Язык"), style = MaterialTheme.typography.titleMedium)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Locales.names.forEach { (value, label) ->
                    FilterChip(
                        model.language == value,
                        { model.preference("language", value) },
                        label = { Text(label) },
                    )
                }
            }
        }
        item {
            Text(model.t("Appearance", "Оформление"), style = MaterialTheme.typography.titleMedium)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(
                        "system" to model.t("System", "Системное"),
                        "light" to model.t("Light", "Светлое"),
                        "dark" to model.t("Dark", "Тёмное"),
                    )
                    .forEach { (key, value) ->
                        FilterChip(
                            model.theme == key,
                            { model.preference("theme", key) },
                            label = { Text(value) },
                        )
                    }
            }
        }
        item {
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Column(Modifier.weight(1f).padding(end = 16.dp)) {
                    Text(model.t("Pure black (OLED)", "Чистый чёрный (OLED)"))
                    Text(
                        model.t(
                            "Use a pure black background when the dark theme is active.",
                            "Чёрный фон при активной тёмной теме, в том числе системной.",
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    model.pureBlack,
                    model::setOled,
                    Modifier.testTag("pureBlack").semantics {
                        contentDescription = model.t("Pure black (OLED)", "Чистый чёрный (OLED)")
                    },
                )
            }
        }
        item {
            Row {
                Text(
                    model.t("System colour palette", "Палитра цветов из системы"),
                    Modifier.weight(1f),
                )
                Switch(
                    checked = model.dynamicColor && android.os.Build.VERSION.SDK_INT >= 31,
                    onCheckedChange = model::setDynamic,
                    modifier = Modifier.testTag("systemColors"),
                    enabled = android.os.Build.VERSION.SDK_INT >= 31,
                )
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("blue", "green", "purple", "orange", "red").forEach { key ->
                    val label =
                        when (key) {
                            "blue" -> model.t("Blue", "Синий")
                            "green" -> model.t("Green", "Зелёный")
                            "purple" -> model.t("Purple", "Фиолетовый")
                            "red" -> model.t("Red", "Красный")
                            else -> model.t("Orange", "Оранжевый")
                        }
                    FilterChip(
                        selected =
                            model.color == key &&
                                (!model.dynamicColor || android.os.Build.VERSION.SDK_INT < 31),
                        onClick = {
                            model.preference("color", key)
                            model.setDynamic(false)
                        },
                        label = { Text(label) },
                    )
                }
            }
        }
        item {
            Text(model.t("Default pronunciation", "Произношение по умолчанию"))
            AccentPicker(model)
        }
        item {
            Row {
                Text(model.t("Offline translation lookup", "Перевод без сети"), Modifier.weight(1f))
                Switch(model.offline, { model.offline = it })
            }
            Text(
                if (model.checkingDictionary) model.t("Checking WikDict…", "Проверка WikDict…")
                else
                    when (model.dictionaryStatus) {
                        "ready" ->
                            model.t(
                                "WikDict: installed and verified",
                                "WikDict: установлен и проверен",
                            )
                        "missing" -> model.t("WikDict: not installed", "WikDict: не установлен")
                        "corrupt" -> model.t("WikDict: damaged", "WikDict: повреждён")
                        else -> model.t("WikDict: unavailable", "WikDict: недоступен")
                    },
                Modifier.testTag("wikdictStatus"),
            )
            OutlinedButton(onClick = install, enabled = !model.busy && !model.checkingDictionary) {
                Text(
                    when (model.dictionaryStatus) {
                        "ready",
                        "corrupt" -> model.t("Download WikDict again", "Скачать WikDict заново")
                        "unavailable" -> model.t("Check WikDict", "Проверить WikDict")
                        else -> model.t("Install WikDict en → ru", "Установить WikDict en → ru")
                    }
                )
            }
        }
        item {
            Text(
                model.t("Collection transfer", "Перенос коллекции"),
                style = MaterialTheme.typography.titleMedium,
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { model.export("bundle", true, share) }) {
                    Text(model.t("Back up / export", "Резервная копия / экспорт"))
                }
                OutlinedButton(onClick = importFile) {
                    Text(model.t("Import bundle", "Импорт коллекции"))
                }
            }
        }
        item {
            Text(
                model.t("Anki export", "Экспорт Anki"),
                style = MaterialTheme.typography.titleMedium,
            )
            FlowRow {
                OutlinedButton(onClick = { model.export("apkg", true, share) }) {
                    Text(model.t("Collection APKG", "Коллекция APKG"))
                }
                TextButton(onClick = { model.export("tsv", true, share) }) {
                    Text(model.t("Collection TSV + media", "Коллекция TSV + аудио"))
                }
            }
        }
        item {
            Text(model.t("About", "О приложении"), style = MaterialTheme.typography.titleMedium)
            Text("${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) · storage 3 · bundle 1")
            TextButton(
                onClick = {
                    context.startActivity(
                        Intent(
                            Intent.ACTION_VIEW,
                            android.net.Uri.parse(
                                "https://github.com/0then0/cambridge-dictionary-audio"
                            ),
                        )
                    )
                }
            ) {
                Text(model.t("Repository", "Репозиторий"))
            }
            TextButton(onClick = { licenses = true }) {
                Text(model.t("Licenses and sources", "Лицензии и источники"))
            }
        }
    }
    if (licenses) LicensesDialog(model.language) { licenses = false }
}

@Composable
private fun ErrorCard(model: AppModel) {
    val error = model.error ?: return
    var details by remember(error) { mutableStateOf(false) }
    Card(
        Modifier.fillMaxWidth().padding(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(
                when (error.code) {
                    "input" ->
                        model.t(
                            "Enter an English word or phrase.",
                            "Введите английское слово или фразу.",
                        )
                    "absent" ->
                        model.t(
                            "No dictionary result. Check the spelling.",
                            "Результат не найден. Проверьте написание.",
                        )
                    "blocked" ->
                        model.t(
                            "Cambridge blocked the request. Try later.",
                            "Cambridge заблокировал запрос. Повторите позже.",
                        )
                    "network" ->
                        model.t(
                            "Network request failed. Check the connection and retry.",
                            "Ошибка сети. Проверьте подключение и повторите.",
                        )
                    "parser" ->
                        model.t(
                            "Dictionary markup is not recognized. See technical details.",
                            "Разметка словаря не распознана. Откройте технические сведения.",
                        )
                    "accent" ->
                        model.t(
                            "The selected accent is unavailable. Choose another explicitly.",
                            "Выбранный акцент недоступен. Выберите другой явно.",
                        )
                    "dictionary_missing" ->
                        model.t(
                            "Install WikDict to translate offline.",
                            "Установите WikDict для перевода без сети.",
                        )
                    "dictionary_corrupt" ->
                        model.t(
                            "WikDict is damaged. Reinstall it in Settings.",
                            "WikDict повреждён. Переустановите его в настройках.",
                        )
                    "translation_choice" ->
                        model.t(
                            "Choose or edit the translation before export.",
                            "Выберите или отредактируйте перевод перед экспортом.",
                        )
                    "schema" ->
                        model.t(
                            "Unsupported data version. Keep a backup and update the application.",
                            "Неподдерживаемая версия данных. Сохраните резервную копию и обновите приложение.",
                        )
                    "audio" ->
                        model.t(
                            "Audio is missing or damaged. Repair the saved recording.",
                            "Аудио отсутствует или повреждено. Восстановите запись.",
                        )
                    "ambiguous_phrase" ->
                        model.t(
                            "A phrase segment has several pronunciations. Choose an unambiguous phrase.",
                            "У слова во фразе несколько произношений. Выберите однозначную фразу.",
                        )
                    "stale" ->
                        model.t(
                            "The selection or collection changed. Repeat the operation.",
                            "Выбор или коллекция изменились. Повторите операцию.",
                        )
                    else ->
                        model.t(
                            "Operation failed. Check free space and technical details; retry.",
                            "Операция не выполнена. Проверьте свободное место и технические сведения; повторите.",
                        )
                }
            )
            TextButton(onClick = { details = !details }) {
                Text(model.t("Technical details", "Технические сведения"))
            }
            if (details)
                androidx.compose.foundation.text.selection.SelectionContainer {
                    Text(error.details)
                }
            TextButton(onClick = model::clearError) { Text(model.t("Close", "Закрыть")) }
        }
    }
}

@Composable
private fun Confirm(
    title: String,
    text: String,
    dismiss: () -> Unit,
    confirm: () -> Unit,
    model: AppModel,
) {
    AlertDialog(
        onDismissRequest = dismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = {
            TextButton(onClick = confirm) { Text(model.t("Confirm", "Подтвердить")) }
        },
        dismissButton = { TextButton(onClick = dismiss) { Text(model.t("Cancel", "Отмена")) } },
    )
}

@Composable
private fun ImportDialog(model: AppModel, preview: JsonObject) {
    val conflicts = preview["conflicts"]!!.jsonArray.map { it.jsonPrimitive.content }
    val decisions = remember(preview) { mutableStateMapOf<String, String>() }
    AlertDialog(
        onDismissRequest = model::dismissImport,
        title = { Text(model.t("Import preview", "Предварительный импорт")) },
        text = {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                item {
                    Text(
                        model.t(
                            "New: ${preview["added"]!!.jsonArray.size}; unchanged: ${preview["unchanged"]!!.jsonArray.size}; conflicts: ${conflicts.size}",
                            "Новых: ${preview["added"]!!.jsonArray.size}; без изменений: ${preview["unchanged"]!!.jsonArray.size}; конфликтов: ${conflicts.size}",
                        )
                    )
                }
                items(conflicts) { id ->
                    val incoming = preview["entries"]?.jsonObject?.get(id)?.jsonObject
                    val existing = model.recordings.find { it.str("variant_id") == id }
                    Column {
                        Text(
                            incoming?.str("word") ?: id,
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(incoming?.str("definition").orEmpty())
                        Text(
                            model.t("Current: ", "Текущий: ") +
                                translationTexts(existing?.let(DomainKtBridge::translation))
                                    .joinToString("; ")
                        )
                        Text(
                            model.t("Incoming: ", "Входящий: ") +
                                translationTexts(incoming?.let(DomainKtBridge::translation))
                                    .joinToString("; ")
                        )
                        FlowRow {
                            FilterChip(
                                decisions[id] == "existing",
                                { decisions[id] = "existing" },
                                label = { Text(model.t("Keep current", "Оставить текущий")) },
                            )
                            FilterChip(
                                decisions[id] == "incoming",
                                { decisions[id] = "incoming" },
                                label = { Text(model.t("Use incoming", "Принять входящий")) },
                            )
                        }
                    }
                }
                item {
                    Text(
                        model.t(
                            "A backup is retained before replacement. Device timestamps never decide a conflict.",
                            "Перед заменой сохраняется резервная копия. Время устройства не определяет решение конфликта.",
                        )
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    model.applyImport(JsonObject(decisions.mapValues { JsonPrimitive(it.value) }))
                },
                enabled = conflicts.all { it in decisions },
            ) {
                Text(model.t("Import", "Импортировать"))
            }
        },
        dismissButton = {
            TextButton(onClick = model::dismissImport) { Text(model.t("Cancel", "Отмена")) }
        },
    )
}

@Composable
private fun PhraseDialog(model: AppModel) {
    val plans = model.phrasePlans
    val selected = remember(plans) { mutableStateMapOf<String, String>() }
    AlertDialog(
        onDismissRequest = model::dismissPhrase,
        title = { Text(model.t("Phrase recordings", "Записи для фразы")) },
        text = {
            LazyColumn {
                item {
                    Text(
                        model.t(
                            "Review each segment in order. Confirming replaces an existing synthesized phrase with the same words and accent; personal translations are retained.",
                            "Проверьте записи в порядке слов. Подтверждение заменит уже собранную фразу с теми же словами и акцентом; личные переводы сохранятся.",
                        )
                    )
                }
                plans.forEachIndexed { planIndex, plan ->
                    item {
                        Text(
                            plan.str("accent").uppercase(),
                            style = MaterialTheme.typography.titleMedium,
                        )
                    }
                    plan["segments"]!!.jsonArray.forEachIndexed { segmentIndex, raw ->
                        val segment = raw.jsonObject
                        item {
                            Text(segment.str("word"), style = MaterialTheme.typography.titleSmall)
                            val key = "$planIndex:$segmentIndex"
                            val options = segment["options"]!!.jsonArray.map { it.jsonObject }
                            options.forEach { option ->
                                val chosen = selected[key] ?: options.first().str("id")
                                Row(
                                    Modifier.fillMaxWidth()
                                        .heightIn(min = 48.dp)
                                        .selectable(
                                            chosen == option.str("id"),
                                            role = Role.RadioButton,
                                            onClick = { selected[key] = option.str("id") },
                                        )
                                ) {
                                    RadioButton(chosen == option.str("id"), onClick = null)
                                    Text("/${option.str("ipa")}/", Modifier.padding(12.dp))
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val choices = plans.mapIndexed { planIndex, plan ->
                        plan["segments"]!!.jsonArray.mapIndexed { segmentIndex, raw ->
                            selected["$planIndex:$segmentIndex"]
                                ?: raw.jsonObject["options"]!!
                                    .jsonArray
                                    .first()
                                    .jsonObject
                                    .str("id")
                        }
                    }
                    model.applyPhrase(choices)
                }
            ) {
                Text(model.t("Build and save", "Собрать и сохранить"))
            }
        },
        dismissButton = {
            TextButton(onClick = model::dismissPhrase) { Text(model.t("Cancel", "Отмена")) }
        },
    )
}
