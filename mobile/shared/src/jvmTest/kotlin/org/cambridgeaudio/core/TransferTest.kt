package org.cambridgeaudio.core

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import kotlin.test.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*

class TransferTest {
    private fun entries() =
        parseEntries(
            javaClass.classLoader.getResource("fixtures/test_shared_audio-bank.html")!!.readText(),
            dictionaryUrl("bank"),
        )

    @Test
    fun replacingNativeRecordsKeepsIdsSharedMediaAndStandaloneFiles() {
        for (shared in listOf(false, true)) for (changedAudio in listOf(false, true)) {
            val tmp = Files.createTempDirectory("cda-replace").toFile()
            try {
                val platform = TestPlatform()
                val engine = Engine(File(tmp, "collection").path, File(tmp, "cache").path, platform)
                val entries = entries()
                platform.responses[entries[0].pronunciations[0].url] =
                    "ID3fixture".encodeToByteArray()
                for (entry in entries.take(if (shared) 2 else 1)) {
                    engine.save(json.encodeToString(entry), entry.pronunciations[0].id, false)
                }
                val first = engine.storage.scan().first()
                val id = first.text("variant_id")
                val original = File(engine.collectionPath, first.text("audio_file"))
                val standalone = File(engine.collectionPath, "hello.us.mp3")
                standalone.writeText("ID3independent")
                val expected = engine.storage.scan().map { it.text("variant_id") }.toSet()
                val archive = File(tmp, "backup.cda").path
                CollectionTransfer(engine).exportBundle(archive)
                val incoming =
                    Engine(File(tmp, "incoming").path, File(tmp, "incoming-cache").path, platform)
                val importer = CollectionTransfer(incoming)
                importer.applyImport(importer.previewImport(archive), "{}")
                incoming.editTranslation(id, "incoming edit", false)
                if (changedAudio) {
                    val media = incoming.storage.identity(id).text("audio_file")
                    val bytes = "ID3new audio".encodeToByteArray()
                    File(incoming.collectionPath, media).writeBytes(bytes)
                    incoming.storage
                        .scan()
                        .filter { it.text("audio_file") == media }
                        .forEach {
                            incoming.storage.save(it.with("audio_sha256" to sha256(bytes)))
                        }
                }
                importer.exportBundle(archive)
                val transfer = CollectionTransfer(engine)
                val preview = transfer.previewImport(archive)
                val decisions =
                    JsonObject(
                            obj(preview).array("conflicts").associate {
                                it.jsonPrimitive.content to JsonPrimitive("incoming")
                            }
                        )
                        .toString()
                val backup = transfer.applyImport(preview, decisions)
                val current = engine.storage.scan()
                assertEquals(expected.size, current.size)
                assertEquals(expected, current.map { it.text("variant_id") }.toSet())
                assertEquals(
                    listOf("incoming edit"),
                    cachedTranslation(engine.storage.identity(id))?.texts,
                )
                assertEquals(shared && !changedAudio, original.exists())
                assertEquals("ID3independent", standalone.readText())
                assertEquals("ID3fixture", File(backup, original.name).readText())
                val again = transfer.previewImport(archive)
                assertTrue(obj(again).array("conflicts").isEmpty())
                assertTrue(obj(again).array("added").isEmpty())
                assertEquals("", transfer.applyImport(again, "{}"))
            } finally {
                tmp.deleteRecursively()
            }
        }
    }

