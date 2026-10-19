package org.cambridgeaudio.core

import kotlinx.serialization.json.*
import okio.Path
import okio.Path.Companion.toPath

/** Legacy v11 APKG writer. SQLite and ZIP are platform APIs; identities are shared. */
class AnkiExporter(private val engine: Engine) {
    private val storage
        get() = engine.storage

    private val fs
        get() = storage.fs

    private val columns =
        listOf(
            "ID",
            "Word",
            "PartOfSpeech",
            "Definition",
            "Translation",
            "IPA",
            "Accent",
            "Audio",
            "Source",
        )

    private fun selected(idsJson: String): List<JsonObject> {
        val ids =
            json.parseToJsonElement(idsJson).jsonArray.map { it.jsonPrimitive.content }.toSet()
        val all = storage.scan()
        val records = if (ids.isEmpty()) all else all.filter { it.text("variant_id") in ids }
        if (records.isEmpty() || ids.isNotEmpty() && records.size != ids.size)
            throw MobileError("missing", "No selected records")
        for (record in records) {
            if (!storage.valid(record))
                throw MobileError("audio", "Missing/corrupt MP3: ${record.text("word")}")
            val translation = cachedTranslation(record)
            if (
                translation != null &&
                    translation.options.isNotEmpty() &&
                    translation.texts.isEmpty()
            )
                throw MobileError("translation_choice", record.text("word"))
        }
        return records
    }

    private fun source(record: JsonObject): String {
        val translation = cachedTranslation(record)
        var source = record.text("source_url").ifEmpty { "https://dictionary.cambridge.org/" }
        source += "; audio: " + record.text("audio_url") + "; " + ankiContract.text("sources")
        if (translation != null)
            source +=
                "\nTranslation: ${translation.source} (russian); ${translation.version}; " +
                    translation.options
                        .filter {
                            translation.selected_id.isEmpty() || it.id == translation.selected_id
                        }
                        .joinToString("; ") { it.origin }
        return source
    }

    private fun fields(record: JsonObject, media: String, disclosure: Boolean): List<String> {
        val values =
            listOf(
                record.text("variant_id"),
                record.text("word"),
                record.text("part_of_speech"),
                record.text("definition"),
                cachedTranslation(record)?.texts?.joinToString("; ").orEmpty(),
                record.text("ipa"),
                record.text("accent").uppercase(),
                "[sound:$media]",
                source(record),
            )
        return values.mapIndexed { index, value ->
            if (index == 8 && disclosure) sourceDisclosure(value) else htmlField(value)
        }
    }

