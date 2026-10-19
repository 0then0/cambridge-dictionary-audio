#include "phrase_codec.h"
#include <lame.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

int cda_encode_phrase(const float *pcm, size_t frames, const char *destination) {
    if (!pcm || !frames || frames > 44100u * 600u || !destination) return -1;
    /* A single gain across the phrase retains segment dynamics. Target -18 dBFS
       RMS with a -1 dBFS peak ceiling. Platform decoders supply mono 44.1 kHz. */
    double sum = 0.0; float peak = 0.0f;
    for (size_t i = 0; i < frames; ++i) {
        if (!isfinite(pcm[i])) return -2;
        sum += (double)pcm[i] * pcm[i];
        if (fabsf(pcm[i]) > peak) peak = fabsf(pcm[i]);
    }
    double rms = sqrt(sum / frames);
    float gain = rms > 1e-9 ? (float)(pow(10.0, -18.0 / 20.0) / rms) : 1.0f;
    if (peak * gain > 0.891251f) gain = 0.891251f / peak;
    lame_t lame = lame_init();
    if (!lame) return -3;
    lame_set_in_samplerate(lame, 44100);
    lame_set_num_channels(lame, 1);
    lame_set_brate(lame, 128);
    lame_set_quality(lame, 2);
    lame_set_write_id3tag_automatic(lame, 1);
    if (lame_init_params(lame) < 0) { lame_close(lame); return -4; }
    FILE *file = fopen(destination, "w+b");
    if (!file) { lame_close(lame); return -5; }
    float input[8192]; unsigned char output[65536];
    int result = 0;
    for (size_t offset = 0; offset < frames; offset += 8192) {
        size_t count = frames - offset < 8192 ? frames - offset : 8192;
        for (size_t i = 0; i < count; ++i) input[i] = pcm[offset + i] * gain;
        int bytes = lame_encode_buffer_ieee_float(lame, input, input, (int)count, output, sizeof(output));
        if (bytes < 0 || fwrite(output, 1, (size_t)bytes, file) != (size_t)bytes) { result = -6; break; }
    }
    if (!result) {
        int bytes = lame_encode_flush(lame, output, sizeof(output));
        if (bytes < 0 || fwrite(output, 1, (size_t)bytes, file) != (size_t)bytes) result = -7;
        if (!result) lame_mp3_tags_fid(lame, file);
    }
    lame_close(lame);
    if (fclose(file)) result = -8;
    if (result) remove(destination);
    return result;
}
