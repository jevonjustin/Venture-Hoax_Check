import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// Kunci tanda tangan rilis disimpan di luar repo. Isinya tidak pernah dicetak.
// Bila berkas ini belum ada, build release tetap jalan, tetapi APK-nya tidak bertanda tangan.
val berkasKunciRilis = file("C:/Users/User/kunci_android/veritas-rilis.properties")
val kunciRilis: Properties? = berkasKunciRilis.takeIf { it.isFile }?.let { berkas ->
    Properties().apply { berkas.inputStream().use { load(it) } }
}
val kunciRilisLengkap = kunciRilis != null &&
    listOf("storeFile", "storePassword", "keyAlias", "keyPassword").all { !kunciRilis.getProperty(it).isNullOrBlank() }
if (!kunciRilisLengkap) {
    logger.warn(
        "PERINGATAN: ${berkasKunciRilis.path} tidak ada atau belum lengkap " +
            "(storeFile, storePassword, keyAlias, keyPassword). APK release dibangun TANPA tanda tangan.",
    )
}

android {
    namespace = "com.example.cekhoaks"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.example.cekhoaks"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (kunciRilisLengkap) {
            create("rilis") {
                storeFile = file(kunciRilis!!.getProperty("storeFile"))
                storePassword = kunciRilis.getProperty("storePassword")
                keyAlias = kunciRilis.getProperty("keyAlias")
                keyPassword = kunciRilis.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            optimization {
                enable = false
            }
            if (kunciRilisLengkap) signingConfig = signingConfigs.getByName("rilis")
            // Alamat server showcase (ngrok) dipakai bila belum ada alamat tersimpan.
            buildConfigField("boolean", "PAKAI_URL_SHOWCASE", "true")
        }
        debug {
            // Paket berbeda supaya debug dan release bisa terpasang berdampingan di satu HP.
            // Nama "Veritas (debug)" ada di src/debug/res/values/strings_debug.xml.
            applicationIdSuffix = ".debug"
            buildConfigField("boolean", "PAKAI_URL_SHOWCASE", "false")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

// Salinan APK release dengan nama yang mudah dikenali: app/build/outputs/veritas/veritas-<versi>.apk.
val versiRilis: String = android.defaultConfig.versionName.orEmpty()
val salinApkRilis = tasks.register<Sync>("salinApkRilis") {
    // Disalin ke variabel lokal: configuration cache menolak lambda yang merujuk objek skrip.
    val versi = versiRilis
    val bertandaTangan = kunciRilisLengkap
    from(layout.buildDirectory.dir("outputs/apk/release")) { include("*.apk") }
    into(layout.buildDirectory.dir("outputs/veritas"))
    rename { nama -> if ("unsigned" in nama) "veritas-$versi-tanpa-tanda-tangan.apk" else "veritas-$versi.apk" }
    doLast {
        if (!bertandaTangan) {
            logger.warn("PERINGATAN: APK release TIDAK bertanda tangan dan tidak bisa dipasang. Isi berkas kunci rilis dulu.")
        }
    }
}
tasks.matching { it.name == "assembleRelease" }.configureEach { finalizedBy(salinApkRilis) }

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.okhttp)
    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}