    @Throws(Exception::class)
    fun exportApkg(destination: String, idsJson: String = "[]"): String {
        val records = selected(idsJson)
        val mapping = storage.mapping()
        val timestamp =
            maxOf(
                engine.platform.nowSeconds(),
                (mapping["last_export"]?.jsonPrimitive?.longOrNull ?: 0) + 1,
            )
        val staging = engine.cache / ("anki-" + engine.platform.randomId())
        fs.createDirectories(staging)
        val destinationPath = destination.toPath()
        val output = staging / "output.apkg"
        try {
            val names = mutableListOf<String>()
            val paths = mutableListOf<String>()
            val media = linkedMapOf<String, String>()
            val models = linkedMapOf<String, JsonElement>()
            val statements = schema().toMutableList()
            val rows = mutableListOf<String>()
            val sources = mutableListOf<String>()
            val notes = mapping["notes"]!!.jsonObject
            var nextId = timestamp * 1000
            for (record in records) {
                storage.checkCancelled()
                val bytes = storage.read(storage.root / record.text("audio_file"))
                val filename = "cambridge-audio-${sha256(bytes)}.mp3"
                if (filename !in media.values) {
                    val number = media.size.toString()
                    media[number] = filename
                    storage.atomic(staging / number, bytes)
                    names += number
                    paths += (staging / number).toString()
                }
                val identity = record.text("variant_id")
                val adopted = notes[identity]?.jsonObject
                val model = adopted?.get("model")?.jsonObject ?: ankiContract["model"]!!.jsonObject
                if (
                    model.array("flds").map { it.jsonObject.text("name") } != columns ||
                        model.array("tmpls").size != 1 ||
                        model["type"]?.jsonPrimitive?.intOrNull != 0
                )
                    throw MobileError("schema", "Unsupported adopted note schema")
                val mid = model["id"]!!.jsonPrimitive.long
                models[mid.toString()] = model
                val guid = adopted?.text("guid") ?: ankiGuid(identity)
                val values = fields(record, filename, true)
                val nid = nextId++
                val cid = nextId++
                rows +=
                    "INSERT INTO notes VALUES($nid,${sql(guid)},$mid,$timestamp,-1,' ',${sql(values.joinToString("\u001f"))},${sql(values[1])},0,0,'')"
                rows +=
                    "INSERT INTO cards VALUES($cid,$nid,1635286302,0,$timestamp,-1,0,0,0,0,0,0,0,0,0,0,0,'')"
                sources += source(record)
            }
            val initial = ankiContract["initial_col"]!!.jsonObject
            val decks = obj(initial.text("decks")).toMutableMap()
            val deck =
                (decks["1635286302"] ?: decks["1"])!!
                    .jsonObject
                    .with(
                        "id" to 1635286302,
                        "name" to "Cambridge Dictionary Audio",
                        "desc" to
                            ("<div style=\"text-align:center;\">" +
                                sourceDisclosure(ankiContract.text("sources")) +
                                "</div>"),
                    )
            decks["1635286302"] = deck
            val col =
                initial.with(
                    "models" to JsonObject(models).toString(),
                    "decks" to JsonObject(decks).toString(),
                )
            val colNames =
                listOf(
                    "id",
                    "crt",
                    "mod",
                    "scm",
                    "ver",
                    "dty",
                    "usn",
                    "ls",
                    "conf",
                    "models",
                    "decks",
                    "dconf",
                    "tags",
                )
            statements +=
                "INSERT INTO col VALUES(" +
                    colNames.joinToString(",") { key ->
                        val value = col[key]!!
                        if (value is JsonNull) "NULL"
                        else if (value.jsonPrimitive.isString) sql(value.jsonPrimitive.content)
                        else value.toString()
                    } +
                    ")"
            statements += rows
            val database = staging / "collection.anki2"
            engine.platform.sqliteCreate(database.toString(), statements)
            storage.atomic(
                staging / "media",
                JsonObject(media.mapValues { JsonPrimitive(it.value) })
                    .toString()
                    .encodeToByteArray(),
            )
            storage.atomic(
                staging / "SOURCES.txt",
                (ankiContract.text("sources") + "\n" + sources.joinToString("\n"))
                    .encodeToByteArray(),
            )
            storage.atomicJson(
                staging / "cambridge-export.json",
                document("application" to "cambridge-dictionary-audio", "version" to 1),
            )
            for (name in
                listOf("collection.anki2", "media", "SOURCES.txt", "cambridge-export.json")) {
                names += name
                paths += (staging / name).toString()
            }
            engine.platform.archiveWrite(output.toString(), names, paths)
            storage.checkCancelled()
            storage.atomicJson(
                storage.root / ".anki-mapping.json",
                mapping.with("last_export" to timestamp),
            )
            fs.atomicMove(output, destinationPath)
            return destination
        } finally {
            fs.deleteRecursively(staging, mustExist = false)
        }
    }

