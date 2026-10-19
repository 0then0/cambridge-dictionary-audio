package org.cambridgeaudio.core

import kotlinx.serialization.json.*
import okio.Path
import okio.Path.Companion.toPath

/** Collection file transfer. The format is the same as cambridge_audio.bundle. */
class CollectionTransfer(private val engine: Engine) {
    private val store
        get() = engine.storage

    private val fs
        get() = store.fs

    private val root
        get() = store.root

    private val journal
        get() = root.parent!! / ".${root.name}.import.json"

    private val format = "cambridge-dictionary-audio-collection"

    private fun readJson(path: Path) = obj(store.read(path).decodeToString())

    private fun write(path: Path, data: JsonObject) = store.atomicJson(path, data)

    private fun canonical(record: JsonObject): JsonObject {
        val bytes = store.read(root / safeFilename(record.text("audio_file")))
        if (!store.valid(record)) throw MobileError("audio", record.text("word"))
        return JsonObject(record - "metadata_path" - "media_valid")
            .with(
                "audio_file" to "audio-${sha256(bytes)}.${record.text("accent")}.mp3",
                "audio_sha256" to sha256(bytes),
                "separate_metadata" to true,
            )
    }

    @Throws(Exception::class)
    fun recover() {
        if (!fs.exists(journal)) return
        val state = readJson(journal)
        val name = state.text("backup")
        if (!Regex("\\.${Regex.escape(root.name)}\\.backup-[a-f0-9]{32}").matches(name))
            throw MobileError("archive", "Invalid recovery journal")
        val backup = root.parent!! / name
        if (!fs.exists(root) && fs.exists(backup)) fs.atomicMove(backup, root)
        fs.delete(journal)
    }

    @Throws(Exception::class)
    fun exportBundle(destination: String): String {
        recover()
        val staging = engine.cache / ("bundle-" + engine.platform.randomId())
        fs.createDirectories(staging / "collection")
        try {
            val files = linkedMapOf<String, Path>()
            val records = mutableListOf<JsonObject>()
            for (record in store.scan()) {
                store.checkCancelled()
                val data = canonical(record)
                val id = data.text("variant_id")
                val metadata = "collection/$id.${data.text("accent")}.json"
                val audio = "collection/" + data.text("audio_file")
                write(staging / metadata, data)
                store.atomic(staging / audio, store.read(root / record.text("audio_file")))
                records += document("id" to id, "metadata" to metadata)
                files[metadata] = staging / metadata
                files[audio] = staging / audio
            }
            val mapping = store.mapping()
            write(staging / "collection/.anki-mapping.json", mapping)
            files["collection/.anki-mapping.json"] = staging / "collection/.anki-mapping.json"
            store.atomic(staging / "SOURCES.txt", sources().encodeToByteArray())
            files["SOURCES.txt"] = staging / "SOURCES.txt"
            val manifest =
                document(
                    "format" to format,
                    "version" to 1,
                    "storage_version" to 3,
                    "records" to JsonArray(records),
                    "files" to
                        JsonObject(
                            files.mapValues { (_, path) ->
                                val bytes = store.read(path)
                                document("size" to bytes.size, "sha256" to sha256(bytes))
                            }
                        ),
                )
            write(staging / "manifest.json", manifest)
            files["manifest.json"] = staging / "manifest.json"
            val output = engine.cache / ("export-" + engine.platform.randomId() + ".cda")
            engine.platform.archiveWrite(
                output.toString(),
                files.keys.toList(),
                files.values.map(Path::toString),
            )
            store.checkCancelled()
            fs.atomicMove(output, destination.toPath())
            return destination
        } finally {
            fs.deleteRecursively(staging, mustExist = false)
        }
    }

    private fun sources() =
        "Audio, definitions and IPA: Cambridge Dictionary, https://dictionary.cambridge.org/. Cambridge content retains its owners' rights; the application's Apache-2.0 license does not apply to dictionary content.\n${Engine.WIKDICT_ATTRIBUTION}\nWikDict license notices apply only to included WikDict translations. Personal translations are identified as User.\n"

    private data class Loaded(
        val manifest: JsonObject,
        val records: Map<String, JsonObject>,
        val mapping: JsonObject,
    )

