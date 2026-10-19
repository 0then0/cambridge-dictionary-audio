package org.cambridgeaudio.app

import android.media.MediaExtractor
import android.media.MediaFormat
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.zip.ZipFile
import kotlinx.serialization.json.*
import org.cambridgeaudio.core.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class ApplicationTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun wikdictPromptReflectsLocalVerificationAndCancelPreservesPackage() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val dictionary = File(context.filesDir, "en-ru-${Engine.WIKDICT_VERSION}.sqlite3")
        val before = Triple(dictionary.exists(), dictionary.length(), dictionary.lastModified())
        lateinit var model: AppModel
        compose.activityRule.scenario.onActivity { activity ->
            model = ViewModelProvider(activity)[AppModel::class.java]
            model.preference("language", "en")
        }
        compose.onNodeWithTag("tab2").performClick()
        compose.waitUntil(20000) {
            !model.checkingDictionary && !model.busy && model.dictionaryStatus != "checking"
        }
        val status = model.dictionaryStatus
        assertTrue(status in listOf("ready", "missing", "corrupt"))
        compose
            .onNodeWithText(
                if (status == "missing") "Install WikDict en → ru" else "Download WikDict again"
            )
            .performScrollTo()
            .performClick()
        compose.waitUntil(20000) { model.wikdictPrompt != null }
        assertEquals(status, model.wikdictPrompt)
        val message =
            when (status) {
                "ready" -> "WikDict is already installed and verified. Download it again?"
                "corrupt" -> "The installed WikDict is damaged. Download it again?"
                else -> "Install the English–Russian WikDict package?"
            }
        compose.onNodeWithText(message, substring = true).assertExists()
        compose.onNodeWithText("Cancel").performClick()
        assertNull(model.wikdictPrompt)
        assertEquals(
            before,
            Triple(dictionary.exists(), dictionary.length(), dictionary.lastModified()),
        )
    }

    @Test
    fun navigationAndSettingsSurviveActivityRecreation() {
        compose.onNodeWithText("Settings", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Language").assertExists()
        compose.onNodeWithText("Русский").performClick()
        compose.onNodeWithText("Настройки", useUnmergedTree = true).assertExists()
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("Коллекция", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Поиск в коллекции").assertExists()
        compose.onNodeWithText("Настройки", useUnmergedTree = true).performClick()
        compose.onNodeWithText("English").performClick()
    }

    @Test
    fun localPlaybackNeverEntersGlobalBusyState() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        val collection = File(context.filesDir, "collection").apply { mkdirs() }
        val id = "aa0000000000000000000002"
        val audio = File(collection, "playback-regression.us.mp3")
        val metadata = File(collection, "$id.us.json")
        val record =
            parseObject(
                """{"version":3,"word":"playback-regression","accent":"us","variant_id":"$id","audio_file":"${audio.name}","separate_metadata":true}"""
            )
        audio.writeBytes(assets.open("segment-a.mp3").use { it.readBytes() })
        metadata.writeText(record.toString())
        lateinit var model: AppModel
        try {
            compose.activityRule.scenario.onActivity { activity ->
                model = ViewModelProvider(activity)[AppModel::class.java]
                model.selectSaved(record)
                model.play()
                assertFalse("Listening must not insert the global operation toolbar", model.busy)
            }
            compose.onNodeWithText("Cancel operation").assertDoesNotExist()
        } finally {
            compose.activityRule.scenario.onActivity {
                model.cancel()
                model.stopPlayback()
            }
            audio.delete()
            metadata.delete()
        }
    }

    @Test
    fun collectionDetailsStayInCollectionAndRestoreSearchDraftAfterRotation() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val collection = File(context.filesDir, "collection").apply { mkdirs() }
        val id = "aa0000000000000000000003"
        val audio = File(collection, "collection-navigation.us.mp3")
        val metadata = File(collection, "$id.us.json")
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        audio.writeBytes(assets.open("segment-a.mp3").use { it.readBytes() })
        metadata.writeText(
            """{"version":3,"word":"collection-navigation","accent":"us","definition":"A saved meaning","variant_id":"$id","audio_file":"${audio.name}","separate_metadata":true}"""
        )
        lateinit var model: AppModel
        try {
            compose.activityRule.scenario.onActivity { activity ->
                model = ViewModelProvider(activity)[AppModel::class.java]
                model.preference("language", "en")
                model.setTranslations(false)
                model.selectEntry(
                    parseObject(
                        """{"word":"search-draft","sense_id":"draft-sense","definition":"Unsaved selected meaning","pronunciations":[]}"""
                    )
                )
                model.personalTranslation("Keep my draft", false)
                model.refresh()
            }
            compose.waitUntil(10000) { model.recordings.any { it.str("variant_id") == id } }
            compose.onNodeWithTag("tab1").performClick()
            compose.onNodeWithText("collection-navigation").performScrollTo().performClick()
            compose.onNodeWithTag("tab1").assertIsSelected()
            compose.onNodeWithTag("collectionDetail").assertExists()
            compose.onNodeWithText("Play").assertExists()
            compose.onNodeWithText("Repair / download again").assertExists()
            compose.onNodeWithText("Delete").assertExists()
            compose.activityRule.scenario.recreate()
            compose.onNodeWithTag("tab1").assertIsSelected()
            compose.onNodeWithTag("collectionBack").performClick()
            compose.onNodeWithText("Search saved entries").assertExists()
            compose.onNodeWithTag("tab0").performClick()
            assertEquals("search-draft", model.selected?.str("word"))
            assertTrue(model.translation.toString().contains("Keep my draft"))
        } finally {
            audio.delete()
            metadata.delete()
            compose.activityRule.scenario.onActivity { model.refresh() }
        }
    }

    @Test
    fun pureBlackAndDesktopRedPreferencesSurviveRecreation() {
        lateinit var model: AppModel
        compose.activityRule.scenario.onActivity { activity ->
            model = ViewModelProvider(activity)[AppModel::class.java]
            model.preference("language", "en")
            model.preference("theme", "system")
            model.setOled(false)
        }
        try {
            compose.onNodeWithTag("tab2").performClick()
            compose.onNodeWithTag("pureBlack").performScrollTo().performClick()
            compose.onNodeWithText("System").assertIsSelected()
            compose.onNodeWithText("Red").performScrollTo().performClick()
            compose.activityRule.scenario.recreate()
            compose.onNodeWithText("Red").performScrollTo().assertIsSelected()
            assertEquals("system", model.theme)
            assertTrue(model.pureBlack)
            assertEquals("red", model.color)
            assertFalse(model.dynamicColor)
            compose.onNodeWithTag("systemColors").performScrollTo().performClick()
            compose.onNodeWithText("Red").assertIsNotSelected()
            compose.onNodeWithText("Red").performClick()
            compose.onNodeWithTag("systemColors").assertIsOff()
            compose.onNodeWithText("Light").performScrollTo().performClick()
            assertTrue(model.pureBlack)
            compose.onNodeWithText("Dark").performClick()
            compose.onNodeWithTag("pureBlack").assertIsOn()
        } finally {
            compose.activityRule.scenario.onActivity {
                model.preference("theme", "system")
                model.setOled(false)
                model.preference("color", "blue")
                model.setDynamic(true)
            }
        }
    }

    @Test
    fun legacyBlackPreferenceMigratesToDarkWithIndependentOledToggle() {
        val app =
            InstrumentationRegistry.getInstrumentation().targetContext.applicationContext
                as android.app.Application
        val prefs = app.getSharedPreferences("preferences", android.content.Context.MODE_PRIVATE)
        val previousTheme = prefs.getString("theme", "system")!!
        val previousBlack = prefs.all["pureBlack"] as? Boolean
        val store = ViewModelStore()
        try {
            prefs.edit().putString("theme", "black").remove("pureBlack").commit()
            compose.activityRule.scenario.onActivity {
                val factory = viewModelFactory { initializer { AppModel(app, SavedStateHandle()) } }
                val migrated = ViewModelProvider(store, factory)[AppModel::class.java]
                assertEquals("dark", migrated.theme)
                assertTrue(migrated.pureBlack)
                assertEquals("dark", prefs.getString("theme", ""))
                assertTrue(prefs.getBoolean("pureBlack", false))
                migrated.preference("theme", "light")
                assertTrue(migrated.pureBlack)
                migrated.setOled(false)
                assertEquals("light", migrated.theme)
            }
        } finally {
            compose.activityRule.scenario.onActivity { store.clear() }
            prefs
                .edit()
                .putString("theme", previousTheme)
                .apply {
                    if (previousBlack == null) remove("pureBlack")
                    else putBoolean("pureBlack", previousBlack)
                }
                .commit()
        }
    }

    @Test
    fun persistentCoreNativeAudioAndStandaloneExports() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        val folder = File(context.cacheDir, "acceptance-${System.nanoTime()}").apply { mkdirs() }
        try {
            val native = AndroidPlatform()
            val platform =
                object : Platform by native {
                    override fun fetch(url: String, maxBytes: Long): HttpResult {
                        val data =
                            if (url.endsWith(".mp3"))
                                assets.open("segment-a.mp3").use { it.readBytes() }
                            else assets.open("test_shared_audio-bank.html").use { it.readBytes() }
                        return HttpResult(200, url, data)
                    }
                }
            val engine =
                Engine(File(folder, "collection").path, File(folder, "cache").path, platform)
            val results = Json.parseToJsonElement(engine.lookup("bank")).jsonArray
            val firstEntry = results[0].jsonObject
            val audio = firstEntry["pronunciations"]!!.jsonArray[0].jsonObject
            val audioId = stableId("cambridge-audio", "us", audio["url"]!!.jsonPrimitive.content)
            val first = parseObject(engine.save(firstEntry.toString(), audioId, false, ""))
            engine.save(results[1].toString(), audioId, false, "")
            assertEquals(
                1,
                File(folder, "collection").listFiles()!!.count { it.extension == "mp3" },
            )
            val identity = first.str("variant_id")
            engine.editTranslation(identity, "личный перевод", false)
            val restored = Engine(engine.collectionPath, engine.cachePath, platform)
            assertTrue(File(restored.audioPath(identity)).isFile)
            val apkg = File(folder, "native.apkg")
            AnkiExporter(restored).exportApkg(apkg.path, "[]")
            ZipFile(apkg).use { z ->
                val database = File(folder, "inspect.anki2")
                z.getInputStream(z.getEntry("collection.anki2")).use {
                    database.writeBytes(it.readBytes())
                }
                val rows =
                    Json.parseToJsonElement(
                            native.sqliteQuery(
                                database.path,
                                "SELECT guid, flds FROM notes",
                                emptyList(),
                            )
                        )
                        .jsonArray
                assertEquals(2, rows.size)
                assertTrue(rows.any { it.jsonArray[0].jsonPrimitive.content == ankiGuid(identity) })
            }
            val bundle = File(folder, "backup.cda")
            CollectionTransfer(restored).exportBundle(bundle.path)
            val target =
                Engine(File(folder, "second").path, File(folder, "second-cache").path, platform)
            val transfer = CollectionTransfer(target)
            transfer.applyImport(transfer.previewImport(bundle.path), "{}")
            assertEquals(2, Json.parseToJsonElement(target.records()).jsonArray.size)
            engine.deleteRecord(identity)
            assertTrue(File(engine.collectionPath, first.str("audio_file")).isFile)
            val segments =
                listOf("segment-a.mp3", "segment-b.mp3").map { name ->
                    File(folder, name)
                        .apply { writeBytes(assets.open(name).use { it.readBytes() }) }
                        .path
                }
            val phrase = File(folder, "phrase.mp3")
            PhraseAudio.combine(segments, phrase.path) { false }
            val extractor = MediaExtractor()
            try {
                extractor.setDataSource(phrase.path)
                assertEquals(
                    "audio/mpeg",
                    extractor.getTrackFormat(0).getString(MediaFormat.KEY_MIME),
                )
                val duration = extractor.getTrackFormat(0).getLong(MediaFormat.KEY_DURATION)
                assertTrue(duration in 950000..1150000)
            } finally {
                extractor.release()
            }
            assertThrows(Exception::class.java) { restored.audioPath(first.str("variant_id")) }
        } finally {
            folder.deleteRecursively()
        }
    }

    @Test
    fun phraseRepairAndBackupRestorePreserveOnePermanentRecordWithNativeAudio() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        val folder = File(context.cacheDir, "repair-${System.nanoTime()}").apply { mkdirs() }
        try {
            val native = AndroidPlatform()
            val requests = mutableListOf<String>()
            var allowLookup = true
            val firstUrl = "https://dictionary.cambridge.org/media/bank.mp3"
            val secondUrl = "https://dictionary.cambridge.org/media/second.mp3"
            val platform =
                object : Platform by native {
                    override fun fetch(url: String, maxBytes: Long): HttpResult {
                        requests += url
                        val data =
                            when (url) {
                                firstUrl -> assets.open("segment-a.mp3").use { it.readBytes() }
                                secondUrl -> assets.open("segment-b.mp3").use { it.readBytes() }
                                else -> {
                                    assertTrue("Repair must use the saved plan", allowLookup)
                                    assets
                                        .open("test_shared_audio-bank.html")
                                        .bufferedReader()
                                        .use { it.readText() }
                                        .replace(
                                            "</audio>",
                                            "</audio><audio><source src=\"/media/second.mp3\"></audio>",
                                        )
                                        .encodeToByteArray()
                                }
                            }
                        return HttpResult(200, url, data)
                    }
                }
            val engine =
                Engine(File(folder, "collection").path, File(folder, "cache").path, platform)
            val plan = engine.planPhrase("bank bank", "us")
            val choices =
                JsonArray(
                        listOf(secondUrl, firstUrl).map {
                            JsonPrimitive(stableId("cambridge-audio", "us", it))
                        }
                    )
                    .toString()
            val saved = parseObject(engine.synthesizeChosen(plan, choices))
            val id = saved.str("variant_id")
            engine.editTranslation(id, "saved phrase translation", false)
            File(engine.audioPath(id)).delete()
            requests.clear()
            allowLookup = false
            val restarted = Engine(engine.collectionPath, engine.cachePath, platform)
            val repaired = parseObject(restarted.repair(id))
            assertEquals(listOf(secondUrl, firstUrl), requests)
            assertEquals(saved["phrase_selections"], repaired["phrase_selections"])
            assertTrue(native.validateAudio(restarted.audioPath(id)))
            val archive = File(folder, "backup.cda").path
            val transfer = CollectionTransfer(restarted)
            transfer.exportBundle(archive)
            restarted.editTranslation(id, "local edit", false)
            val decisions = buildJsonObject { put(id, "incoming") }.toString()
            transfer.applyImport(transfer.previewImport(archive), decisions)
            assertEquals(1, Json.parseToJsonElement(restarted.records()).jsonArray.size)
            for (missing in listOf(true, false)) {
                val audio = File(restarted.audioPath(id))
                if (missing) audio.delete() else audio.writeText("corrupt")
                transfer.applyImport(transfer.previewImport(archive), decisions)
                val record =
                    Json.parseToJsonElement(restarted.records()).jsonArray.single().jsonObject
                assertEquals(id, record.str("variant_id"))
                assertTrue(native.validateAudio(restarted.audioPath(id)))
                assertTrue(
                    MobileJson()
                        .cachedTranslationJson(record.toString())
                        .contains("saved phrase translation")
                )
            }
        } finally {
            folder.deleteRecursively()
        }
    }

    @Test
    fun undecodableLegacyAudioShowsErrorWithoutCrashing() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val collection = File(context.filesDir, "collection").apply { mkdirs() }
        val identity = "aa0000000000000000000001"
        val audio = File(collection, "corrupt-regression.us.mp3")
        val metadata = File(collection, "$identity.us.json")
        val record =
            parseObject(
                """{"version":3,"word":"corrupt-regression","accent":"us","variant_id":"$identity","audio_file":"${audio.name}","separate_metadata":true}"""
            )
        audio.writeText("ID3invalid legacy media")
        metadata.writeText(record.toString())
        lateinit var model: AppModel
        try {
            compose.activityRule.scenario.onActivity { activity ->
                model = ViewModelProvider(activity)[AppModel::class.java]
                model.selectSaved(record)
                model.play()
            }
            compose.waitUntil(10000) { model.error != null }
            assertEquals("audio", model.error?.code)
            assertFalse(model.playing)
        } finally {
            audio.delete()
            metadata.delete()
            compose.activityRule.scenario.onActivity { model.refresh() }
        }
    }

    @Test
    fun desktopBundleToAndroidStandaloneExport() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        val folder = File(context.filesDir, "acceptance").apply { mkdirs() }
        val source = File(folder, "desktop.cda")
        source.writeBytes(assets.open("desktop.cda").use { it.readBytes() })
        val platform = AndroidPlatform()
        val engine = Engine(File(folder, "collection").path, File(folder, "cache").path, platform)
        val transfer = CollectionTransfer(engine)
        val preview = transfer.previewImport(source.path)
        val conflicts = parseObject(preview)["conflicts"]!!.jsonArray
        val decisions =
            JsonObject(
                conflicts.associate { it.jsonPrimitive.content to JsonPrimitive("incoming") }
            )
        transfer.applyImport(preview, decisions.toString())
        val records = Json.parseToJsonElement(engine.records()).jsonArray.map { it.jsonObject }
        assertEquals(3, records.size)
        val money = records.single {
            it.str("definition") == "an organization where people keep and borrow money"
        }
        engine.editTranslation(money.str("variant_id"), "Android personal translation", false)
        AnkiExporter(engine).exportApkg(File(folder, "android.apkg").path, "[]")
        transfer.exportBundle(File(folder, "android.cda").path)
        assertEquals(
            1,
            records
                .filter { it.str("word") == "bank" }
                .map { it.str("audio_file") }
                .distinct()
                .size,
        )
    }
}
