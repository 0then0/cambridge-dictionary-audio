package org.cambridgeaudio.app

import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import java.nio.ByteOrder
import kotlin.math.floor
import org.cambridgeaudio.core.MobileError

object PhraseAudio {
    init {
        System.loadLibrary("cambridge_phrase")
    }

    private external fun encode(samples: FloatArray, destination: String): Int

    fun combine(segments: List<String>, destination: String, cancelled: () -> Boolean) {
        val decoded = segments.map { decode(it, cancelled) }
        val size = decoded.sumOf { it.size }
        if (size <= 0 || size > 44100 * 600) throw MobileError("audio", "Phrase exceeds 10 minutes")
        val pcm = FloatArray(size)
        var offset = 0
        decoded.forEach {
            it.copyInto(pcm, offset)
            offset += it.size
        }
        if (cancelled()) throw MobileError("cancelled")
        val result = encode(pcm, destination)
        if (result != 0) throw MobileError("audio", "LAME error $result")
        if (cancelled()) {
            java.io.File(destination).delete()
            throw MobileError("cancelled")
        }
    }

    fun validate(path: String, cancelled: () -> Boolean): Boolean {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(path)
            if (
                (0 until extractor.trackCount).none {
                    extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME) == "audio/mpeg"
                }
            )
                return false
        } finally {
            extractor.release()
        }
        return decode(path, cancelled).let { it.isNotEmpty() && it.all(Float::isFinite) }
    }

    private fun decode(path: String, cancelled: () -> Boolean): FloatArray {
        val extractor = MediaExtractor()
        var decoder: MediaCodec? = null
        try {
            extractor.setDataSource(path)
            val track =
                (0 until extractor.trackCount).firstOrNull {
                    extractor
                        .getTrackFormat(it)
                        .getString(MediaFormat.KEY_MIME)
                        ?.startsWith("audio/") == true
                } ?: throw MobileError("audio", "No audio track")
            extractor.selectTrack(track)
            var format = extractor.getTrackFormat(track)
            val codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
            decoder = codec
            codec.configure(format, null, null, 0)
            codec.start()
            var inputDone = false
            var outputDone = false
            var rate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var encoding = AudioFormat.ENCODING_PCM_16BIT
            val chunks = mutableListOf<FloatArray>()
            var total = 0
            var stalled = 0
            val info = MediaCodec.BufferInfo()
            while (!outputDone) {
                if (cancelled()) throw MobileError("cancelled")
                if (!inputDone) {
                    val index = codec.dequeueInputBuffer(10000)
                    if (index >= 0) {
                        val buffer = codec.getInputBuffer(index)!!
                        val count = extractor.readSampleData(buffer, 0)
                        if (count < 0) {
                            codec.queueInputBuffer(
                                index,
                                0,
                                0,
                                0,
                                MediaCodec.BUFFER_FLAG_END_OF_STREAM,
                            )
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(index, 0, count, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                when (val index = codec.dequeueOutputBuffer(info, 10000)) {
                    MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        format = codec.outputFormat
                        rate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                        encoding =
                            if (format.containsKey(MediaFormat.KEY_PCM_ENCODING))
                                format.getInteger(MediaFormat.KEY_PCM_ENCODING)
                            else AudioFormat.ENCODING_PCM_16BIT
                    }
                    MediaCodec.INFO_TRY_AGAIN_LATER -> {
                        stalled++
                        if (stalled > 1500) throw MobileError("audio", "Decoder stalled")
                    }
                    else ->
                        if (index >= 0) {
                            stalled = 0
                            val buffer =
                                codec
                                    .getOutputBuffer(index)!!
                                    .duplicate()
                                    .order(ByteOrder.nativeOrder())
                            buffer.position(info.offset)
                            buffer.limit(info.offset + info.size)
                            val width =
                                if (encoding == AudioFormat.ENCODING_PCM_FLOAT) 4
                                else if (encoding == AudioFormat.ENCODING_PCM_16BIT) 2
                                else throw MobileError("audio", "Unsupported PCM encoding")
                            val mono = FloatArray(info.size / width / channels)
                            for (i in mono.indices) {
                                var sample = 0f
                                repeat(channels) {
                                    sample +=
                                        if (width == 4) buffer.float else buffer.short / 32768f
                                }
                                mono[i] = sample / channels
                            }
                            chunks += mono
                            total += mono.size
                            if (total > rate * 600)
                                throw MobileError("audio", "Segment exceeds 10 minutes")
                            outputDone = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                            codec.releaseOutputBuffer(index, false)
                        }
                }
            }
            val samples = FloatArray(total)
            var offset = 0
            chunks.forEach {
                it.copyInto(samples, offset)
                offset += it.size
            }
            if (rate == 44100) return samples
            if (samples.isEmpty() || rate <= 0) throw MobileError("audio", "Empty decoder output")
            return FloatArray((samples.size.toLong() * 44100 / rate).toInt()) { i ->
                val position = i.toDouble() * rate / 44100
                val lower = floor(position).toInt().coerceAtMost(samples.lastIndex)
                val upper = (lower + 1).coerceAtMost(samples.lastIndex)
                val fraction = (position - lower).toFloat()
                samples[lower] * (1 - fraction) + samples[upper] * fraction
            }
        } finally {
            decoder?.let {
                runCatching { it.stop() }
                it.release()
            }
            extractor.release()
        }
    }
}
