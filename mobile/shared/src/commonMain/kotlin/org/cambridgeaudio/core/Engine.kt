package org.cambridgeaudio.core

import com.fleeksoft.ksoup.Ksoup
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import okio.Path.Companion.toPath

/** UI-independent application operations, shared by Kotlin/Compose and SwiftUI. */
class Engine(val collectionPath: String, val cachePath: String, val platform: Platform) {
    internal val cache = cachePath.toPath()
    // Initialize inside a throwing operation so Swift receives startup I/O errors as NSError.
    internal val storage by lazy {
        Storage(collectionPath.toPath(), platform).also { it.fs.createDirectories(cache) }
    }
    private val pages = linkedMapOf<String, String>()
    private var nextRequest = 0L

    internal fun fetch(
        url: String,
        maxBytes: Long = 8L * 1024 * 1024,
        cached: Boolean = false,
    ): ByteArray {
        if (cached)
            pages[url]?.let {
                return it.encodeToByteArray()
            }
        require(url.startsWith("https://dictionary.cambridge.org/") || url == WIKDICT_URL)
        var response: HttpResult? = null
        for (attempt in 0..2) {
            storage.checkCancelled()
            var remaining = nextRequest - platform.nowSeconds()
            if (remaining > 30) throw MobileError("blocked", "Retry after $remaining seconds")
            while (remaining > 0) {
                platform.pause(100)
                storage.checkCancelled()
                remaining = nextRequest - platform.nowSeconds()
            }
            nextRequest = platform.nowSeconds() + 1
            response =
                try {
                    platform.fetch(url, maxBytes)
                } catch (e: Exception) {
                    if (e is MobileError && e.code == "cancelled") throw e
                    throw MobileError("network", e.message.orEmpty())
                }
            if (response.status != 429) break
            nextRequest =
                platform.nowSeconds() + (response.retryAfter.toLongOrNull() ?: (2L shl attempt))
        }
        val result = response ?: throw MobileError("network")
        if (result.status == 403 || result.status == 429)
            throw MobileError("blocked", "HTTP ${result.status}")
        if (result.status == 404) throw MobileError("absent", url)
        if (result.status !in 200..299) throw MobileError("network", "HTTP ${result.status}")
        val prefix = result.body.take(20_000).toByteArray().decodeToString().lowercase()
        if (listOf("cf-chl-", "captcha", "access denied").any { it in prefix })
            throw MobileError("blocked", "Blocking page")
        if (result.body.size > maxBytes) throw MobileError("network", "Oversized response")
        if (cached) {
            if (pages.size >= 64) pages.remove(pages.keys.first())
            pages[url] = result.body.decodeToString()
        }
        storage.checkCancelled()
        return result.body
    }

    private fun validateDownloadedAudio(bytes: ByteArray) {
        if (!isMp3(bytes)) throw MobileError("audio", "Response is not MP3")
        val path = cache / ("validate-" + platform.randomId() + ".mp3")
        try {
            storage.atomic(path, bytes)
            if (!platform.validateAudio(path.toString()))
                throw MobileError("audio", "MP3 cannot be decoded")
        } finally {
            storage.fs.delete(path, mustExist = false)
        }
    }

    @Throws(Exception::class)
    fun lookup(input: String): String {
        val word = normalizeWord(input)
        val url = dictionaryUrl(word)
        val html = fetch(url, cached = true).decodeToString()
        val entries = parseEntries(html, url)
        if (entries.isEmpty()) {
            pages.remove(url)
            val soup = Ksoup.parse(html)
            if (soup.select(".entry-body__el").isNotEmpty())
                throw MobileError("parser", "Dictionary blocks have no supported headers")
            if (
                soup
                    .select(
                        ".no-results, .no-results-found, .spellcheck, .didyoumean, .search-result"
                    )
                    .isNotEmpty()
            )
                throw MobileError("absent", word)
            throw MobileError("parser", "Unrecognized Cambridge HTML for $word")
        }
        return json.encodeToString(entries)
    }

    @Throws(Exception::class)
    fun records(): String =
        JsonArray(storage.scan().map { it.with("media_valid" to storage.valid(it)) }).toString()