    /** TSV + flat media are shared as one ZIP, with the original nine-field contract. */
    @Throws(Exception::class)
    fun exportTsv(destination: String, idsJson: String = "[]"): String {
        val records = selected(idsJson)
        val staging = engine.cache / ("tsv-" + engine.platform.randomId())
        fs.createDirectories(staging / "media")
        try {
            val files = linkedMapOf<String, Path>()
            val lines =
                mutableListOf(
                    "#separator:Tab",
                    "#html:true",
                    "#columns:" + columns.joinToString("\t"),
                )
            for (record in records) {
                storage.checkCancelled()
                val filename = "cambridge-${record.text("variant_id")}.mp3"
                val media = staging / "media" / filename
                storage.atomic(media, storage.read(storage.root / record.text("audio_file")))
                files["media/$filename"] = media
                lines +=
                    fields(record, filename, false).joinToString("\t") { value ->
                        if (value.any { it == '\t' || it == '"' })
                            "\"${value.replace("\"", "\"\"")}\""
                        else value
                    }
            }
            storage.atomic(
                staging / "collection.tsv",
                (lines.joinToString("\n") + "\n").encodeToByteArray(),
            )
            storage.atomic(
                staging / "SOURCES.txt",
                (ankiContract.text("sources") + records.joinToString("\n", transform = ::source))
                    .encodeToByteArray(),
            )
            storage.atomic(
                staging / "IMPORT.txt",
                ("Anki TSV import (UTF-8)\nCreate these fields in this order: ${columns.joinToString(", ")}.\nCopy media/*.mp3 into collection.media. Import collection.tsv with Tab, HTML enabled.\nMatch by note type and first field (ID), never internal GUID. To migrate old TSV notes to APKG, adopt original GUIDs explicitly using desktop --anki-reference.\nhttps://docs.ankiweb.net/manual/importing/text-files\n")
                    .encodeToByteArray(),
            )
            for (name in listOf("collection.tsv", "SOURCES.txt", "IMPORT.txt")) files[name] =
                staging / name
            val output = staging / "export.zip"
            engine.platform.archiveWrite(
                output.toString(),
                files.keys.toList(),
                files.values.map(Path::toString),
            )
            storage.checkCancelled()
            fs.atomicMove(output, destination.toPath())
            return destination
        } finally {
            fs.deleteRecursively(staging, mustExist = false)
        }
    }

    private fun schema() =
        listOf(
            "CREATE TABLE col(id integer primary key,crt integer not null,mod integer not null,scm integer not null,ver integer not null,dty integer not null,usn integer not null,ls integer not null,conf text not null,models text not null,decks text not null,dconf text not null,tags text not null)",
            "CREATE TABLE notes(id integer primary key,guid text not null,mid integer not null,mod integer not null,usn integer not null,tags text not null,flds text not null,sfld integer not null,csum integer not null,flags integer not null,data text not null)",
            "CREATE TABLE cards(id integer primary key,nid integer not null,did integer not null,ord integer not null,mod integer not null,usn integer not null,type integer not null,queue integer not null,due integer not null,ivl integer not null,factor integer not null,reps integer not null,lapses integer not null,left integer not null,odue integer not null,odid integer not null,flags integer not null,data text not null)",
            "CREATE TABLE revlog(id integer primary key,cid integer not null,usn integer not null,ease integer not null,ivl integer not null,lastIvl integer not null,factor integer not null,time integer not null,type integer not null)",
            "CREATE TABLE graves(usn integer not null,oid integer not null,type integer not null)",
            "CREATE INDEX ix_notes_usn on notes(usn)",
            "CREATE INDEX ix_cards_usn on cards(usn)",
            "CREATE INDEX ix_revlog_usn on revlog(usn)",
            "CREATE INDEX ix_cards_nid on cards(nid)",
            "CREATE INDEX ix_cards_sched on cards(did,queue,due)",
            "CREATE INDEX ix_revlog_cid on revlog(cid)",
            "CREATE INDEX ix_notes_csum on notes(csum)",
        )
}

internal fun sql(text: String) = "'" + text.replace("'", "''") + "'"

internal fun htmlField(value: String) =
    value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&#x27;")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")

internal fun sourceDisclosure(value: String) =
    "<details class=\"cambridge-source\" style=\"display:inline-block; max-width:100%; font-size:13px; line-height:1.45; text-align:left; overflow-wrap:anywhere;\"><summary style=\"cursor:pointer;\">Source</summary><div>${htmlField(value)}</div></details>"
