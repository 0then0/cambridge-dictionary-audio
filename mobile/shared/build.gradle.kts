plugins {
    kotlin("multiplatform")
    kotlin("plugin.serialization")
    id("com.android.kotlin.multiplatform.library")
}

kotlin {
    android {
        namespace = "org.cambridgeaudio.core"
        compileSdk = 37
        minSdk = 28
    }
    jvm()
    if (
        providers.gradleProperty("enableAppleTargets").orNull == "true" ||
            (System.getProperty("os.name") == "Mac OS X" &&
                file("/Applications/Xcode.app").exists())
    ) {
        listOf(iosArm64(), iosSimulatorArm64(), iosX64()).forEach { target ->
            target.binaries.framework {
                baseName = "CambridgeCore"
                isStatic = true
            }
        }
    }
    sourceSets {
        commonMain.dependencies {
            implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.10.0")
            implementation("com.fleeksoft.ksoup:ksoup:0.2.6")
            implementation("com.squareup.okio:okio:3.16.4")
        }
        getByName("androidMain").kotlin.srcDir("src/jvmCommon/kotlin")
        getByName("jvmMain").kotlin.srcDir("src/jvmCommon/kotlin")
        commonTest.dependencies { implementation(kotlin("test")) }
        getByName("jvmTest").dependencies { implementation("org.xerial:sqlite-jdbc:3.51.2.0") }
        getByName("jvmTest").resources.srcDir("../../contracts")
    }
}