    @Throws(Exception::class)
    fun preview(entryJson: String, audioId: String): String {
        val entry = json.decodeFromString<Entry>(entryJson)
        val audio =
            entry.pronunciations.singleOrNull { it.id == audioId } ?: throw MobileError("accent")
        val saved =
            storage.scan().firstOrNull {
                it.text("audio_url") == audio.url &&
                    it.text("accent") == audio.accent &&
                    storage.valid(it)
            }
        if (saved != null) return (storage.root / saved.text("audio_file")).toString()
        val bytes = fetch(audio.url, 32L * 1024 * 1024)
        validateDownloadedAudio(bytes)
        val path = cache / "preview-${audio.id}.${audio.accent}.mp3"
        storage.atomic(path, bytes)
        return path.toString()
    }

    @Throws(Exception::class)
    fun save(
        entryJson: String,
        audioId: String,
        overwrite: Boolean,
        translationJson: String = "",
    ): String {
        val entry = json.decodeFromString<Entry>(entryJson)
        val audio =
            entry.pronunciations.singleOrNull { it.id == audioId } ?: throw MobileError("accent")
        val records = storage.scan()
        val choice = stableId(entry.sense_id, audio.accent, audio.url)
        val existing = records.singleOrNull {
            it.text("audio_url") == audio.url &&
                it.text("accent") == audio.accent &&
                (it.text("source_sense_id", it.text("sense_id")) == entry.sense_id ||
                    it.text("variant_id") == choice ||
                    it.text("variant_id") in entry.legacy_ids)
        }
        val id = existing?.text("variant_id") ?: platform.randomId().replace("-", "").take(24)
        val shared = records.firstOrNull {
            it.text("audio_url") == audio.url &&
                it.text("accent") == audio.accent &&
                storage.valid(it)
        }
        val name =
            existing?.text("audio_file")
                ?: shared?.text("audio_file")
                ?: audioFilename(normalizeWord(entry.word), audio.accent, audio.id)
        var bytes =
            if (!overwrite && shared != null) storage.read(storage.root / shared.text("audio_file"))
            else fetch(audio.url, 32L * 1024 * 1024)
        validateDownloadedAudio(bytes)
        storage.checkCancelled()
        // Publish complete media before its sidecar. Unreferenced audio after a crash
        // is recoverable; no previously saved metadata is removed on cancellation.
        val sense = existing?.text("sense_id")?.ifEmpty { entry.sense_id } ?: entry.sense_id
        var metadata =
            (existing ?: JsonObject(emptyMap())).with(
                "version" to 3,
                "word" to entry.word,
                "accent" to audio.accent,
                "ipa" to audio.ipa,
                "definition" to entry.definition,
                "part_of_speech" to entry.part_of_speech,
                "entry_id" to
                    (existing?.text("entry_id")?.ifEmpty { entry.entry_id } ?: entry.entry_id),
                "sense_id" to sense,
                "source_entry_id" to entry.entry_id,
                "source_sense_id" to entry.sense_id,
                "variant_id" to id,
                "source_url" to entry.source_url,
                "audio_url" to audio.url,
                "lemma" to entry.lemma,
                "combined" to false,
                "audio_file" to name,
                "audio_sha256" to sha256(bytes),
                "separate_metadata" to true,
                "metadata_path" to (existing?.text("metadata_path") ?: "$id.${audio.accent}.json"),
            )
        if (translationJson.isNotEmpty()) {
            val prepared = json.decodeFromString<TranslationResult>(translationJson)
            if (prepared.sense_id == entry.sense_id)
                metadata = mergeResult(metadata, prepared.copy(sense_id = sense))
        } else if (existing == null) {
            records
                .firstOrNull {
                    it.text("word") == entry.word &&
                        it.text("source_sense_id", it.text("sense_id")) == entry.sense_id
                }
                ?.let { related ->
                    val cache =
                        related.array("translation_cache").filter { raw ->
                            runCatching {
                                    val t = json.decodeFromJsonElement<TranslationResult>(raw)
                                    t.source == "User" ||
                                        t.selected_id.isNotEmpty() ||
                                        t.texts.isNotEmpty()
                                }
                                .getOrDefault(false)
                        }
                    metadata =
                        metadata.with(
                            "translation_cache" to
                                JsonArray(cache.map { it.jsonObject.with("sense_id" to sense) })
                        )
                }
        }
        val updates =
            linkedMapOf(
                name to bytes,
                metadata.text("metadata_path") to storage.metadataBytes(metadata),
            )
        if (overwrite)
            records
                .filter { it.text("audio_file") == name && it.text("variant_id") != id }
                .forEach {
                    updates[it.text("metadata_path")] =
                        storage.metadataBytes(it.with("audio_sha256" to sha256(bytes)))
                }
        storage.commitFiles(updates)
        return metadata.toString()
    }

