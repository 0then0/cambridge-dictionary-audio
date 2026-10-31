package org.cambridgeaudio.app

import android.app.Application
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.*
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.serialization.json.*
import org.cambridgeaudio.core.*

internal fun JsonObject.str(key: String) = this[key]?.jsonPrimitive?.contentOrNull.orEmpty()

internal fun JsonObject.bool(key: String) = this[key]?.jsonPrimitive?.booleanOrNull == true

internal fun parseObject(text: String) = Json.parseToJsonElement(text).jsonObject

data class TaskError(val code: String, val details: String)

data class SelectionState(
    val entries: List<JsonObject>,
    val selected: JsonObject?,
    val translation: JsonObject?,
    val audio: Map<String, String>,
)

class AppModel(application: Application, private val state: SavedStateHandle) :
    AndroidViewModel(application) {
    private val prefs = application.getSharedPreferences("preferences", Context.MODE_PRIVATE)
    private val legacyBlack = prefs.getString("theme", "system") == "black"
    var language by mutableStateOf(prefs.getString("language", "en")!!)
        private set

    var theme by mutableStateOf(if (legacyBlack) "dark" else prefs.getString("theme", "system")!!)
        private set

    var pureBlack by mutableStateOf(prefs.getBoolean("pureBlack", legacyBlack))
        private set

    var accent by mutableStateOf(prefs.getString("accent", "us")!!)
        private set

    var dynamicColor by mutableStateOf(prefs.getBoolean("dynamicColor", true))
        private set

    var color by mutableStateOf(prefs.getString("color", "blue")!!)
        private set

    var showTranslation by mutableStateOf(prefs.getBoolean("translation", false))
        private set

    var offline by mutableStateOf(false)
    var query by mutableStateOf(state.get<String>("query").orEmpty())
    var entries by mutableStateOf<List<JsonObject>>(emptyList())
        private set

    var selected by mutableStateOf<JsonObject?>(null)
        private set

    var recordings by mutableStateOf<List<JsonObject>>(emptyList())
        private set

    var translation by mutableStateOf<JsonObject?>(null)
        private set

    var selectedAudio by mutableStateOf<Map<String, String>>(emptyMap())
        private set

    var busy by mutableStateOf(false)
        private set

    var message by mutableStateOf("")
        private set

    var error by mutableStateOf<TaskError?>(null)
        private set

    var importPreview by mutableStateOf<JsonObject?>(null)
        private set

    var playing by mutableStateOf(false)
        private set

    var preparingAudio by mutableStateOf(false)
        private set

    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private val platform = AndroidPlatform()
    private val engine =
        Engine(
            File(application.filesDir, "collection").path,
            File(application.cacheDir, "work").path,
            platform,
        )
    private var request = 0L
    private var selection = 0L
    private var editRevision = 0L
    private var token: AtomicBoolean? = null
    private var player: MediaPlayer? = null
    private val audioManager = application.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val focus =
        AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setOnAudioFocusChangeListener { change ->
                if (change != AudioManager.AUDIOFOCUS_GAIN) stopPlayback()
            }
            .build()
    private val noisy =
        object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                stopPlayback()
            }
        }

    init {
        if (legacyBlack)
            prefs.edit().putString("theme", theme).putBoolean("pureBlack", pureBlack).apply()
        if (Build.VERSION.SDK_INT >= 33)
            application.registerReceiver(
                noisy,
                IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY),
                Context.RECEIVER_NOT_EXPORTED,
            )
        else
            @Suppress("UnspecifiedRegisterReceiverFlag")
            application.registerReceiver(
                noisy,
                IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY),
            )
        run {
            CollectionTransfer(engine).recover()
            refreshWorker()
        }
    }

    fun t(en: String, ru: String) = Locales.text(language, en, ru)

    fun preference(key: String, value: String) {
        prefs.edit().putString(key, value).apply()
        when (key) {
            "language" -> language = value
            "theme" -> theme = value
            "accent" -> accent = value
            "color" -> color = value
        }
    }

    fun setDynamic(value: Boolean) {
        dynamicColor = value
        prefs.edit().putBoolean("dynamicColor", value).apply()
    }

    fun setOled(value: Boolean) {
        pureBlack = value
        prefs.edit().putBoolean("pureBlack", value).apply()
    }

    fun setTranslations(value: Boolean) {
        showTranslation = value
        prefs.edit().putBoolean("translation", value).apply()
        if (value) translateSelected()
    }

    private fun run(showProgress: Boolean = true, work: () -> Unit) {
        val serial = ++request
        val flag = AtomicBoolean(false)
        token?.set(true)
        token = flag
        busy = showProgress
        preparingAudio = false
        error = null
        if (showProgress) message = ""
        executor.execute {
            platform.cancellation = flag
            // Cancellation may arrive during blocking I/O; forward it to its adapter.
            try {
                if (flag.get()) throw MobileError("cancelled")
                work()
            } catch (e: Exception) {
                main.post {
                    if (serial == request && (e as? MobileError)?.code != "cancelled") {
                        preparingAudio = false
                        error =
                            TaskError((e as? MobileError)?.code ?: "storage", e.message.orEmpty())
                    }
                }
            } finally {
                main.post { if (serial == request) busy = false }
            }
        }
    }

    fun cancel() {
        token?.set(true)
        platform.cancellation.set(true)
        request++
        busy = false
        stopPlayback()
    }

    private fun refreshWorker() {
        val records = Json.parseToJsonElement(engine.records()).jsonArray.map { it.jsonObject }
        main.post {
            recordings = records
            selected?.str("variant_id")?.takeIf(String::isNotEmpty)?.let { id ->
                selected = records.find { it.str("variant_id") == id }
            }
        }
    }

    fun refresh() = run { refreshWorker() }

    fun search() {
        val input = query
        state["query"] = input
        selection++
        editRevision++
        selected = null
        entries = emptyList()
        translation = null
        val key = selection
        run {
            val results =
                Json.parseToJsonElement(engine.lookup(input)).jsonArray.map { it.jsonObject }
            main.post {
                if (key == selection) {
                    entries = results
                    results.firstOrNull()?.let { selectEntry(it) }
                }
            }
        }
    }

    fun selectEntry(entry: JsonObject) {
        cancel()
        selection++
        editRevision++
        selected = entry
        selectedAudio = emptyMap()
        translation = null
        error = null
        val choices = entry["pronunciations"]?.jsonArray.orEmpty().map { it.jsonObject }
        selectedAudio =
            listOf("us", "uk")
                .mapNotNull { region ->
                    choices
                        .firstOrNull { it.str("accent") == region }
                        ?.let { region to DomainKtBridge.audioId(it) }
                }
                .toMap()
        if (showTranslation) translateSelected()
    }

    fun selectSaved(record: JsonObject) {
        cancel()
        selection++
        editRevision++
        selected = record
        entries = emptyList()
        selectedAudio = emptyMap()
        translation = DomainKtBridge.translation(record)
    }

    var collectionSearchSelection: SelectionState? = null

    fun captureSelection() = SelectionState(entries, selected, translation, selectedAudio)

    fun restoreSelection(snapshot: SelectionState) {
        cancel()
        selection++
        editRevision++
        entries = snapshot.entries
        val id = snapshot.selected?.str("variant_id").orEmpty()
        selected =
            if (id.isEmpty()) snapshot.selected else recordings.find { it.str("variant_id") == id }
        selectedAudio = snapshot.audio
        translation =
            if (id.isNotEmpty()) selected?.let(DomainKtBridge::translation)
            else snapshot.translation
    }

    fun chooseAudio(region: String, id: String) {
        selectedAudio = selectedAudio + (region to id)
        stopPlayback()
    }

    private fun metadata(entry: JsonObject): JsonObject {
        if (entry.str("variant_id").isNotEmpty()) return entry
        return JsonObject(
            entry +
                mapOf(
                    "translation_cache" to JsonArray(listOfNotNull(translation)),
                    "sense_id" to JsonPrimitive(entry.str("sense_id")),
                )
        )
    }

    fun translateSelected() {
        val item = selected ?: return
        val input = metadata(item).toString()
        val key = selection
        val revision = editRevision
        val isOffline = offline
        run {
            val result = parseObject(engine.translation(input, isOffline))
            if (key == selection && revision == editRevision) {
                if (item.str("variant_id").isNotEmpty())
                    engine.persistTranslation(item.str("variant_id"), result.toString())
                main.post { if (key == selection && revision == editRevision) translation = result }
            }
        }
    }

    fun personalTranslation(text: String, reset: Boolean) {
        val item = selected ?: return
        editRevision++
        if (item.str("variant_id").isEmpty()) {
            translation =
                if (reset || text.isBlank()) null
                else
                    buildJsonObject {
                        put("language", "russian")
                        put("sense_id", item.str("sense_id"))
                        put("source", "User")
                        put(
                            "options",
                            buildJsonArray {
                                add(
                                    buildJsonObject {
                                        put("id", stableId(text))
                                        put("texts", buildJsonArray { add(text.trim()) })
                                        put("origin", "User edit")
                                        put("matched", true)
                                    }
                                )
                            },
                        )
                    }
            return
        }
        run {
            val updated = parseObject(engine.editTranslation(item.str("variant_id"), text, reset))
            main.post {
                selected = updated
                translation = DomainKtBridge.translation(updated)
            }
            refreshWorker()
        }
    }

    fun chooseTranslation(optionId: String) {
        val item = selected ?: return
        val result = translation ?: return
        editRevision++
        if (item.str("variant_id").isEmpty()) {
            translation = JsonObject(result + ("selected_id" to JsonPrimitive(optionId)))
            return
        }
        run {
            val updated =
                parseObject(
                    engine.chooseTranslation(item.str("variant_id"), result.toString(), optionId)
                )
            main.post {
                selected = updated
                translation = DomainKtBridge.translation(updated)
            }
            refreshWorker()
        }
    }

    fun save(overwrite: Boolean = false) {
        val item = selected ?: return
        val prepared = translation?.toString().orEmpty()
        val choice = selectedAudio.toMap()
        val region = accent
        run {
            if (item.str("variant_id").isNotEmpty()) {
                engine.repair(item.str("variant_id"))
            } else
                for (a in if (region == "both") listOf("us", "uk") else listOf(region)) {
                    val id = choice[a] ?: throw MobileError("accent", a.uppercase())
                    engine.save(item.toString(), id, overwrite, prepared)
                }
            refreshWorker()
            main.post { message = t("Saved", "Сохранено") }
        }
    }

    fun play(region: String = if (accent == "uk") "uk" else "us") {
        val item = selected ?: return
        val key = selection
        stopPlayback()
        run(showProgress = false) {
            val path =
                if (item.str("variant_id").isNotEmpty()) engine.audioPath(item.str("variant_id"))
                else
                    engine.preview(
                        item.toString(),
                        selectedAudio[region] ?: throw MobileError("accent", region.uppercase()),
                    )
            val cancellation = platform.cancellation
            main.post {
                if (key == selection && !cancellation.get()) startPlayback(path, cancellation)
            }
        }
        preparingAudio = true
    }

    private fun startPlayback(path: String, cancellation: AtomicBoolean) {
        stopPlayback()
        if (audioManager.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            error = TaskError("audio_focus", "Audio focus denied")
            return
        }
        preparingAudio = true
        val current = MediaPlayer()
        player = current
        try {
            current.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            current.setOnCompletionListener { stopPlayback() }
            current.setOnErrorListener { _, what, extra ->
                error = TaskError("audio", "MediaPlayer $what/$extra")
                stopPlayback()
                true
            }
            current.setOnPreparedListener { prepared ->
                if (player === prepared && !cancellation.get()) {
                    prepared.start()
                    playing = true
                    preparingAudio = false
                } else if (player === prepared) stopPlayback()
            }
            current.setDataSource(path)
            current.prepareAsync()
        } catch (failure: Exception) {
            error = TaskError("audio", failure.message.orEmpty())
            stopPlayback()
        }
    }

    fun stopPlayback() {
        player?.release()
        player = null
        playing = false
        preparingAudio = false
        audioManager.abandonAudioFocusRequest(focus)
    }

    fun deleteSelected() {
        val id = selected?.str("variant_id").orEmpty()
        if (id.isEmpty()) return
        stopPlayback()
        run {
            engine.deleteRecord(id)
            main.post { selected = null }
            refreshWorker()
        }
    }

    var dictionaryStatus by mutableStateOf("checking")
        private set

    var checkingDictionary by mutableStateOf(false)
        private set

    var wikdictPrompt by mutableStateOf<String?>(null)
        private set

    fun refreshWikdictStatus(prompt: Boolean = false) {
        if (checkingDictionary || (prompt && busy)) return
        checkingDictionary = true
        executor.execute {
            try {
                val status = engine.wikdictStatus()
                main.post {
                    checkingDictionary = false
                    dictionaryStatus = status
                    if (prompt) wikdictPrompt = status
                }
            } catch (failure: Exception) {
                main.post {
                    checkingDictionary = false
                    dictionaryStatus = "unavailable"
                    if (prompt) error = TaskError("storage", failure.message.orEmpty())
                }
            }
        }
    }

    fun requestWikdict() = refreshWikdictStatus(prompt = true)

    fun dismissWikdictPrompt() {
        wikdictPrompt = null
    }

    fun installWikdict() {
        dismissWikdictPrompt()
        run {
            engine.installWikdict()
            main.post {
                dictionaryStatus = "ready"
                message = t("WikDict installed", "WikDict установлен")
            }
        }
    }

    var phrasePlans by mutableStateOf<List<JsonObject>>(emptyList())
        private set

    fun synthesize() {
        val input = query
        val accents = if (accent == "both") listOf("us", "uk") else listOf(accent)
        run {
            val plans = accents.map { parseObject(engine.planPhrase(input, it)) }
            main.post { phrasePlans = plans }
        }
    }

    fun dismissPhrase() {
        phrasePlans = emptyList()
    }

    fun applyPhrase(selections: List<List<String>>) {
        val plans = phrasePlans.toList()
        if (plans.size != selections.size) return
        run {
            val saved = Json.parseToJsonElement(engine.records()).jsonArray.map { it.jsonObject }
            for ((index, plan) in plans.withIndex()) {
                val existing = saved.firstOrNull {
                    it.str("word") == plan.str("word") &&
                        it.str("accent") == plan.str("accent") &&
                        it.bool("combined")
                }
                engine.synthesizeChosen(
                    plan.toString(),
                    JsonArray(selections[index].map(::JsonPrimitive)).toString(),
                    existing?.str("variant_id").orEmpty(),
                )
            }
            refreshWorker()
            main.post {
                phrasePlans = emptyList()
                message = t("Phrase saved", "Фраза сохранена")
            }
        }
    }

    fun export(kind: String, all: Boolean, complete: (File) -> Unit) {
        val id = selected?.str("variant_id").orEmpty()
        val ids = if (!all && id.isNotEmpty()) buildJsonArray { add(id) }.toString() else "[]"
        run {
            val folder = File(getApplication<Application>().cacheDir, "exports").apply { mkdirs() }
            val file =
                File(
                    folder,
                    "cambridge-${System.currentTimeMillis()}.${if (kind == "bundle") "cda" else if (kind == "apkg") "apkg" else "zip"}",
                )
            when (kind) {
                "bundle" -> CollectionTransfer(engine).exportBundle(file.path)
                "apkg" -> AnkiExporter(engine).exportApkg(file.path, ids)
                else -> AnkiExporter(engine).exportTsv(file.path, ids)
            }
            main.post { complete(file) }
        }
    }

    fun importDocument(uri: Uri) = run {
        val application = getApplication<Application>()
        val source = File(application.cacheDir, "import-${System.nanoTime()}.cda")
        try {
            application.contentResolver.openInputStream(uri)!!.use { input ->
                source.outputStream().use { output ->
                    val buffer = ByteArray(65536)
                    var total = 0L
                    while (true) {
                        if (platform.cancelled()) throw MobileError("cancelled")
                        val count = input.read(buffer)
                        if (count < 0) break
                        total += count
                        if (total > 2L * 1024 * 1024 * 1024)
                            throw MobileError("archive", "Collection bundle exceeds 2 GiB")
                        output.write(buffer, 0, count)
                    }
                }
            }
            val preview = parseObject(CollectionTransfer(engine).previewImport(source.path))
            main.post { importPreview = preview }
        } catch (error: Exception) {
            source.delete()
            throw error
        }
    }

    fun applyImport(decisions: JsonObject) {
        val preview = importPreview ?: return
        run {
            val backup =
                CollectionTransfer(engine).applyImport(preview.toString(), decisions.toString())
            refreshWorker()
            main.post {
                importPreview = null
                message =
                    t("Collection imported", "Коллекция импортирована") +
                        if (backup.isNotEmpty())
                            t(
                                "; previous collection backed up",
                                "; прежняя коллекция сохранена в резервной копии",
                            )
                        else ""
            }
        }
    }

    fun dismissImport() {
        importPreview = null
    }

    fun importReadError(details: String) {
        error = TaskError("archive", details)
    }

    fun clearError() {
        error = null
    }

    fun background() {
        cancel()
        stopPlayback()
    }

    override fun onCleared() {
        background()
        getApplication<Application>().unregisterReceiver(noisy)
        executor.shutdownNow()
        super.onCleared()
    }
}

/** Keep JSON extension helpers private to the presentation layer. Domain rules stay in shared. */
internal object DomainKtBridge {
    fun audioId(audio: JsonObject) =
        stableId("cambridge-audio", audio.str("accent"), audio.str("url"))

    fun translation(record: JsonObject): JsonObject? {
        val result = cachedTranslation(record) ?: return null
        return Json.encodeToJsonElement(TranslationResult.serializer(), result).jsonObject
    }
}
