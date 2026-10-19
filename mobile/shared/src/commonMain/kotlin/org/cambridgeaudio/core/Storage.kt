package org.cambridgeaudio.core

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import okio.HashingSource
import okio.Path
import okio.buffer

/** Persistent sidecars are the source of truth. Any UI list is a rebuildable index. */
internal class Storage(val root: Path, val platform: Platform) {
    val fs = systemFileSystem()

    init {
        val journal = root.parent!! / ".${root.name}.import.json"
        if (fs.exists(journal) && !fs.exists(root)) {
            val state = obj(read(journal).decodeToString())
            val name = state.text("backup")
            if (!Regex("\\.${Regex.escape(root.name)}\\.backup-[a-f0-9]{32}").matches(name))
                throw MobileError("archive", "Invalid recovery journal")
            val backup = root.parent!! / name
            if (fs.metadata(backup).symlinkTarget != null)
                throw MobileError("archive", "Unsafe backup")
            fs.atomicMove(backup, root)
            fs.delete(journal)
        }
        fs.createDirectories(root)
        recoverWrite()
    }

    /**
     * Multi-file media/metadata commits can finish after cancellation once their durable intent
     * exists. Startup completes a committed interrupted write.
     */
    private fun recoverWrite() {
        val journal = root.parent!! / ".${root.name}.write.json"
        if (!fs.exists(journal)) return
        val state = obj(read(journal).decodeToString())
        val pendingName = safeFilename(state.text("pending"))
        if (!pendingName.startsWith(".${root.name}.pending-"))
            throw MobileError("storage", "Invalid pending write")
        val pending = root.parent!! / pendingName
        for (raw in state.array("files")) {
            val item = raw.jsonObject
            val name = safeFilename(item.text("name"))
            val source = pending / name
            val destination = root / name
            if (fs.exists(source)) {
                if (sha256(read(source)) != item.text("sha256"))
                    throw MobileError("storage", "Damaged staged write")
                fs.atomicMove(source, destination)
            } else if (!fs.exists(destination) || sha256(read(destination)) != item.text("sha256"))
                throw MobileError("storage", "Incomplete interrupted write")
        }
        fs.delete(journal)
        fs.deleteRecursively(pending, mustExist = false)
    }

    fun commitFiles(updates: Map<String, ByteArray>) {
        recoverWrite()
        val pending = root.parent!! / ".${root.name}.pending-${platform.randomId()}"
        val journal = root.parent!! / ".${root.name}.write.json"
        fs.createDirectories(pending)
        var committed = false
        try {
            for ((name, bytes) in updates) {
                safeFilename(name)
                if (fs.metadataOrNull(root / name)?.symlinkTarget != null)
                    throw MobileError("storage", "Refuse symbolic-link destination")
                atomic(pending / name, bytes)
            }
            checkCancelled()
            val state =
                document(
                    "version" to 1,
                    "pending" to pending.name,
                    "files" to
                        JsonArray(
                            updates.map { (name, bytes) ->
                                document("name" to name, "sha256" to sha256(bytes))
                            }
                        ),
                )
            // Last cancellation check is before publishing the durable commit.
            atomicJson(journal, state)
            committed = true
            recoverWrite()
        } finally {
            if (!committed) fs.deleteRecursively(pending, mustExist = false)
        }
    }

    fun metadataBytes(data: JsonObject): ByteArray =
        json.encodeToString(JsonObject(data - "metadata_path" - "media_valid")).encodeToByteArray()

    fun read(path: Path, limit: Long = 64L * 1024 * 1024): ByteArray {
        val meta = fs.metadata(path)
        if (
            meta.symlinkTarget != null ||
                !meta.isRegularFile ||
                (meta.size ?: Long.MAX_VALUE) > limit
        )
            throw MobileError("storage", "Unsafe or oversized file: $path")
        return fs.read(path) { readByteArray() }
    }

    fun fileHash(path: Path): String {
        if (fs.metadata(path).symlinkTarget != null)
            throw MobileError("storage", "Refuse symbolic link")
        val hashing = HashingSource.sha256(fs.source(path))
        val source = hashing.buffer()
        try {
            while (!source.exhausted()) source.skip(
                minOf(65536L, source.buffer.size.coerceAtLeast(1))
            )
        } finally {
            source.close()
        }
        return hashing.hash.hex()
    }

    fun atomic(path: Path, bytes: ByteArray) {
        fs.createDirectories(path.parent!!)
        val temporary = path.parent!! / ("." + platform.randomId() + ".tmp")
        try {
            fs.write(temporary) { write(bytes) }
            platform.syncFile(temporary.toString())
            checkCancelled()
            fs.atomicMove(temporary, path)
        } finally {
            fs.delete(temporary, mustExist = false)
        }
    }

    fun atomicJson(path: Path, data: JsonObject) =
        atomic(path, json.encodeToString(data).encodeToByteArray())

    fun checkCancelled() {
        if (platform.cancelled()) throw MobileError("cancelled")
    }