    @Test
    fun backupRestoresMissingAndCorruptNativeAndPortableSharedMedia() {
        for (portable in listOf(false, true)) for (missing in listOf(false, true)) {
            val tmp = Files.createTempDirectory("cda-restore").toFile()
            try {
                val platform = TestPlatform()
                val source = Engine(File(tmp, "source").path, File(tmp, "cache").path, platform)
                val entries = entries()
                platform.responses[entries[0].pronunciations[0].url] =
                    "ID3fixture".encodeToByteArray()
                for (entry in entries) source.save(
                    json.encodeToString(entry),
                    entry.pronunciations[0].id,
                    false,
                )
                val archive = File(tmp, "backup.cda").path
                CollectionTransfer(source).exportBundle(archive)
                val target =
                    if (portable)
                        Engine(File(tmp, "target").path, File(tmp, "target-cache").path, platform)
                    else source
                val transfer = CollectionTransfer(target)
                if (portable) transfer.applyImport(transfer.previewImport(archive), "{}")
                val expected = target.storage.scan().map { it.text("variant_id") }.toSet()
                val audio =
                    File(target.collectionPath, target.storage.scan().first().text("audio_file"))
                if (missing) audio.delete() else audio.writeText("damaged")
                val preview = transfer.previewImport(archive)
                assertEquals(
                    expected,
                    obj(preview).array("conflicts").map { it.jsonPrimitive.content }.toSet(),
                )
                fun decisions(choice: String) =
                    JsonObject(expected.associateWith { JsonPrimitive(choice) }).toString()
                val before =
                    File(target.collectionPath)
                        .listFiles()!!
                        .filter { !it.name.startsWith('.') }
                        .associate { it.name to sha256(it.readBytes()) }
                transfer.applyImport(preview, decisions("existing"))
                assertEquals(
                    before,
                    File(target.collectionPath)
                        .listFiles()!!
                        .filter { !it.name.startsWith('.') }
                        .associate { it.name to sha256(it.readBytes()) },
                )
                val backup =
                    transfer.applyImport(transfer.previewImport(archive), decisions("incoming"))
                assertEquals(expected, target.storage.scan().map { it.text("variant_id") }.toSet())
                assertEquals(expected.size, target.storage.scan().size)
                assertTrue(target.storage.scan().all(target.storage::valid))
                if (missing) assertFalse(File(backup, audio.name).exists())
                else assertEquals("damaged", File(backup, audio.name).readText())
                assertTrue(obj(transfer.previewImport(archive)).array("conflicts").isEmpty())
            } finally {
                tmp.deleteRecursively()
            }
        }
    }

    @Test
    fun unrelatedMissingRecordingDoesNotBlockImport() {
        val tmp = Files.createTempDirectory("cda-import-missing").toFile()
        try {
            val platform = TestPlatform()
            val entry = entries()[0]
            platform.responses[entry.pronunciations[0].url] = "ID3fixture".encodeToByteArray()
            val source = Engine(File(tmp, "source").path, File(tmp, "cache").path, platform)
            source.save(json.encodeToString(entry), entry.pronunciations[0].id, false)
            val archive = File(tmp, "backup.cda").path
            CollectionTransfer(source).exportBundle(archive)
            val target = Engine(File(tmp, "target").path, File(tmp, "target-cache").path, platform)
            val local =
                obj(target.save(json.encodeToString(entry), entry.pronunciations[0].id, false))
            File(target.collectionPath, local.text("audio_file")).delete()
            val metadata = File(target.collectionPath, local.text("metadata_path"))
            val before = metadata.readBytes()
            val transfer = CollectionTransfer(target)
            transfer.applyImport(transfer.previewImport(archive), "{}")
            assertEquals(2, target.storage.scan().size)
            assertContentEquals(before, metadata.readBytes())
            assertFalse(target.storage.valid(target.storage.identity(local.text("variant_id"))))
        } finally {
            tmp.deleteRecursively()
        }
    }

