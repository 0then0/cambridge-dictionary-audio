package org.cambridgeaudio.core

import java.io.File
import java.io.FileOutputStream
import java.sql.DriverManager
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.*

internal class TestPlatform : Platform {
    var aborted = false
    val responses = mutableMapOf<String, ByteArray>()
    var requests = mutableListOf<String>()
    var clock = 1800000000L
    var beforeSync: (String) -> Unit = {}

    override fun fetch(url: String, maxBytes: Long): HttpResult {
        requests += url
        return responses[url]?.let { HttpResult(200, url, it) }
            ?: HttpResult(404, url, byteArrayOf())
    }

    override fun cancelled() = aborted

    override fun randomId() = UUID.randomUUID().toString().replace("-", "")

    override fun nowSeconds() = clock

    override fun pause(milliseconds: Long) {
        clock++
    }

    override fun syncFile(path: String) {
        beforeSync(path)
        FileOutputStream(path, true).use { it.fd.sync() }
    }

    override fun archiveList(path: String): String =
        ZipFile(path).use { zip ->
            JsonArray(
                    zip.entries()
                        .asSequence()
                        .map { entry ->
                            document(
                                "name" to entry.name,
                                "size" to entry.size,
                                "directory" to entry.isDirectory,
                            )
                        }
                        .toList()
                )
                .toString()
        }

    override fun archiveRead(path: String, member: String, maxBytes: Long): ByteArray =
        ZipFile(path).use { zip ->
            val entry = zip.getEntry(member) ?: throw MobileError("archive", member)
            require(entry.size <= maxBytes)
            zip.getInputStream(entry).use { it.readBytes() }
        }

    override fun archiveWrite(path: String, names: List<String>, files: List<String>) {
        ZipOutputStream(FileOutputStream(path)).use { zip ->
            for ((name, file) in names.zip(files)) {
                zip.putNextEntry(ZipEntry(name))
                zip.write(File(file).readBytes())
                zip.closeEntry()
            }
        }
    }

    override fun sqliteQuery(path: String, sql: String, arguments: List<String>): String =
        DriverManager.getConnection("jdbc:sqlite:file:$path?mode=ro").use { conn ->
            conn.prepareStatement(sql).use { statement ->
                arguments.forEachIndexed { i, value -> statement.setString(i + 1, value) }
                statement.executeQuery().use { rows ->
                    val result = mutableListOf<JsonArray>()
                    while (rows.next()) result +=
                        JsonArray(
                            (1..rows.metaData.columnCount).map {
                                rows.getString(it)?.let(::JsonPrimitive) ?: JsonNull
                            }
                        )
                    JsonArray(result).toString()
                }
            }
        }

    override fun sqliteCreate(path: String, statements: List<String>) {
        DriverManager.getConnection("jdbc:sqlite:$path").use { conn ->
            conn.autoCommit = false
            conn.createStatement().use { statement -> statements.forEach { statement.execute(it) } }
            conn.commit()
        }
    }

    override fun validateAudio(path: String) {
        if (!isMp3(File(path).readBytes())) throw MobileError("audio", "MP3 cannot be decoded")
    }

    override fun synthesize(segments: List<String>, destination: String) {
        throw MobileError("test", "Native codec tested separately")
    }
}
