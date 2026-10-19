package org.cambridgeaudio.core

import java.io.File
import java.nio.file.Files
import kotlin.test.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*

class ContractTest {
    private fun resource(name: String) =
        checkNotNull(javaClass.classLoader.getResource(name)).readText()

    private val golden
        get() = obj(resource("golden.json"))

    @Test
    fun normalizationIdentitiesAndFilenames() {
        for (raw in golden.array("normalization")) {
            val case = raw.jsonObject
            if (case.flag("invalid")) assertFails { normalizeWord(case.text("input")) }
            else {
                val word = normalizeWord(case.text("input"))
                assertEquals(case.text("normalized"), word)
                assertEquals(case.text("filename"), audioFilename(word, "us"))
            }
        }
        for (raw in golden.array("identities")) {
            val case = raw.jsonObject
            assertEquals(
                case.text("id"),
                stableId(*case.array("values").map { it.jsonPrimitive.content }.toTypedArray()),
            )
        }
        for (raw in golden.array("guids")) {
            val case = raw.jsonObject
            assertEquals(case.text("guid"), ankiGuid(case.text("id")))
        }
    }

    @Test
    fun originalPythonHtmlFixtures() {
        for (raw in golden.array("parsers")) {
            val case = raw.jsonObject
            val actual =
                json.encodeToJsonElement(
                    parseEntries(resource(case.text("file")), case.text("url"))
                )
            assertEquals(case["entries"], actual, case.text("file"))
        }
    }

    @Test
    fun conservativeTranslationMatching() {
        for (raw in golden.array("matching")) {
            val case = raw.jsonObject
            val options = json.decodeFromJsonElement<List<TranslationOption>>(case["options"]!!)
            assertEquals(
                case["expected"],
                json.encodeToJsonElement(
                    matchOptions(options, case.text("definition"), case.text("part"))
                ),
            )
        }
    }

    @Test
    fun sharedMediaOfflineRestartEditDeleteAndMissingMedia() {
        val tmp = Files.createTempDirectory("cda-core").toFile()
        try {
            val platform = TestPlatform()
            val html = resource("fixtures/test_shared_audio-bank.html")
            platform.responses[dictionaryUrl("bank")] = html.encodeToByteArray()
            val url = "https://dictionary.cambridge.org/media/bank.mp3"
            platform.responses[url] = "ID3fixture".encodeToByteArray()
            val root = File(tmp, "collection").path
            val cache = File(tmp, "cache").path
            var engine = Engine(root, cache, platform)
            val entries = json.decodeFromString<List<Entry>>(engine.lookup("bank"))
            val first =
                obj(
                    engine.save(
                        json.encodeToString(entries[0]),
                        entries[0].pronunciations[0].id,
                        false,
                    )
                )
            engine.editTranslation(first.text("variant_id"), "my bank", false)
            val second =
                obj(
                    engine.save(
                        json.encodeToString(entries[1]),
                        entries[1].pronunciations[0].id,
                        false,
                    )
                )
            assertEquals(first.text("audio_file"), second.text("audio_file"))
            assertEquals(1, platform.requests.count { it == url })
            engine = Engine(root, cache, platform)
            assertEquals(2, json.parseToJsonElement(engine.records()).jsonArray.size)
            assertEquals(
                listOf("my bank"),
                cachedTranslation(engine.storage.identity(first.text("variant_id")))?.texts,
            )
            engine.deleteRecord(first.text("variant_id"))
            assertTrue(File(root, second.text("audio_file")).exists())
            File(root, second.text("audio_file")).writeText("corrupt")
            assertFalse(engine.storage.valid(second))
            engine.repair(second.text("variant_id"))
            assertTrue(engine.storage.valid(engine.storage.identity(second.text("variant_id"))))
            engine.deleteRecord(second.text("variant_id"))
            assertFalse(File(root, second.text("audio_file")).exists())
        } finally {
            tmp.deleteRecursively()
        }
    }

    @Test
    fun cancellationAndLateTranslationNeverOverwritePersonalEdit() {
        val tmp = Files.createTempDirectory("cda-late").toFile()
        try {
            val platform = TestPlatform()
            val engine = Engine(File(tmp, "collection").path, File(tmp, "cache").path, platform)
            val entry =
                parseEntries(
                    resource("fixtures/test_shared_audio-bank.html"),
                    dictionaryUrl("bank"),
                )[0]
            platform.responses[entry.pronunciations[0].url] = "ID3fixture".encodeToByteArray()
            val saved =
                obj(engine.save(json.encodeToString(entry), entry.pronunciations[0].id, false))
            val id = saved.text("variant_id")
            engine.editTranslation(id, "latest", false)
            val late =
                TranslationResult(
                    "russian",
                    saved.text("sense_id"),
                    "Cambridge",
                    listOf(TranslationOption("source", listOf("stale"), matched = true)),
                )
            engine.persistTranslation(id, json.encodeToString(late))
            assertEquals(listOf("latest"), cachedTranslation(engine.storage.identity(id))?.texts)
            platform.aborted = true
            assertFails {
                engine.save(json.encodeToString(entry), entry.pronunciations[0].id, true)
            }
            assertTrue(engine.storage.valid(engine.storage.identity(id)))
            assertEquals(listOf("latest"), cachedTranslation(engine.storage.identity(id))?.texts)
        } finally {
            tmp.deleteRecursively()
        }
    }
}
