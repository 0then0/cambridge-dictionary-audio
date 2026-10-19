package org.cambridgeaudio.core

import java.io.File
import java.io.RandomAccessFile
import java.nio.file.Files
import kotlin.test.*

class WikdictStatusTest {
    @Test
    fun missingAndDamagedPackagesAreDetectedWithoutNetworkOrModification() {
        val folder = Files.createTempDirectory("cda-dictionary-status").toFile()
        try {
            val platform = TestPlatform()
            val engine =
                Engine(File(folder, "collection").path, File(folder, "cache").path, platform)
            assertEquals("missing", engine.wikdictStatus())
            val dictionary = File(folder, "en-ru-${Engine.WIKDICT_VERSION}.sqlite3")
            dictionary.writeText("damaged")
            assertEquals("corrupt", engine.wikdictStatus())
            assertEquals("damaged", dictionary.readText())
            RandomAccessFile(dictionary, "rw").use { it.setLength(Engine.WIKDICT_SIZE) }
            val hash = sha256(dictionary.readBytes())
            assertEquals("corrupt", engine.wikdictStatus())
            assertEquals(hash, sha256(dictionary.readBytes()))
            assertTrue(platform.requests.isEmpty())
        } finally {
            folder.deleteRecursively()
        }
    }

    @Test
    fun verifiedPackageAndFailedReplacementPreserveInstalledDictionary() {
        val fixture = System.getenv("CDA_WIKDICT_ACCEPTANCE_PATH")
        org.junit.Assume.assumeTrue("Needs a local pinned WikDict package", fixture != null)
        val folder = Files.createTempDirectory("cda-dictionary-reinstall").toFile()
        try {
            val platform = TestPlatform()
            val engine =
                Engine(File(folder, "collection").path, File(folder, "cache").path, platform)
            val dictionary = File(folder, "en-ru-${Engine.WIKDICT_VERSION}.sqlite3")
            File(fixture!!).copyTo(dictionary)
            assertEquals("ready", engine.wikdictStatus())
            assertTrue(platform.requests.isEmpty())
            platform.responses[Engine.WIKDICT_URL] = "bad download".encodeToByteArray()
            assertEquals(
                "dictionary_corrupt",
                assertFailsWith<MobileError> { engine.installWikdict() }.code,
            )
            assertEquals("ready", engine.wikdictStatus())
            assertEquals(Engine.WIKDICT_SHA256, sha256(dictionary.readBytes()))
            platform.responses[Engine.WIKDICT_URL] = File(fixture).readBytes()
            assertEquals(Engine.WIKDICT_VERSION, engine.installWikdict())
            assertEquals("ready", engine.wikdictStatus())
        } finally {
            folder.deleteRecursively()
        }
    }
}