    private fun load(source: String): Loaded {
        val list = json.parseToJsonElement(engine.platform.archiveList(source)).jsonArray
        if (list.size > 100000) throw MobileError("archive", "Too many files")
        val names = mutableSetOf<String>()
        var total = 0L
        for (raw in list) {
            val m = raw.jsonObject
            val name = m.text("name")
            if (
                name.startsWith('/') ||
                    name.split('/').any { it.isEmpty() || it == "." || it == ".." } ||
                    name.any { it in "\\:\u0000" }
            )
                throw MobileError("archive", "Unsafe ZIP path")
            if (
                !names.add(name.lowercase()) ||
                    m.flag("symlink") ||
                    m.flag("directory") ||
                    m.flag("encrypted")
            )
                throw MobileError("archive", "Duplicate/link/encrypted ZIP member")
            val size = m["size"]?.jsonPrimitive?.longOrNull ?: -1
            if (
                size < 0 ||
                    size > if (name == "manifest.json") 8L * 1024 * 1024 else 64L * 1024 * 1024
            )
                throw MobileError("archive", "Oversized ZIP member")
            total += size
        }
        if (total > 2L * 1024 * 1024 * 1024) throw MobileError("archive", "Bundle exceeds 2 GiB")
        val manifest =
            obj(
                engine.platform
                    .archiveRead(source, "manifest.json", 8L * 1024 * 1024)
                    .decodeToString()
            )
        if (
            manifest.text("format") != format ||
                manifest["version"]?.jsonPrimitive?.intOrNull != 1 ||
                manifest["storage_version"]?.jsonPrimitive?.intOrNull != 3
        )
            throw MobileError("schema", "Unsupported collection bundle")
        val files =
            manifest["files"]?.jsonObject ?: throw MobileError("archive", "No checksum manifest")
        if (names != (files.keys + "manifest.json").map { it.lowercase() }.toSet())
            throw MobileError("archive", "Manifest does not match ZIP")
        val records = linkedMapOf<String, JsonObject>()
        val referenced = mutableSetOf<String>()
        for ((name, raw) in files) {
            store.checkCancelled()
            val expected = raw.jsonObject
            val bytes = engine.platform.archiveRead(source, name, 64L * 1024 * 1024)
            if (
                bytes.size.toLong() != expected["size"]?.jsonPrimitive?.longOrNull ||
                    sha256(bytes) != expected.text("sha256")
            )
                throw MobileError("archive", "Checksum / size mismatch: $name")
        }
        for (raw in manifest.array("records")) {
            val item = raw.jsonObject
            val id = item.text("id")
            val name = item.text("metadata")
            if (!Regex("[a-f0-9]{24}").matches(id) || id in records || name !in files)
                throw MobileError("archive", "Invalid/duplicate record ID")
            val data =
                obj(engine.platform.archiveRead(source, name, 64L * 1024 * 1024).decodeToString())
            val accent = data.text("accent")
            val audio = safeFilename(data.text("audio_file"))
            if (
                accent !in setOf("us", "uk") ||
                    data["version"]?.jsonPrimitive?.intOrNull != 3 ||
                    data.text("variant_id") != id ||
                    name != "collection/$id.$accent.json" ||
                    !audio.endsWith(".$accent.mp3")
            )
                throw MobileError("archive", "Invalid record identity/reference")
            val bytes = engine.platform.archiveRead(source, "collection/$audio", 64L * 1024 * 1024)
            if (!isMp3(bytes) || sha256(bytes) != data.text("audio_sha256"))
                throw MobileError("audio", "Invalid referenced media")
            if (
                listOf("word", "ipa", "definition").any {
                    data[it] !is JsonPrimitive || data[it]?.jsonPrimitive?.isString != true
                }
            )
                throw MobileError("archive", "Missing record fields")
            referenced += name
            referenced += "collection/$audio"
            records[id] = data
        }
        if (
            (files.keys - referenced - setOf("SOURCES.txt", "collection/.anki-mapping.json"))
                .isNotEmpty()
        )
            throw MobileError("archive", "Unreferenced bundle data")
        val mapping =
            if ("collection/.anki-mapping.json" in files)
                obj(
                    engine.platform
                        .archiveRead(source, "collection/.anki-mapping.json", 64L * 1024 * 1024)
                        .decodeToString()
                )
            else document("version" to 1, "notes" to JsonObject(emptyMap()))
        if (mapping["version"]?.jsonPrimitive?.intOrNull != 1 || mapping["notes"] !is JsonObject)
            throw MobileError("schema", "Anki mapping")
        return Loaded(manifest, records, mapping)
    }

    private fun revision(): String =
        sha256(
            JsonObject(
                    fs.list(root)
                        .filter { it.name.endsWith(".json") || it.name.endsWith(".mp3") }
                        .associate { it.name to JsonPrimitive(sha256(store.read(it))) }
                )
                .toString()
                .encodeToByteArray()
        )

    private fun comparable(data: JsonObject) =
        JsonObject(data - "audio_file" - "separate_metadata" - "metadata_path" - "media_valid")