    @Throws(Exception::class) fun deleteRecord(identity: String) = storage.remove(identity)

    @Throws(Exception::class)
    fun audioPath(identity: String): String {
        val data = storage.identity(identity)
        if (!storage.valid(data)) throw MobileError("audio", "Missing or corrupt MP3; use repair")
        return (storage.root / data.text("audio_file")).toString()
    }

    @Throws(Exception::class)
    fun repair(identity: String): String {
        val data = storage.identity(identity)
        if (data.flag("combined")) {
            val plan = data["phrase_plan"]
            val selections = data["phrase_selections"]
            if (plan != null || selections != null) {
                if (plan !is JsonObject || selections !is JsonArray)
                    throw MobileError("input", "Invalid saved phrase plan")
                return synthesizeChosen(plan.toString(), selections.toString(), identity)
            }
            return synthesize(data.text("word"), data.text("accent"), identity)
        }
        val url = data.text("audio_url")
        if (url.isEmpty())
            throw MobileError(
                "audio",
                "Legacy entry has no source URL; choose its source meaning explicitly",
            )
        val bytes = fetch(url, 32L * 1024 * 1024)
        validateDownloadedAudio(bytes)
        val updates = linkedMapOf(data.text("audio_file") to bytes)
        storage
            .scan()
            .filter { it.text("audio_file") == data.text("audio_file") }
            .forEach {
                updates[it.text("metadata_path")] =
                    storage.metadataBytes(it.with("audio_sha256" to sha256(bytes)))
            }
        storage.commitFiles(updates)
        return data.toString()
    }

    @Throws(Exception::class)
    fun editTranslation(identity: String, text: String, reset: Boolean): String {
        val current = storage.identity(identity)
        val sense = current.text("sense_id")
        val meaning = current.text("source_sense_id", sense).ifEmpty { identity }
        for (record in
            storage.scan().filter {
                it.text("word") == current.text("word") &&
                    it.text("source_sense_id", it.text("sense_id")).ifEmpty {
                        it.text("variant_id")
                    } == meaning
            }) {
            var edited =
                record.with(
                    "translation_cache" to
                        JsonArray(
                            record.array("translation_cache").filterNot {
                                it.jsonObject.text("source") == "User" &&
                                    it.jsonObject.text("language") == "russian" &&
                                    it.jsonObject.text("sense_id") == record.text("sense_id")
                            }
                        )
                )
            if (!reset && text.isNotBlank())
                edited =
                    mergeResult(
                        edited,
                        TranslationResult(
                            "russian",
                            record.text("sense_id"),
                            "User",
                            listOf(
                                TranslationOption(
                                    stableId(text),
                                    listOf(text.trim()),
                                    origin = "User edit",
                                    matched = true,
                                )
                            ),
                        ),
                    )
            storage.save(edited)
        }
        return storage.identity(identity).toString()
    }

    @Throws(Exception::class)
    fun chooseTranslation(identity: String, resultJson: String, optionId: String): String {
        val result = json.decodeFromString<TranslationResult>(resultJson)
        val current = storage.identity(identity)
        if (
            result.sense_id != current.text("sense_id") || result.options.none { it.id == optionId }
        )
            throw MobileError("stale")
        val meaning = current.text("source_sense_id", current.text("sense_id"))
        storage
            .scan()
            .filter {
                it.text("word") == current.text("word") &&
                    it.text("source_sense_id", it.text("sense_id")) == meaning
            }
            .forEach {
                storage.save(
                    mergeResult(
                        it,
                        result.copy(sense_id = it.text("sense_id"), selected_id = optionId),
                    )
                )
            }
        return storage.identity(identity).toString()
    }

