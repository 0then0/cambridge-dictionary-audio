#include <jni.h>
#include "phrase_codec.h"
JNIEXPORT jint JNICALL Java_org_cambridgeaudio_app_PhraseAudio_encode(JNIEnv *env, jobject self, jfloatArray samples, jstring destination) {
    (void)self;
    jfloat *pcm = (*env)->GetFloatArrayElements(env, samples, 0);
    const char *path = (*env)->GetStringUTFChars(env, destination, 0);
    int result = cda_encode_phrase(pcm, (size_t)(*env)->GetArrayLength(env, samples), path);
    (*env)->ReleaseStringUTFChars(env, destination, path);
    (*env)->ReleaseFloatArrayElements(env, samples, pcm, JNI_ABORT);
    return result;
}
