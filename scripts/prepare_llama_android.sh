#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="$ROOT_DIR/vendor/llama.cpp"
LLAMA_COMMIT="dbadb68eecdfb3ab0e86872d011738fc937f0364"

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
                arguments += "-DGGML_CPU_ALL_VARIANTS=ON"
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
              'constexpr int   DEFAULT_CONTEXT_SIZE    = 4096;')
s = s.replace('constexpr int   BATCH_SIZE              = 512;',
              'constexpr int   BATCH_SIZE              = 256;')
p.write_text(s)
PY

echo "Prepared official llama.cpp Android runtime at $LLAMA_COMMIT"