    /** The caller presents this preview only if its search/meaning token still matches. */
    @Throws(Exception::class)
    fun translation(metadataJson: String, offline: Boolean): String {
        val metadata = obj(metadataJson)
        val cached = cachedTranslation(metadata)
        if (
            cached != null &&
                (cached.source == "User" || cached.texts.isNotEmpty() || cached.source == "WikDict")
        )
            return json.encodeToString(cached)
        var status = "absent"
        var error = ""
        var unmatched = cached
        if (!offline && cached == null)
            try {
                val url = dictionaryUrl(metadata.text("word"), "english-russian")
                val soup = Ksoup.parse(fetch(url, cached = true).decodeToString(), url)
                val options =
                    soup
                        .select(".entry-body__el .def-body")
                        .mapNotNull { body ->
                            val texts = body.select(".trans").map { it.text() }.distinct()
                            if (texts.isEmpty()) return@mapNotNull null
                            val owner = body.parents().firstOrNull { it.hasClass("entry-body__el") }
                            val part = owner?.selectFirst(".pos, .dpos")?.text().orEmpty()
                            val sense =
                                body.parents().firstOrNull { it.hasClass("def-block") } ?: body
                            val gloss =
                                sense
                                    .selectFirst(".def.ddef_d")
                                    ?.text()
                                    .orEmpty()
                                    .removeSuffix(":")
                                    .trimEnd()
                            TranslationOption(
                                stableId(part, gloss, *texts.toTypedArray()),
                                texts,
                                gloss,
                                part,
                                url,
                            )
                        }
                        .distinctBy { it.id }
                if (options.isNotEmpty()) {
                    unmatched =
                        align(
                            TranslationResult(
                                "russian",
                                metadata.text("sense_id"),
                                "Cambridge",
                                options,
                            ),
                            metadata.text("definition"),
                            metadata.text("part_of_speech"),
                        )
                    if (unmatched.texts.isNotEmpty()) return json.encodeToString(unmatched)
                } else if (soup.select(".entry-body__el").isEmpty()) {
                    status = "parser"
                    error = "Unrecognized bilingual HTML"
                }
            } catch (e: MobileError) {
                if (e.code == "cancelled") throw e
                status = e.code
                error = e.detail
            }
        try {
            val local = wikdictLookup(metadata.text("lemma").ifEmpty { metadata.text("word") })
            if (local.isNotEmpty()) {
                val translated =
                    align(
                        TranslationResult(
                            "russian",
                            metadata.text("sense_id"),
                            "WikDict",
                            local,
                            status = status,
                            error = error,
                            version = WIKDICT_VERSION,
                        ),
                        metadata.text("definition"),
                        metadata.text("part_of_speech"),
                    )
                if (translated.texts.isNotEmpty() || unmatched == null)
                    return json.encodeToString(translated)
            }
        } catch (e: MobileError) {
            if (e.code == "cancelled") throw e
            if (unmatched == null)
                return json.encodeToString(
                    TranslationResult(
                        "russian",
                        metadata.text("sense_id"),
                        "WikDict",
                        status = e.code,
                        error =
                            listOf(error, e.detail).filter(String::isNotEmpty).joinToString("; "),
                    )
                )
        }
        return json.encodeToString(
            unmatched
                ?: TranslationResult(
                    "russian",
                    metadata.text("sense_id"),
                    "Cambridge",
                    status = status,
                    error = error,
                )
        )
    }

    @Throws(Exception::class)
    fun persistTranslation(identity: String, resultJson: String): String {
        val current = storage.identity(identity)
        val result = json.decodeFromString<TranslationResult>(resultJson)
        if (current.text("sense_id") != result.sense_id) throw MobileError("stale")
        storage.save(mergeResult(current, result))
        return storage.identity(identity).toString()
    }