    @Test
    fun conflictingUnownedFileAndFailedStagingNeverChangeExistingCollection() {
        val tmp = Files.createTempDirectory("cda-import-failure").toFile()
        try {
            val platform = TestPlatform()
            val entry = entries()[0]
            val bytes = "ID3fixture".encodeToByteArray()
            platform.responses[entry.pronunciations[0].url] = bytes
            val engine = Engine(File(tmp, "collection").path, File(tmp, "cache").path, platform)
            val saved =
                obj(engine.save(json.encodeToString(entry), entry.pronunciations[0].id, false))
            val transfer = CollectionTransfer(engine)
            val archive = File(tmp, "backup.cda").path
            transfer.exportBundle(archive)
            engine.editTranslation(saved.text("variant_id"), "local edit", false)
            val unrelated = File(engine.collectionPath, "audio-${sha256(bytes)}.us.mp3")
            unrelated.writeText("ID3independent content")
            fun snapshot() =
                File(engine.collectionPath).listFiles()!!.associate {
                    it.name to sha256(it.readBytes())
                }
            val before = snapshot()
            val decisions = document(saved.text("variant_id") to "incoming").toString()
            assertEquals(
                "conflict",
                assertFailsWith<MobileError> {
                        transfer.applyImport(transfer.previewImport(archive), decisions)
                    }
                    .code,
            )
            assertEquals(before, snapshot())
            unrelated.delete()
            val beforeFailure = snapshot()
            platform.beforeSync = { path ->
                if (".staging-" in path && path.endsWith(".json"))
                    throw java.io.IOException("disk full")
            }
            assertFailsWith<java.io.IOException> {
                transfer.applyImport(transfer.previewImport(archive), decisions)
            }
            assertEquals(beforeFailure, snapshot())
            assertTrue(engine.storage.valid(engine.storage.identity(saved.text("variant_id"))))
        } finally {
            tmp.deleteRecursively()
        }
    }

    @Test
    fun jvmBundleAndAnkiExports() {
        val tmp = Files.createTempDirectory("cda-transfer").toFile()
        try {
            val platform = TestPlatform()
            val engine = Engine(File(tmp, "collection").path, File(tmp, "cache").path, platform)
            val entry =
                parseEntries(
                    javaClass.classLoader
                        .getResource("fixtures/test_shared_audio-bank.html")!!
                        .readText(),
                    dictionaryUrl("bank"),
                )[0]
            platform.responses[entry.pronunciations[0].url] = "ID3fixture".encodeToByteArray()
            val saved =
                obj(engine.save(json.encodeToString(entry), entry.pronunciations[0].id, false))
            engine.editTranslation(saved.text("variant_id"), "банк", false)
            val file = File(tmp, "transfer.cda").path
            CollectionTransfer(engine).exportBundle(file)
            val target = Engine(File(tmp, "target").path, File(tmp, "target-cache").path, platform)
            val transfer = CollectionTransfer(target)
            val preview = transfer.previewImport(file)
            assertEquals(1, obj(preview).array("added").size)
            transfer.applyImport(preview, "{}")
            assertEquals(1, obj(transfer.previewImport(file)).array("unchanged").size)
            assertEquals(
                saved.text("variant_id"),
                target.storage.scan().single().text("variant_id"),
            )
            assertEquals(listOf("банк"), cachedTranslation(target.storage.scan().single())?.texts)
            target.editTranslation(saved.text("variant_id"), "new personal text", false)
            val conflict = transfer.previewImport(file)
            assertEquals(1, obj(conflict).array("conflicts").size)
            assertFails { transfer.applyImport(conflict, "{}") }
            val backup =
                transfer.applyImport(
                    conflict,
                    document(saved.text("variant_id") to "incoming").toString(),
                )
            assertTrue(File(backup).isDirectory)
            val output = File(tmp, "mobile.apkg")
            AnkiExporter(target).exportApkg(output.path)
            ZipFile(output).use { z ->
                val db = File(tmp, "check.anki2")
                z.getInputStream(z.getEntry("collection.anki2")).use {
                    db.writeBytes(it.readBytes())
                }
                val rows =
                    Json.parseToJsonElement(
                            platform.sqliteQuery(
                                db.path,
                                "SELECT guid,mid,flds FROM notes",
                                emptyList(),
                            )
                        )
                        .jsonArray
                assertEquals(1, rows.size)
                assertEquals(
                    ankiGuid(saved.text("variant_id")),
                    rows[0].jsonArray[0].jsonPrimitive.content,
                )
                assertEquals("1635286301", rows[0].jsonArray[1].jsonPrimitive.content)
                assertEquals(9, rows[0].jsonArray[2].jsonPrimitive.content.split('\u001f').size)
                assertEquals(
                    1,
                    Json.parseToJsonElement(
                            z.getInputStream(z.getEntry("media")).reader().readText()
                        )
                        .jsonObject
                        .size,
                )
            }
            AnkiExporter(target).exportTsv(File(tmp, "tsv.zip").path)
        } finally {
            tmp.deleteRecursively()
        }
    }
}
