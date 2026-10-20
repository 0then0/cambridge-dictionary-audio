package org.cambridgeaudio.app

import android.database.sqlite.SQLiteDatabase
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.*
import org.cambridgeaudio.core.*

class AndroidPlatform : Platform {
    @Volatile var cancellation = AtomicBoolean(false)

    override fun cancelled() = cancellation.get()

    override fun pause(milliseconds: Long) {
        Thread.sleep(milliseconds)
    }

    override fun randomId() = UUID.randomUUID().toString().replace("-", "")

    override fun nowSeconds() = System.currentTimeMillis() / 1000

    override fun syncFile(path: String) {
        FileOutputStream(File(path), true).use { it.fd.sync() }
    }

    override fun fetch(url: String, maxBytes: Long): HttpResult {
        var current = url
        repeat(6) {
            if (cancelled()) throw MobileError("cancelled")
            val uri = URI(current)
            if (
                uri.scheme != "https" ||
                    uri.userInfo != null ||
                    uri.port !in listOf(-1, 443) ||
                    uri.host !in listOf("dictionary.cambridge.org", "download.wikdict.com")
            )
                throw MobileError("network", "Untrusted redirect")
            val connection = uri.toURL().openConnection() as HttpURLConnection
            try {
                connection.instanceFollowRedirects = false
                connection.connectTimeout = 15000
                connection.readTimeout = 15000
                connection.setRequestProperty(
                    "User-Agent",
                    "Mozilla/5.0 CambridgeDictionaryAudio/${BuildConfig.VERSION_NAME}",
                )
                val status = connection.responseCode
                if (status in listOf(301, 302, 303, 307, 308)) {
                    current = uri.resolve(connection.getHeaderField("Location")).toString()
                    return@repeat
                }
                if (connection.contentLengthLong > maxBytes)
                    throw MobileError("network", "Oversized response")
                val input = if (status >= 400) connection.errorStream else connection.inputStream
                val output = java.io.ByteArrayOutputStream()
                input?.use { stream ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        if (cancelled()) throw MobileError("cancelled")
                        val count = stream.read(buffer)
                        if (count < 0) break
                        if (output.size().toLong() + count > maxBytes)
                            throw MobileError("network", "Oversized response")
                        output.write(buffer, 0, count)
                    }
                }
                return HttpResult(
                    status,
                    current,
                    output.toByteArray(),
                    connection.getHeaderField("Retry-After").orEmpty(),
                )
            } finally {
                connection.disconnect()
            }
        }
        throw MobileError("network", "Too many redirects")
    }

    override fun archiveList(path: String): String =
        ZipFile(path).use { zip ->
            JsonArray(
                    zip.entries()
                        .asSequence()
                        .map { e ->
                            buildJsonObject {
                                put("name", e.name)
                                put("size", e.size)
                                put("compressed_size", e.compressedSize)
                                put("directory", e.isDirectory)
                                // java.util.zip does not expose Unix modes; links are never
                                // extracted.
                                // Content is consumed only as validated bytes under a generated
                                // path.
                                put("symlink", false)
                                put("encrypted", false)
                            }
                        }
                        .toList()
                )
                .toString()
        }

    override fun archiveRead(path: String, member: String, maxBytes: Long): ByteArray =
        ZipFile(path).use { zip ->
            val entry =
                zip.getEntry(member) ?: throw MobileError("archive", "Missing member $member")
            if (entry.size !in 0..maxBytes) throw MobileError("archive", "Oversized member")
            zip.getInputStream(entry).use { stream ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(65536)
                while (true) {
                    if (cancelled()) throw MobileError("cancelled")
                    val count = stream.read(buffer)
                    if (count < 0) break
                    if (output.size().toLong() + count > maxBytes)
                        throw MobileError("archive", "Oversized member")
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
        }

    override fun archiveWrite(path: String, names: List<String>, files: List<String>) {
        require(names.size == files.size)
        FileOutputStream(path).use { file ->
            ZipOutputStream(file).use { zip ->
                for ((name, source) in names.zip(files)) {
                    if (cancelled()) throw MobileError("cancelled")
                    zip.putNextEntry(ZipEntry(name))
                    FileInputStream(source).use { it.copyTo(zip) }
                    zip.closeEntry()
                }
                zip.finish()
                file.fd.sync()
            }
        }
    }

    override fun sqliteQuery(path: String, sql: String, arguments: List<String>): String {
        return SQLiteDatabase.openDatabase(
                path,
                null,
                SQLiteDatabase.OPEN_READONLY or SQLiteDatabase.NO_LOCALIZED_COLLATORS,
            )
            .use { db ->
                db.rawQuery(sql, arguments.toTypedArray()).use { cursor ->
                    val rows = mutableListOf<JsonArray>()
                    while (cursor.moveToNext()) rows +=
                        JsonArray(
                            (0 until cursor.columnCount).map {
                                if (cursor.isNull(it)) JsonNull
                                else JsonPrimitive(cursor.getString(it))
                            }
                        )
                    JsonArray(rows).toString()
                }
            }
    }

    override fun sqliteCreate(path: String, statements: List<String>) {
        SQLiteDatabase.openOrCreateDatabase(path, null).use { db ->
            db.beginTransaction()
            try {
                statements.forEach {
                    if (cancelled()) throw MobileError("cancelled")
                    db.execSQL(it)
                }
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
            }
        }
    }

    override fun validateAudio(path: String) {
        if (!PhraseAudio.validate(path, ::cancelled))
            throw MobileError("audio", "MP3 cannot be decoded")
    }

    override fun synthesize(segments: List<String>, destination: String) {
        PhraseAudio.combine(segments, destination, ::cancelled)
    }
}