    internal fun mergeResult(metadata: JsonObject, incoming: TranslationResult): JsonObject {
        var result = incoming
        val previous =
            metadata
                .array("translation_cache")
                .find { raw ->
                    val o = raw.jsonObject
                    o.text("language") == incoming.language &&
                        o.text("sense_id") == incoming.sense_id &&
                        o.text("source") == incoming.source
                }
                ?.jsonObject
        if (
            previous != null &&
                (incoming.source == "User" ||
                    incoming.selected_id.isEmpty() && previous.text("selected_id").isNotEmpty())
        )
            result = json.decodeFromJsonElement(previous)
        val resultData = json.encodeToJsonElement(result).jsonObject
        val options =
            resultData.array("options").map { option ->
                val old =
                    previous
                        ?.array("options")
                        ?.firstOrNull { it.jsonObject.text("id") == option.jsonObject.text("id") }
                        ?.jsonObject
                JsonObject((old ?: JsonObject(emptyMap())) + option.jsonObject)
            }
        val updated =
            JsonObject((previous ?: JsonObject(emptyMap())) + resultData)
                .with("options" to JsonArray(options))
        val cache =
            metadata.array("translation_cache").filterNot {
                val o = it.jsonObject
                o.text("language") == result.language &&
                    o.text("sense_id") == result.sense_id &&
                    o.text("source") == result.source
            } + JsonObject(updated)
        var combined =
            metadata.with(
                "translation_cache" to JsonArray(cache),
                "translation_language" to result.language,
            )
        combined =
            combined.with(
                "translations" to (cachedTranslation(combined)?.texts ?: emptyList()).strings()
            )
        return combined
    }

    @Throws(Exception::class)
    fun installWikdict(): String {
        val bytes = fetch(WIKDICT_URL, WIKDICT_SIZE)
        if (bytes.size.toLong() != WIKDICT_SIZE || sha256(bytes) != WIKDICT_SHA256)
            throw MobileError("dictionary_corrupt", "Download checksum / size mismatch")
        val staging = cache / "wikdict-${platform.randomId()}.sqlite3"
        try {
            storage.atomic(staging, bytes)
            validateWikdict(staging.toString())
            storage.atomic(storage.root.parent!! / "en-ru-$WIKDICT_VERSION.sqlite3", bytes)
            storage.atomic(
                storage.root.parent!! / "WIKDICT-LICENSE.txt",
                (WIKDICT_ATTRIBUTION + "\n$WIKDICT_URL\n$WIKDICT_SHA256\n").encodeToByteArray(),
            )
        } finally {
            storage.fs.delete(staging, mustExist = false)
        }
        return WIKDICT_VERSION
    }

    private fun validateWikdict(path: String) {
        val check =
            json
                .parseToJsonElement(platform.sqliteQuery(path, "PRAGMA quick_check", emptyList()))
                .jsonArray
        if (check.firstOrNull()?.jsonArray?.firstOrNull()?.jsonPrimitive?.content != "ok")
            throw MobileError("dictionary_corrupt", "SQLite integrity check")
        platform.sqliteQuery(
            path,
            "SELECT written_rep, lexentry, sense, trans_list FROM translation LIMIT 1",
            emptyList(),
        )
    }

    /** Checks the installed pinned package without downloading or modifying it. */
    @Throws(Exception::class)
    fun wikdictStatus(): String =
        try {
            verifiedWikdictPath()
            "ready"
        } catch (failure: MobileError) {
            when (failure.code) {
                "dictionary_missing" -> "missing"
                "dictionary_corrupt" -> "corrupt"
                else -> throw failure
            }
        }

    private fun verifiedWikdictPath(): okio.Path {
        val path = storage.root.parent!! / "en-ru-$WIKDICT_VERSION.sqlite3"
        if (!storage.fs.exists(path))
            throw MobileError(
                "dictionary_missing",
                "Install WikDict en → ru explicitly in Settings",
            )
        if (storage.fs.metadata(path).size != WIKDICT_SIZE)
            throw MobileError("dictionary_corrupt", "Reinstall WikDict")
        val bytes = storage.read(path)
        if (bytes.size.toLong() != WIKDICT_SIZE || sha256(bytes) != WIKDICT_SHA256)
            throw MobileError("dictionary_corrupt", "Reinstall WikDict")
        validateWikdict(path.toString())
        return path
    }

