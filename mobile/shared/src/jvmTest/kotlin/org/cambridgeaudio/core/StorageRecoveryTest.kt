package org.cambridgeaudio.core

import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.*
import kotlinx.serialization.json.JsonArray
import okio.Path.Companion.toPath

class StorageRecoveryTest {
    @Test
    fun diskFullBeforeCommitPreservesOldMediaAndMetadata() {
        val folder = Files.createTempDirectory("cda-full").toFile()
        try {
            val platform = TestPlatform()
            val root = File(folder, "collection")
            val storage = Storage(root.path.toPath(), platform)
            val old =
                mapOf(
                    "bank.us.mp3" to "ID3old".encodeToByteArray(),
                    "bank.us.json" to "old metadata".encodeToByteArray(),
                )
            storage.commitFiles(old)
            var writes = 0
            platform.beforeSync = {
                if (++writes == 2) throw IOException("No space left on device")
            }
            assertFailsWith<IOException> {
                storage.commitFiles(
                    mapOf(
                        "bank.us.mp3" to "ID3new".encodeToByteArray(),
                        "bank.us.json" to "new metadata".encodeToByteArray(),
                    )
                )
            }
            old.forEach { (name, bytes) ->
                assertContentEquals(bytes, File(root, name).readBytes())
            }
            assertFalse(File(folder, ".collection.write.json").exists())
            assertEquals(listOf("collection"), folder.list()!!.toList())
        } finally {
            folder.deleteRecursively()
        }
    }

    @Test
    fun restartCompletesInterruptedCommittedMediaAndMetadataTogether() {
        val folder = Files.createTempDirectory("cda-recover").toFile()
        try {
            val root = File(folder, "collection").apply { mkdir() }
            val pending = File(folder, ".collection.pending-test").apply { mkdir() }
            val audio = "ID3new".encodeToByteArray()
            val metadata = "new metadata".encodeToByteArray()
            // Process died after installing audio but before moving its matching metadata.
            File(root, "bank.us.mp3").writeBytes(audio)
            File(root, "bank.us.json").writeText("old metadata")
            File(pending, "bank.us.json").writeBytes(metadata)
            File(folder, ".collection.write.json")
                .writeText(
                    document(
                            "version" to 1,
                            "pending" to pending.name,
                            "files" to
                                JsonArray(
                                    listOf(
                                        document(
                                            "name" to "bank.us.mp3",
                                            "sha256" to sha256(audio),
                                        ),
                                        document(
                                            "name" to "bank.us.json",
                                            "sha256" to sha256(metadata),
                                        ),
                                    )
                                ),
                        )
                        .toString()
                )
            Storage(root.path.toPath(), TestPlatform())
            assertContentEquals(audio, File(root, "bank.us.mp3").readBytes())
            assertContentEquals(metadata, File(root, "bank.us.json").readBytes())
            assertEquals(listOf("collection"), folder.list()!!.toList())
            Storage(root.path.toPath(), TestPlatform())
            assertContentEquals(metadata, File(root, "bank.us.json").readBytes())
        } finally {
            folder.deleteRecursively()
        }
    }

    @Test
    fun cancellationBeforeDurableIntentPreservesSavedFiles() {
        val folder = Files.createTempDirectory("cda-cancel").toFile()
        try {
            val platform = TestPlatform()
            val root = File(folder, "collection")
            val storage = Storage(root.path.toPath(), platform)
            storage.commitFiles(mapOf("bank.us.mp3" to "ID3old".encodeToByteArray()))
            platform.beforeSync = { platform.aborted = true }
            assertFails {
                storage.commitFiles(mapOf("bank.us.mp3" to "ID3new".encodeToByteArray()))
            }
            assertEquals("ID3old", File(root, "bank.us.mp3").readText())
            assertEquals(listOf("collection"), folder.list()!!.toList())
        } finally {
            folder.deleteRecursively()
        }
    }
}
