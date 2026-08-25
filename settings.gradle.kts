pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "KiraparaNews"
include(":app")

val llamaAndroidDir = file("vendor/llama.cpp/examples/llama.android/lib")
if (!llamaAndroidDir.exists()) {
    throw GradleException("Official llama.cpp Android runtime is not prepared. Run scripts/prepare_llama_android.sh first.")
}
include(":llamaAndroid")
project(":llamaAndroid").projectDir = llamaAndroidDir