    private fun wikdictLookup(word: String): List<TranslationOption> {
        val path = verifiedWikdictPath()
        val rows =
            json
                .parseToJsonElement(
                    platform.sqliteQuery(
                        path.toString(),
                        "SELECT lexentry,sense,trans_list FROM translation WHERE written_rep=? ORDER BY score DESC,lexentry,sense",
                        listOf(word),
                    )
                )
                .jsonArray
        return rows
            .mapNotNull { row ->
                val values = row.jsonArray
                val lexentry = values[0].jsonPrimitive.contentOrNull.orEmpty()
                val gloss = cleanWiki(values[1].jsonPrimitive.contentOrNull.orEmpty())
                val texts =
                    values[2]
                        .jsonPrimitive
                        .contentOrNull
                        .orEmpty()
                        .split(Regex("\\s+\\|\\s+"))
                        .map(::cleanWiki)
                        .filter(String::isNotEmpty)
                        .distinct()
                if (texts.isEmpty()) null
                else
                    TranslationOption(
                        stableId(lexentry, gloss, *texts.toTypedArray()),
                        texts,
                        gloss,
                        lexentry.split("__").getOrNull(1)?.lowercase().orEmpty(),
                        "$WIKDICT_URL#${lexentry.ifEmpty { word }}",
                    )
            }
            .distinctBy { it.id }
    }

    @Throws(Exception::class)
    fun planPhrase(input: String, accent: String): String {
        val word = normalizeWord(input)
        if (word.split(' ').size < 2 || accent !in setOf("us", "uk")) throw MobileError("input")
        val segments =
            word.split(' ').map { token ->
                val entries = json.decodeFromString<List<Entry>>(lookup(token))
                val options =
                    entries
                        .flatMap { it.pronunciations }
                        .filter { it.accent == accent }
                        .distinctBy { it.id }
                if (options.isEmpty()) throw MobileError("accent", "$token: $accent")
                document(
                    "word" to token,
                    "options" to
                        JsonArray(
                            options.map { audio ->
                                json.encodeToJsonElement(audio).jsonObject.with("id" to audio.id)
                            }
                        ),
                )
            }
        return document("word" to word, "accent" to accent, "segments" to JsonArray(segments))
            .toString()
    }

    @Throws(Exception::class)
    fun synthesize(input: String, accent: String, replacingIdentity: String = ""): String {
        val plan = obj(planPhrase(input, accent))
        val selections =
            plan.array("segments").map { raw ->
                val choices = raw.jsonObject.array("options")
                if (choices.size != 1)
                    throw MobileError("ambiguous_phrase", raw.jsonObject.text("word"))
                choices.single().jsonObject.text("id")
            }
        return synthesizeChosen(plan.toString(), selections.strings().toString(), replacingIdentity)
    }

