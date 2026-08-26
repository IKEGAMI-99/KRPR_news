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
                // Stability-first Android build. Keep one conservative generic
                // arm64 CPU backend and keep Q4_0 in its original layout.
                arguments += "-DGGML_CPU_ALL_VARIANTS=OFF"
                arguments += "-DGGML_CPU_REPACK=OFF"
                arguments += "-DGGML_CPU_KLEIDIAI=OFF"
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

# Keep the deliberately tiny v0.3.8 inference profile while verifying the real
# native crash fix. Once Gemma 4 generates reliably, performance can be restored
# independently without mixing correctness and optimization changes.
s = s.replace('constexpr int   N_THREADS_MIN           = 2;',
              'constexpr int   N_THREADS_MIN           = 1;')
s = s.replace('constexpr int   N_THREADS_MAX           = 4;',
              'constexpr int   N_THREADS_MAX           = 1;')
s = s.replace('constexpr int   N_THREADS_HEADROOM      = 2;',
              'constexpr int   N_THREADS_HEADROOM      = 0;')
s = s.replace('constexpr int   DEFAULT_CONTEXT_SIZE    = 8192;',
              'constexpr int   DEFAULT_CONTEXT_SIZE    = 1024;')
s = s.replace('constexpr int   BATCH_SIZE              = 512;',
              'constexpr int   BATCH_SIZE              = 1;')

checks = [
    'constexpr int   N_THREADS_MIN           = 1;',
    'constexpr int   N_THREADS_MAX           = 1;',
    'constexpr int   N_THREADS_HEADROOM      = 0;',
    'constexpr int   DEFAULT_CONTEXT_SIZE    = 1024;',
    'constexpr int   BATCH_SIZE              = 1;',
]
for check in checks:
    if check not in s:
        raise SystemExit(f'Could not patch stability setting: {check}')

# Gemma 4 has unusual attention shapes. Keep the ordinary attention path until
# the first complete translation/summary succeeds on-device.
needle = '''    ctx_params.n_threads = n_threads;
    ctx_params.n_threads_batch = n_threads;'''
replacement = '''    ctx_params.n_threads = n_threads;
    ctx_params.n_threads_batch = n_threads;
    ctx_params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;'''
if needle not in s:
    raise SystemExit('Could not patch Flash Attention setting in ai_chat.cpp')
s = s.replace(needle, replacement, 1)

# The Gemma 4 GGUF carries a custom Jinja chat template. The upstream Android
# sample hard-codes use_jinja=false, which throws std::runtime_error before the
# first llama_decode and aborts the :ai process. Use llama.cpp's Jinja/minja path.
old_template = '''    auto formatted = common_chat_format_single(
            g_chat_templates.get(), chat_msgs, new_msg, role == ROLE_USER, /* use_jinja */ false);'''
new_template = '''    auto formatted = common_chat_format_single(
            g_chat_templates.get(), chat_msgs, new_msg, role == ROLE_USER, /* use_jinja */ true);'''
if old_template not in s:
    raise SystemExit('Could not enable Jinja chat template formatting in ai_chat.cpp')
s = s.replace(old_template, new_template, 1)

# Never allow a C++ template exception to unwind across JNI and terminate the
# Android process. Convert it into a normal native error code instead.
old_system = '''    if (has_chat_template) {
        formatted_system_prompt = chat_add_and_format(ROLE_SYSTEM, system_prompt);
    }
    env->ReleaseStringUTFChars(jsystem_prompt, system_prompt);'''
new_system = '''    if (has_chat_template) {
        try {
            formatted_system_prompt = chat_add_and_format(ROLE_SYSTEM, system_prompt);
        } catch (const std::exception &e) {
            LOGe("%s: chat template failed: %s", __func__, e.what());
            env->ReleaseStringUTFChars(jsystem_prompt, system_prompt);
            return 3;
        }
    }
    env->ReleaseStringUTFChars(jsystem_prompt, system_prompt);'''
if old_system not in s:
    raise SystemExit('Could not add system prompt template exception guard')
s = s.replace(old_system, new_system, 1)

old_user = '''    if (has_chat_template) {
        formatted_user_prompt = chat_add_and_format(ROLE_USER, user_prompt);
    }
    env->ReleaseStringUTFChars(juser_prompt, user_prompt);'''
new_user = '''    if (has_chat_template) {
        try {
            formatted_user_prompt = chat_add_and_format(ROLE_USER, user_prompt);
        } catch (const std::exception &e) {
            LOGe("%s: chat template failed: %s", __func__, e.what());
            env->ReleaseStringUTFChars(juser_prompt, user_prompt);
            return 3;
        }
    }
    env->ReleaseStringUTFChars(juser_prompt, user_prompt);'''
if old_user not in s:
    raise SystemExit('Could not add user prompt template exception guard')
s = s.replace(old_user, new_user, 1)

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

# Patch the Android wrapper: keep SAF compatibility and propagate native prompt
# formatting failures as normal Kotlin exceptions instead of silently ending a Flow.
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

old_prompt_error = '''            processUserPrompt(message, predictLength).let { result ->
                if (result != 0) {
                    Log.e(TAG, "Failed to process user prompt: $result")
                    return@flow
                }
            }
'''
new_prompt_error = '''            processUserPrompt(message, predictLength).let { result ->
                if (result != 0) {
                    RuntimeException("Failed to process user prompt: $result").also { error ->
                        Log.e(TAG, error.message, error)
                        _state.value = InferenceEngine.State.Error(error)
                        throw error
                    }
                }
            }
'''
if old_prompt_error not in s:
    raise SystemExit('Could not patch prompt error propagation')
s = s.replace(old_prompt_error, new_prompt_error, 1)
p.write_text(s)
PY

echo "Prepared official llama.cpp Android runtime at $LLAMA_COMMIT (Gemma4 Jinja=on ctx=1024 batch=1 threads=1 flash-attn=off q4-repack=off generic-cpu)"