    fun scan(): List<JsonObject> {
        recoverWrite()
        val result = mutableListOf<JsonObject>()
        val referenced = mutableSetOf<String>()
        for (path in
            fs.list(root).filter { it.name.endsWith(".json") && !it.name.startsWith('.') }) {
            val raw =
                try {
                    obj(read(path).decodeToString())
                } catch (e: Exception) {
                    throw MobileError("metadata", "$path: ${e.message}")
                }
            val version = raw["version"]?.jsonPrimitive?.intOrNull
            if (version !in 1..3)
                throw MobileError("schema", "Unsupported metadata version $version: $path")
            val accent = path.name.removeSuffix(".json").substringAfterLast('.')
            if (accent !in setOf("us", "uk")) continue
            var data = raw
            val audio =
                if (version == 3) raw.text("audio_file")
                else path.name.removeSuffix(".json") + ".mp3"
            safeFilename(audio)
            if (!audio.endsWith(".$accent.mp3"))
                throw MobileError("metadata", "Invalid audio reference: $audio")
            val identity =
                recordId(raw, accent, path.name.substringBeforeLast('.').substringBeforeLast('.'))
            if (
                version == 1 &&
                    raw.array("translation_cache").isEmpty() &&
                    raw.array("translations").isNotEmpty() &&
                    raw.text("translation_language").isNotEmpty()
            ) {
                val texts = raw.array("translations").map { it.jsonPrimitive.content }
                val cache =
                    TranslationResult(
                        raw.text("translation_language"),
                        raw.text("sense_id"),
                        "Cambridge",
                        listOf(
                            TranslationOption(
                                stableId(*texts.toTypedArray()),
                                texts,
                                origin = "Legacy JSON cache; sense association unverified",
                            )
                        ),
                    )
                data =
                    data.with(
                        "translation_cache" to JsonArray(listOf(json.encodeToJsonElement(cache)))
                    )
            }
            data =
                data.with(
                    "version" to 3,
                    "accent" to accent,
                    "audio_file" to audio,
                    "variant_id" to identity,
                    "separate_metadata" to true,
                    "metadata_path" to path.name,
                )
            if (result.any { it.text("variant_id") == identity })
                throw MobileError("metadata", "Duplicate permanent ID $identity")
            referenced += audio
            result += data
        }
        for (path in fs.list(root).filter { it.name.endsWith(".mp3") && it.name !in referenced }) {
            val accent = path.name.removeSuffix(".mp3").substringAfterLast('.')
            if (accent !in setOf("us", "uk")) continue
            var word = path.name.removeSuffix(".$accent.mp3")
            if (word.startsWith('_') && audioFilename(word.drop(1), accent) == path.name)
                word = word.drop(1)
            val identity = stableId("legacy", word.lowercase(), accent, "recording")
            if (result.any { it.text("variant_id") == identity }) continue
            result +=
                document(
                    "version" to 3,
                    "word" to word,
                    "accent" to accent,
                    "ipa" to "",
                    "definition" to "",
                    "variant_id" to identity,
                    "audio_file" to path.name,
                    "metadata_path" to "${path.name.removeSuffix(".mp3")}.json",
                    "separate_metadata" to true,
                )
        }
        return result.sortedWith(compareBy({ it.text("word").lowercase() }, { it.text("accent") }))
    }

    fun valid(data: JsonObject): Boolean = runCatching {
        val bytes = read(root / safeFilename(data.text("audio_file")))
        isMp3(bytes) &&
            (data.text("audio_sha256").isEmpty() || sha256(bytes) == data.text("audio_sha256"))
    }
        .getOrDefault(false)

    fun save(data: JsonObject) {
        val path = root / safeFilename(data.text("metadata_path"))
        atomicJson(path, JsonObject(data - "metadata_path" - "media_valid"))
    }

    fun identity(id: String) =
        scan().singleOrNull { it.text("variant_id") == id } ?: throw MobileError("missing", id)

    fun mapping(): JsonObject {
        val path = root / ".anki-mapping.json"
        return if (fs.exists(path))
            obj(read(path).decodeToString()).also {
                if (it["version"]?.jsonPrimitive?.intOrNull != 1 || it["notes"] !is JsonObject)
                    throw MobileError("schema", "Anki mapping")
            }
        else document("version" to 1, "notes" to JsonObject(emptyMap()))
    }

    fun remove(id: String) {
        val records = scan()
        val record = records.single { it.text("variant_id") == id }
        val audio = record.text("audio_file")
        val metadata = root / safeFilename(record.text("metadata_path"))
        // Remove an MP3-only record directly; otherwise publish the deletion first.
        fs.delete(metadata, mustExist = false)
        if (records.none { it.text("variant_id") != id && it.text("audio_file") == audio })
            fs.delete(root / safeFilename(audio), mustExist = false)
    }
}

internal fun safeFilename(name: String): String {
    if (name.isEmpty() || name in setOf(".", "..") || name.any { it in "/\\:\u0000" })
        throw MobileError("archive", "Unsafe filename $name")
    return name
}

internal fun recordId(data: JsonObject, accent: String, fallbackWord: String): String {
    val id = data.text("variant_id")
    return when {
        Regex("[0-9a-f]{24}").matches(id) -> id
        id.isNotEmpty() -> stableId("variant", id)
        else ->
            stableId(
                "legacy",
                data.text("word", fallbackWord).lowercase(),
                accent,
                if (data.flag("combined")) "combined" else "recording",
            )
    }
}
