package org.cambridgeaudio.core

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.serialization.json.*

/** Opt-in integration handoff to scripts/verify_mobile_anki.py; no Cambridge I/O. */
class CrossPlatformAcceptance {
    @Test
    fun transferAndExport() {
        val location = System.getenv("CDA_ACCEPTANCE_ROOT")
        org.junit.Assume.assumeTrue(
            "Requires disposable real-Anki acceptance setup",
            location != null,
        )
        requireNotNull(location)
        val root = File(location)
        val platform = TestPlatform()
        val engine =
            Engine(File(root, "mobile-collection").path, File(root, "mobile-cache").path, platform)
        val transfer = CollectionTransfer(engine)
        val input = File(root, "desktop.cda").path
        val preview = transfer.previewImport(input)
        transfer.applyImport(preview, "{}")
        val records = Json.parseToJsonElement(engine.records()).jsonArray.map { it.jsonObject }
        assertEquals(3, records.size)
        val money = records.single {
            it.text("definition") == "an organization where people keep and borrow money"
        }
        engine.editTranslation(money.text("variant_id"), "мобильный личный перевод", false)
        val record =
            engine.storage
                .identity(money.text("variant_id"))
                .with("definition" to "updated financial meaning from mobile")
        engine.storage.save(record)
        AnkiExporter(engine).exportApkg(File(root, "mobile.apkg").path, "[]")
        transfer.exportBundle(File(root, "mobile.cda").path)
        // A second independent Kotlin storage exercises a transfer/restart. It is
        // explicitly a JVM adapter, not a claim of iOS device validation.
        val second =
            Engine(File(root, "second-mobile").path, File(root, "second-cache").path, platform)
        val next = CollectionTransfer(second)
        next.applyImport(next.previewImport(File(root, "mobile.cda").path), "{}")
        next.exportBundle(File(root, "return.cda").path)
        AnkiExporter(second).exportApkg(File(root, "second-mobile.apkg").path, "[]")
        assertEquals(
            records.map { it.text("variant_id") }.toSet(),
            second.storage.scan().map { it.text("variant_id") }.toSet(),
        )
        assertTrue(File(root, "mobile.apkg").isFile)
        File(root, "mobile-results.json").writeText(engine.records())
    }
}
