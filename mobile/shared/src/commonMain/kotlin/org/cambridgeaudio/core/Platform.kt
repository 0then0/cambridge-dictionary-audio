package org.cambridgeaudio.core

import okio.FileSystem

/** Blocking adapters are invoked only on a worker, never on the presentation thread. */
interface Platform {
    @Throws(Exception::class) fun fetch(url: String, maxBytes: Long): HttpResult

    @Throws(Exception::class) fun archiveList(path: String): String

    @Throws(Exception::class)
    fun archiveRead(path: String, member: String, maxBytes: Long): ByteArray

    @Throws(Exception::class)
    fun archiveWrite(path: String, names: List<String>, files: List<String>)

    @Throws(Exception::class)
    fun sqliteQuery(path: String, sql: String, arguments: List<String>): String

    @Throws(Exception::class) fun sqliteCreate(path: String, statements: List<String>)

    @Throws(Exception::class) fun synthesize(segments: List<String>, destination: String)

    // Throw on invalid audio. Unit also supports Swift implementations of this ObjC protocol;
    // Swift cannot export a throwing method whose result is a primitive Boolean.
    @Throws(Exception::class) fun validateAudio(path: String)

    fun randomId(): String

    fun nowSeconds(): Long

    fun cancelled(): Boolean

    fun pause(milliseconds: Long)

    @Throws(Exception::class) fun syncFile(path: String)
}

class HttpResult(val status: Int, val url: String, val body: ByteArray, val retryAfter: String = "")

class MobileError(val code: String, val detail: String = "") : Exception("$code: $detail")

internal expect fun systemFileSystem(): FileSystem

internal expect fun normalizeGloss(text: String): String
