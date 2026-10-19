#ifndef CDA_PHRASE_CODEC_H
#define CDA_PHRASE_CODEC_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* 44100 Hz mono float PCM. Returns 0 on success; never creates a fake container. */
int cda_encode_phrase(const float *pcm, size_t frames, const char *destination);
#ifdef __cplusplus
}
#endif
#endif
