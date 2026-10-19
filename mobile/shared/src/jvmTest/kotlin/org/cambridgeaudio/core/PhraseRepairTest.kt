package org.cambridgeaudio.core

import java.io.File
import java.nio.file.Files
import kotlin.test.*

class PhraseRepairTest {
    @Test
    fun legacyPlanCanBeRebuiltButMalformedSavedSelectionsNeverFallBackSilently() {
        val tmp = Files.createTempDirectory("cda-legacy-phrase").toFile()
        try {
            val fake = TestPlatform()
            val platform =
                object : Platform by fake {
                    override fun synthesize(segments: List<String>, destination: String) {
                        File(destination).writeText("ID3rebuilt")
                    }
                }
            fake.responses[dictionaryUrl("bank")] =
                javaClass.classLoader
                    .getResource("fixtures/test_shared_audio-bank.html")!!
                    .readBytes()
            fake.responses["https://dictionary.cambridge.org/media/bank.mp3"] =
                "ID3segment".encodeToByteArray()
            val engine = Engine(File(tmp, "collection").path, File(tmp, "cache").path, platform)
            val id = "a".repeat(24)
            val metadata =
                document(
                    "version" to 3,
                    "word" to "bank bank",
                    "accent" to "us",
                    "combined" to true,
                    "variant_id" to id,
                    "audio_file" to "legacy.us.mp3",
                    "metadata_path" to "$id.us.json",
                    "ipa" to "",
                    "definition" to "",
                )
            engine.storage.commitFiles(
                mapOf(
                    "legacy.us.mp3" to "ID3old".encodeToByteArray(),
                    "$id.us.json" to engine.storage.metadataBytes(metadata),
                )
            )
            val repaired = obj(engine.repair(id))
            assertEquals(id, repaired.text("variant_id"))
            assertTrue(engine.storage.valid(repaired))
            assertEquals(2, repaired.array("phrase_selections").size)
            engine.storage.save(repaired.with("phrase_selections" to "broken"))
            val before =
                File(engine.collectionPath).listFiles()!!.associate {
                    it.name to sha256(it.readBytes())
                }
            fake.requests.clear()
            assertEquals("input", assertFailsWith<MobileError> { engine.repair(id) }.code)
            assertTrue(fake.requests.isEmpty())
            assertEquals(
                before,
                File(engine.collectionPath).listFiles()!!.associate {
                    it.name to sha256(it.readBytes())
                },
            )
        } finally {
            tmp.deleteRecursively()
        }
    }

    @Test
    fun repairUsesSavedPronunciationsWithoutRepeatingDictionaryLookup() {
        val tmp = Files.createTempDirectory("cda-phrase-repair").toFile()
        try {
            val fake = TestPlatform()
            var encoded = emptyList<String>()
            val platform =
                object : Platform by fake {
                    override fun synthesize(segments: List<String>, destination: String) {
                        encoded = segments.map { File(it).readText() }
                        File(destination).writeText("ID3combined")
                    }
                }
            val html =
                javaClass.classLoader
                    .getResource("fixtures/test_shared_audio-bank.html")!!
                    .readText()
                    .replace(
                        "</audio>",
                        "</audio><audio><source src=\"/media/second.mp3\"></audio>",
                    )
            fake.responses[dictionaryUrl("bank")] = html.encodeToByteArray()
            val firstUrl = "https://dictionary.cambridge.org/media/bank.mp3"
            val secondUrl = "https://dictionary.cambridge.org/media/second.mp3"
            fake.responses[firstUrl] = "ID3first".encodeToByteArray()
            fake.responses[secondUrl] = "ID3second".encodeToByteArray()
            val engine = Engine(File(tmp, "collection").path, File(tmp, "cache").path, platform)
            val plan = engine.planPhrase("bank bank", "us")
            val choices =
                listOf(
                    stableId("cambridge-audio", "us", secondUrl),
                    stableId("cambridge-audio", "us", firstUrl),
                )
            val saved = obj(engine.synthesizeChosen(plan, choices.strings().toString()))
            val id = saved.text("variant_id")
            engine.editTranslation(id, "personal phrase", false)
            File(engine.audioPath(id)).delete()
            // The source HTML can change or become unavailable after the original selection.
            fake.responses.remove(dictionaryUrl("bank"))
            fake.requests.clear()
            val restarted = Engine(engine.collectionPath, engine.cachePath, platform)
            val repaired = obj(restarted.repair(id))
            assertEquals(listOf(secondUrl, firstUrl), fake.requests)
            assertEquals(listOf("ID3second", "ID3first"), encoded)
            assertEquals(id, repaired.text("variant_id"))
            assertEquals(saved["phrase_plan"], repaired["phrase_plan"])
            assertEquals(saved["phrase_selections"], repaired["phrase_selections"])
            assertEquals(listOf("personal phrase"), cachedTranslation(repaired)?.texts)
            assertTrue(restarted.storage.valid(repaired))
            val before =
                File(engine.collectionPath).listFiles()!!.associate {
                    it.name to sha256(it.readBytes())
                }
            fake.responses.remove(secondUrl)
            assertEquals("absent", assertFailsWith<MobileError> { restarted.repair(id) }.code)
            assertEquals(
                before,
                File(engine.collectionPath).listFiles()!!.associate {
                    it.name to sha256(it.readBytes())
                },
            )
            fake.aborted = true
            assertEquals("cancelled", assertFailsWith<MobileError> { restarted.repair(id) }.code)
            assertEquals(
                before,
                File(engine.collectionPath).listFiles()!!.associate {
                    it.name to sha256(it.readBytes())
                },
            )
        } finally {
            tmp.deleteRecursively()
        }
    }
}