    @Throws(Exception::class)
    fun synthesizeChosen(
        planJson: String,
        selectionsJson: String,
        replacingIdentity: String = "",
    ): String {
        val plan = obj(planJson)
        val word = normalizeWord(plan.text("word"))
        val accent = plan.text("accent")
        val selections =
            json.parseToJsonElement(selectionsJson).jsonArray.map { it.jsonPrimitive.content }
        val segments = plan.array("segments")
        if (
            accent !in setOf("us", "uk") ||
                segments.size < 2 ||
                segments.size != selections.size ||
                segments.map { it.jsonObject.text("word") } != word.split(' ')
        )
            throw MobileError("input")
        val previous =
            if (replacingIdentity.isNotEmpty()) storage.identity(replacingIdentity) else null
        if (
            previous != null &&
                (!previous.flag("combined") ||
                    previous.text("word") != word ||
                    previous.text("accent") != accent)
        )
            throw MobileError("stale")
        if (
            previous == null &&
                storage.scan().any {
                    it.flag("combined") && it.text("word") == word && it.text("accent") == accent
                }
        )
            throw MobileError("replace_required", "Confirm replacing the existing phrase")
        val temp = cache / ("phrase-" + platform.randomId())
        storage.fs.createDirectories(temp)
        try {
            val paths = segments.mapIndexed { index, raw ->
                storage.checkCancelled()
                val audio =
                    raw.jsonObject
                        .array("options")
                        .map { it.jsonObject }
                        .singleOrNull {
                            it.text("id") == selections[index] && it.text("accent") == accent
                        } ?: throw MobileError("accent")
                val bytes = fetch(audio.text("url"), 32L * 1024 * 1024)
                if (!isMp3(bytes)) throw MobileError("audio", raw.jsonObject.text("word"))
                val path = temp / "$index.mp3"
                storage.atomic(path, bytes)
                path.toString()
            }
            val output = temp / "combined.mp3"
            platform.synthesize(paths, output.toString())
            storage.checkCancelled()
            val bytes = storage.read(output)
            if (!isMp3(bytes)) throw MobileError("audio", "Encoder did not produce MP3")
            val id = previous?.text("variant_id") ?: platform.randomId().replace("-", "").take(24)
            val filename = previous?.text("audio_file") ?: audioFilename(word, accent, id)
            val result =
                (previous ?: JsonObject(emptyMap())).with(
                    "version" to 3,
                    "word" to word,
                    "accent" to accent,
                    "ipa" to "",
                    "definition" to "",
                    "combined" to true,
                    "variant_id" to id,
                    "sense_id" to "",
                    "audio_file" to filename,
                    "audio_sha256" to sha256(bytes),
                    "source_url" to dictionaryUrl(word),
                    "metadata_path" to (previous?.text("metadata_path") ?: "$id.$accent.json"),
                    "separate_metadata" to true,
                    "phrase_plan" to plan,
                    "phrase_selections" to selections.strings(),
                )
            storage.commitFiles(
                linkedMapOf(
                    filename to bytes,
                    result.text("metadata_path") to storage.metadataBytes(result),
                )
            )
            return result.toString()
        } finally {
            storage.fs.deleteRecursively(temp, mustExist = false)
        }
    }

    companion object {
        const val WIKDICT_VERSION = "2_2026-06"
        const val WIKDICT_URL =
            "https://download.wikdict.com/dictionaries/sqlite/2_2026-06/en-ru.sqlite3"
        const val WIKDICT_SIZE = 20938752L
        const val WIKDICT_SHA256 =
            "3f65395883b996131c9b7a7b7b7c14c1b4458c892fae0050decd71dc0a3b4b0a"
        const val WIKDICT_ATTRIBUTION =
            "WikDict by Karl Bartel, https://www.wikdict.com/page/download. Wiktionary contributors via DBnary (https://kaiko.getalp.org/about-dbnary/). CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/. Displayed/exported translations have wiki markup removed and duplicates removed. Dictionary content is separate from the application's Apache-2.0 code."
    }
}

internal fun cleanWiki(text: String): String {
    var value = Regex("\\[\\[(?:[^\\]|]+\\|)?([^\\]]+)\\]\\]").replace(text, "$1")
    value =
        Regex("\\{\\{(?:l|m|t|t\\+)\\|[^|{}]+\\|([^|{}]+)(?:\\|[^{}]*)?\\}\\}").replace(value, "$1")
    value = Regex("\\{\\{[^{}]*\\}\\}").replace(value, "")
    value =
        Regex("\\[https?://\\S+\\s+([^\\]]+)\\]")
            .replace(value, "$1")
            .replace("'''", "")
            .replace("''", "")
    return Ksoup.parse(value)
        .text()
        .split(Regex("\\s+"))
        .filter(String::isNotEmpty)
        .joinToString(" ")
}

/** String-only bridge keeps Swift independent of Kotlin serialization internals. */
class MobileJson {
    fun audioId(accent: String, url: String): String = stableId("cambridge-audio", accent, url)

    fun cachedTranslationJson(metadataJson: String): String =
        cachedTranslation(obj(metadataJson))?.let { json.encodeToString(it) }.orEmpty()

    fun translationTexts(resultJson: String): String =
        if (resultJson.isEmpty()) "[]"
        else json.encodeToString(json.decodeFromString<TranslationResult>(resultJson).texts)

    fun personalTranslation(senseId: String, text: String): String =
        json.encodeToString(
            TranslationResult(
                "russian",
                senseId,
                "User",
                listOf(
                    TranslationOption(
                        stableId(text),
                        listOf(text.trim()),
                        origin = "User edit",
                        matched = true,
                    )
                ),
            )
        )
}
