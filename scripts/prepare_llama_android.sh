#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="$ROOT_DIR/vendor/llama.cpp"
# 2026-08-25 upstream llama.cpp. Includes the dynamic split-input fix for wide
# models plus the Gemma 4/runtime fixes merged after the previous 2026-08-03 pin.
LLAMA_COMMIT="d222767c7a6516559a3f49e7721b6c6b1acc87b4"

if [[ -d "$VENDOR_DIR/.git" ]] && [[ "$(git -C "$VENDOR_DIR" rev-parse HEAD 2>/dev/null || true)" == "$LLAMA_COMMIT" ]]; then
  echo "Pinned llama.cpp already prepared: $LLAMA_COMMIT"
else
  rm -rf "$VENDOR_DIR"
  mkdir -p "$(dirname "$VENDOR_DIR")"
  git init -q "$VENDOR_DIR"
  git -C "$VENDOR_DIR" remote add origin https://github.com/ggml-org/llama.cpp.git
  git -C "$VENDOR_DIR" fetch --depth 1 origin "$LLAMA_COMMIT"
  git -C "$VENDOR_DIR" checkout -q --detach FETCH_HEAD
fi

LIB_DIR="$VENDOR_DIR/examples/llama.android/lib"

cat > "$LIB_DIR/build.gradle.kts" <<'EOF'
plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.arm.aichat"
    compileSdk = 36
    ndkVersion = "29.0.13113456"

    defaultConfig {
        minSdk = 26

        ndk {
            abiFilters += "arm64-v8a"
        }

        externalNativeBuild {
            cmake {
                arguments += "-DCMAKE_BUILD_TYPE=Release"
                arguments += "-DBUILD_SHARED_LIBS=ON"
                arguments += "-DLLAMA_BUILD_APP=OFF"
                arguments += "-DLLAMA_BUILD_COMMON=ON"
                arguments += "-DLLAMA_OPENSSL=OFF"
                arguments += "-DGGML_NATIVE=OFF"
                arguments += "-DGGML_BACKEND_DL=ON"
                # Stability-first build for Android. v0.3.6 died during Gemma 4
                # prompt prefill before the first generated token. Avoid runtime
                # CPU-variant selection until that path is proven stable.
                arguments += "-DGGML_CPU_ALL_VARIANTS=OFF"
                arguments += "-DGGML_LLAMAFILE=OFF"
            }
        }
    }

    externalNativeBuild {
        cmake {
            path("src/main/cpp/CMakeLists.txt")
            version = "3.31.6"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.18.0")
    implementation("androidx.datastore:datastore-preferences:1.2.0")
}
EOF

python3 - "$LIB_DIR/src/main/cpp/ai_chat.cpp" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
s = s.replace('constexpr int   DEFAULT_CONTEXT_SIZE    = 8192;',
              'constexpr int   DEFAULT_CONTEXT_SIZE    = 2048;')
s = s.replace('constexpr int   BATCH_SIZE              = 512;',
              'constexpr int   BATCH_SIZE              = 8;')

if 'constexpr int   DEFAULT_CONTEXT_SIZE    = 2048;' not in s:
    raise SystemExit('Could not patch mobile context size in ai_chat.cpp')
if 'constexpr int   BATCH_SIZE              = 8;' not in s:
    raise SystemExit('Could not patch stability batch size in ai_chat.cpp')

# Translation/summary requests are independent jobs, not a chat conversation.
# Clear chat/KV history before every user prompt while keeping model weights loaded.
old = '''Java_com_arm_aichat_internal_InferenceEngineImpl_processUserPrompt(
        JNIEnv *env,
        jobject /*unused*/,
        jstring juser_prompt,
        jint n_predict
) {
    // Reset short-term states
    reset_short_term_states();'''
new = '''Java_com_arm_aichat_internal_InferenceEngineImpl_processUserPrompt(
        JNIEnv *env,
        jobject /*unused*/,
        jstring juser_prompt,
        jint n_predict
) {
    // Kirapara News runs independent translation/summary jobs.
    reset_long_term_states();
    reset_short_term_states();'''
if old not in s:
    raise SystemExit('Could not patch independent prompt reset in ai_chat.cpp')
s = s.replace(old, new, 1)
p.write_text(s)
PY

# Upstream Android sample currently calls an API introduced in Android 30.
# Preserve app minSdk 26 by using a simple priority fallback on older devices.
python3 - "$LIB_DIR/src/main/cpp/logging.h" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
old = '''static inline int ai_should_log(int prio) {
    return __android_log_is_loggable(prio, LOG_TAG, LOG_MIN_LEVEL);
}'''
new = '''static inline int ai_should_log(int prio) {
#if __ANDROID_API__ >= 30
    return __android_log_is_loggable(prio, LOG_TAG, LOG_MIN_LEVEL);
#else
    return prio >= LOG_MIN_LEVEL;
#endif
}'''
if old not in s:
    raise SystemExit('Could not patch Android < 30 logging compatibility')
s = s.replace(old, new, 1)
p.write_text(s)
PY

# Keep compatibility with a previously selected SAF descriptor if it reaches the
# upstream wrapper. v0.3.4+ normally uses an app-private prepared model path.
python3 - "$LIB_DIR/src/main/java/com/arm/aichat/internal/InferenceEngineImpl.kt" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()
old = '''                File(pathToModel).let {
                    require(it.exists()) { "File not found" }
                    require(it.isFile) { "Not a valid file" }
                    require(it.canRead()) { "Cannot read file" }
                }
'''
new = '''                if (pathToModel.startsWith("/proc/self/fd/")) {
                    Log.i(TAG, "Using open SAF file descriptor; skipping java.io.File access checks")
                } else {
                    File(pathToModel).let {
                        require(it.exists()) { "File not found" }
                        require(it.isFile) { "Not a valid file" }
                        require(it.canRead()) { "Cannot read file" }
                    }
                }
'''
if old not in s:
    raise SystemExit('Could not patch SAF /proc/self/fd access check')
s = s.replace(old, new, 1)
p.write_text(s)
PY

echo "Prepared official llama.cpp Android runtime at $LLAMA_COMMIT (ctx=2048 batch=8 generic-cpu)"