    @Throws(Exception::class)
    fun previewImport(source: String): String {
        recover()
        val incoming = load(source)
        val local = store.scan().associateBy { it.text("variant_id") }
        val mapping = store.mapping()["notes"]!!.jsonObject
        val added = mutableListOf<String>()
        val same = mutableListOf<String>()
        val conflicts = mutableListOf<String>()
        for ((id, record) in incoming.records) {
            val mapped = incoming.mapping["notes"]!!.jsonObject[id]
            when {
                id !in local -> added += id
                store.valid(local[id]!!) &&
                    comparable(record) == comparable(canonical(local[id]!!)) &&
                    (mapped == null || mapping[id] == null || mapped == mapping[id]) -> same += id
                else -> conflicts += id
            }
        }
        for ((id, mapped) in incoming.mapping["notes"]!!.jsonObject) {
            if (id !in incoming.records && id in mapping && mapped != mapping[id]) conflicts += id
        }
        return document(
                "source" to source,
                "bundle_sha256" to store.fileHash(source.toPath()),
                "revision" to revision(),
                "added" to added.strings(),
                "unchanged" to same.strings(),
                "conflicts" to conflicts.strings(),
                "entries" to JsonObject(incoming.records),
            )
            .toString()
    }

    @Throws(Exception::class)
    fun applyImport(previewJson: String, decisionsJson: String): String {
        val preview = obj(previewJson)
        val decisions = obj(decisionsJson)
        val conflicts = preview.array("conflicts").map { it.jsonPrimitive.content }
        if (conflicts.any { decisions.text(it) !in setOf("existing", "incoming") })
            throw MobileError("conflict", "Resolve every conflict")
        val source = preview.text("source")
        if (
            store.fileHash(source.toPath()) != preview.text("bundle_sha256") ||
                revision() != preview.text("revision")
        )
            throw MobileError("stale", "Preview the changed collection again")
        val incoming = load(source)
        val selected =
            preview.array("added").map { it.jsonPrimitive.content }.toSet() +
                conflicts.filter { decisions.text(it) == "incoming" }
        val currentMapping = store.mapping()
        val notes = currentMapping["notes"]!!.jsonObject.toMutableMap()
        for ((id, value) in incoming.mapping["notes"]!!.jsonObject) if (
            id !in conflicts || decisions.text(id) == "incoming"
        )
            notes[id] = value
        val mergedMapping =
            JsonObject(incoming.mapping + currentMapping)
                .with(
                    "notes" to JsonObject(notes),
                    "last_export" to
                        maxOf(
                            incoming.mapping["last_export"]?.jsonPrimitive?.longOrNull ?: 0,
                            currentMapping["last_export"]?.jsonPrimitive?.longOrNull ?: 0,
                        ),
                )
        if (selected.isEmpty() && mergedMapping == currentMapping) return ""
        val staging = root.parent!! / ".${root.name}.staging-${engine.platform.randomId()}"
        val backup =
            root.parent!! / ".${root.name}.backup-${engine.platform.randomId().replace("-", "")}"
        fs.createDirectories(staging)
        try {
            for (path in fs.list(root)) {
                if (fs.metadata(path).symlinkTarget != null || !fs.metadata(path).isRegularFile)
                    throw MobileError("storage", "Unsupported local link/directory")
                fs.copy(path, staging / path.name)
            }
            val local = store.scan().associateBy { it.text("variant_id") }
            val replacing = selected.intersect(incoming.records.keys)
            for (id in selected) {
                val data = incoming.records[id] ?: continue
                val audio = data.text("audio_file")
                val destination = staging / safeFilename(audio)
                val bytes =
                    engine.platform.archiveRead(source, "collection/$audio", 64L * 1024 * 1024)
                if (fs.exists(destination) && sha256(store.read(destination)) != sha256(bytes)) {
                    val owners = local.values.filter { it.text("audio_file") == audio }
                    // Repair shared media only when all owners expect the incoming bytes.
                    if (owners.isEmpty() || owners.any { it.text("audio_sha256") != sha256(bytes) })
                        throw MobileError("conflict", "Existing media filename")
                }
                store.atomic(destination, bytes)
                val metadata = local[id]?.text("metadata_path") ?: "$id.${data.text("accent")}.json"
                if (id !in local && fs.exists(staging / metadata))
                    throw MobileError("conflict", "Existing metadata filename")
                write(staging / safeFilename(metadata), data)
            }
            val referenced =
                local.filterKeys { it !in replacing }.values.map { it.text("audio_file") }.toSet() +
                    replacing.map { incoming.records[it]!!.text("audio_file") }
            for (id in replacing.intersect(local.keys)) {
                val audio = local[id]!!.text("audio_file")
                if (audio !in referenced)
                    fs.delete(staging / safeFilename(audio), mustExist = false)
            }
            write(staging / ".anki-mapping.json", mergedMapping)
            store.checkCancelled()
            for (file in fs.list(staging)) engine.platform.syncFile(file.toString())
            write(journal, document("version" to 1, "backup" to backup.name))
            fs.atomicMove(root, backup)
            try {
                fs.atomicMove(staging, root)
            } catch (e: Exception) {
                fs.atomicMove(backup, root)
                throw e
            }
            fs.delete(journal)
            return backup.toString()
        } finally {
            fs.deleteRecursively(staging, mustExist = false)
        }
    }
}
