# Proyek Referensi

Salinan repositori ada di `_referensi/` (di-clone dengan `git clone --depth 1`, masuk `.gitignore`, tidak ikut build). Kebijakan pemakaian kode ada di `CLAUDE.md`.

## Lisensi

| Repositori | Pembuat | Lisensi | Konsekuensi |
|---|---|---|---|
| [ervareza/screen-translator](https://github.com/ervareza/screen-translator) | Ervareza Naurian | MIT (file `LICENSE`) | Boleh diadaptasi seperlunya dengan atribusi |
| [SavinduK/SnapCrop](https://github.com/SavinduK/SnapCrop) | SavinduK | MIT menurut `README.md` ("Distributed under the MIT License. See LICENSE for more information."), tetapi **file `LICENSE` tidak disertakan** di repositori | Atas keputusan developer, diperlakukan sebagai MIT: boleh diadaptasi seperlunya dengan atribusi |
| [cvzi/ScreenshotTile](https://github.com/cvzi/ScreenshotTile) | cvzi | GPLv3 (file `LICENSE`) | Jangan salin kode. Keputusan merilis aplikasi sebagai GPLv3 dibahas di awal tahap 2 |
| [EdwardSierra/ScreenshotApp](https://github.com/EdwardSierra/ScreenshotApp) | Edward Sierra | GPLv3 (file `LICENSE` dan header di tiap file) | Sama dengan ScreenshotTile |
| [mtsahakis/MediaProjectionDemo](https://github.com/mtsahakis/MediaProjectionDemo) | mtsahakis | "Do whatever you want License." (satu baris, bukan lisensi standar) | Diperlakukan hati-hati: hanya pelajari pola |

## Tahap 1 — Tombol mengambang

| Repositori | Lisensi | File yang relevan | Yang diambil | Catatan untuk tahap berikutnya |
|---|---|---|---|---|
| screen-translator | MIT | `OverlayManager.kt` (LayoutParams `TYPE_APPLICATION_OVERLAY` + `FLAG_NOT_FOCUSABLE` + `PixelFormat.TRANSLUCENT`, `removeView` dibungkus try/catch); `ScreenCaptureService.kt` (notifikasi ongoing dengan aksi Stop lewat `PendingIntent.getService` + `FLAG_IMMUTABLE`, channel `IMPORTANCE_LOW`); `MainActivity.kt` baris 466-512 (cek `canDrawOverlays`, buka `ACTION_MANAGE_OVERLAY_PERMISSION` dengan URI `package:`, izin `POST_NOTIFICATIONS`) | Pola diadaptasi, tidak ada baris yang disalin utuh. Atribusi ada di KDoc `FloatingButtonService.kt` | Pemicu tangkap layarnya lewat `InactivityAccessibilityService` (jangan diikuti). Tahap 2: `ScreenCaptureService.kt` mendaftarkan `MediaProjection.Callback` sebelum `createVirtualDisplay` dan memakai `FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION`; `captureScreen()` menunjukkan konversi `Image` ke `Bitmap` dengan `rowPadding` |
| SnapCrop | MIT (menurut README, file LICENSE tidak ada) | `TouchOverlayManager.kt` (`attachOverlay`/`detachOverlay` dengan penanda `isOverlayAttached` agar tidak terpasang dua kali, `removeView` di try/finally) | Pola diadaptasi (penjaga "sudah terpasang" dan pelepasan yang aman). Atribusi ada di KDoc `FloatingButtonService.kt` | README menyebut izin "Display over other apps", tetapi kodenya memasang overlay dengan `TYPE_ACCESSIBILITY_OVERLAY` dari `KeyCaptureService` (AccessibilityService), dan manifest tidak mendeklarasikan `SYSTEM_ALERT_WINDOW`. Pendekatan ini tidak diikuti. Tahap 3: `SelectionView.kt` dan `CropOverlayView.kt` bisa dipelajari untuk kotak seleksi |
| ScreenshotTile | GPLv3 | `ScreenshotAccessibilityService.kt` (`windowViewAbsoluteLayoutParams`, `onConfigurationChanged` untuk menata ulang posisi tombol saat rotasi); `utils/AndroidHelpers.kt` (`safeRemoveView`) | Hanya pola (hitung ulang posisi saat orientasi berubah), ditulis sendiri | Tombol mengambangnya bergantung pada AccessibilityService (`TYPE_ACCESSIBILITY_OVERLAY`), jadi tidak diikuti. Tahap 2-3: `BasicForegroundService.kt` dan `AcquireScreenshotPermission.kt` untuk alur izin MediaProjection lintas versi Android |
| ScreenshotApp | GPLv3 | `util/PermissionHelper.kt` (cek dan buka izin overlay) | Hanya pola, ditulis sendiri | Tahap 2-3: `ui/ProjectionRequestActivity.kt` dan `ui/capture/ScreenshotCaptureService.kt` untuk alur minta izin lalu start service bertipe `mediaProjection` |
| MediaProjectionDemo | Tidak standar | Tidak ada yang relevan untuk tahap 1 | Tidak dipakai | Tahap 2: `ScreenCaptureService.java` sebagai dasar konsep `VirtualDisplay` + `ImageReader` (kode lama) |

### Ringkasan

Semua repositori yang punya tombol mengambang (ScreenshotTile, SnapCrop) memasangnya dari AccessibilityService, sedangkan proyek ini memakai `SYSTEM_ALERT_WINDOW` + `TYPE_APPLICATION_OVERLAY` dari foreground service biasa. Implementasi tahap 1 ditulis sendiri berdasarkan dokumentasi Android, memakai pola dari screen-translator dan SnapCrop (MIT, dengan atribusi). Tidak ada kode dari repositori GPLv3 yang disalin.

## Tahap 2 — Tombol bisa digeser dan ambil layar

| Repositori | Lisensi | File yang relevan | Yang diambil | Catatan |
|---|---|---|---|---|
| screen-translator | MIT | `ScreenCaptureService.kt` (`startForeground` bertipe `FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION` sebelum `getMediaProjection`, `registerCallback` sebelum `createVirtualDisplay`, konversi `Image` ke `Bitmap` dengan `rowPadding` di `captureScreen()`); `MainActivity.kt` (hasil `createScreenCaptureIntent` diteruskan ke service lewat extra, penjaga klik ganda); `CHANGELOG.md` dan `release_notes_1.0.6.md` (perbaikan Android 14/15) | Pola diadaptasi, ditulis ulang. Atribusi ada di KDoc `PengambilLayar.kt` dan `FloatingButtonService.kt` | Konversi bitmapnya tidak memotong kolom padding, sehingga bitmap lebih lebar dari layar. Di proyek ini padding dipotong. VirtualDisplay-nya tidak menyesuaikan ukuran saat layar diputar |
| SnapCrop | MIT (menurut README) | `ThreeFingerTouchOverlayView.kt` `handlePillTouchEvent` (simpan `rawY` dan `lp.y` saat `ACTION_DOWN`, anggap geseran setelah melewati `touchSlop`, `coerceIn`, `updateViewLayout`) | Pola diadaptasi, ditulis ulang. Atribusi ada di KDoc `FloatingButtonView.kt` dan `FloatingButtonService.kt` | Batas posisinya memakai margin tetap 24dp. Di proyek ini batasnya memakai tinggi status bar dan navigation bar. Pengambilan layarnya lewat AccessibilityService, jadi tidak diikuti |
| MediaProjectionDemo | Tidak standar | `ScreenCaptureService.java` | Hanya konsep `VirtualDisplay` + `ImageReader` + `OnImageAvailableListener` di thread latar | Saat rotasi, kode ini membuat ulang VirtualDisplay, yang dilarang sejak Android 14. Proyek ini memakai `VirtualDisplay.resize()` + `setSurface()` |
| ScreenshotTile | GPLv3 | `TakeScreenshotActivity.kt` (`createVirtualDisplay`, `stopScreenSharing`), `BasicForegroundService.kt` | Tidak ada kode yang disalin. Hanya dibaca untuk memahami bahwa izin Android 14 berlaku satu kali | Membuat VirtualDisplay baru untuk setiap screenshot, berbeda dari sesi permanen di proyek ini |
| ScreenshotApp | GPLv3 | `capture/ScreenCaptureManager.kt`, `ui/capture/ScreenshotCaptureService.kt` | Tidak ada kode yang disalin. Hanya dibaca untuk memahami masalah frame basi di ImageReader | Sama dengan ScreenshotTile: VirtualDisplay dibuat dan dilepas setiap kali mengambil gambar |

### Ringkasan tahap 2

Sesi rekam layar dibuka sekali saat tombol diaktifkan dan dipertahankan selama tombol aktif. Tidak ada referensi yang memakai pendekatan ini dengan cara yang sama, jadi `PengambilLayar.kt` ditulis sendiri berdasarkan dokumentasi Android, dengan pola dari screen-translator dan SnapCrop (MIT, dengan atribusi). Tidak ada kode dari repositori GPLv3 yang disalin.

## Tahap 3 — Layar pilih area

| Repositori | Lisensi | File yang relevan | Yang diambil | Catatan |
|---|---|---|---|---|
| SnapCrop | MIT (menurut README) | `SelectionView.kt` (enum mode sentuhan: kotak baru, pindah, empat sudut, empat sisi; sudut diperiksa sebelum sisi; batas kotak di dalam view; lapisan gelap di luar seleksi) | Pola diadaptasi, ditulis ulang. Atribusi ada di KDoc `CropSelectionView.kt` | Kotak di SnapCrop digeser secara bertahap per gerakan jari. Di proyek ini posisi dihitung dari posisi awal gestur, dan perhitungannya dipisah ke `GeometriSeleksi.kt` agar bisa diuji. SnapCrop menggambar Bitmap diregangkan ke seluruh view; di proyek ini skalanya seragam dan pemetaan ke piksel Bitmap dihitung eksplisit |
| ScreenshotTile, ScreenshotApp | GPLv3 | Tidak dibaca untuk tahap ini | Tidak ada | |

Ikon panah empat arah di kotak petunjuk (`ic_geser.xml`) digambar ulang dari prototipe proyek sendiri (`docs/prototype`).

Aset pihak ketiga:

| Aset | Sumber | Lisensi |
|---|---|---|
| Bentuk ikon `verified_user` (`app/src/main/res/drawable/ic_verified_user.xml`) | [Material Icons (Google)](https://github.com/google/material-design-icons) | Apache-2.0 |

## Tahap 4 — Kirim potongan ke server dummy

Tidak ada kode yang disalin dari repositori referensi. Klien HTTP, kartu status, dan server ditulis sendiri berdasarkan dokumentasi resmi setiap library. Tahap ini hanya menambah dependensi library, yang semuanya berlisensi permisif. Lisensinya diperiksa dari metadata paket (Python) dan file `LICENSE` di repositori resminya (Android).

### Library Android

| Library | Versi | Lisensi | Dipakai untuk |
|---|---|---|---|
| [OkHttp](https://github.com/square/okhttp) (`com.squareup.okhttp3:okhttp`) | 5.3.2 | Apache-2.0 | Klien HTTP. `Call.cancel()` memutus koneksi saat tombol Batal ditekan. Versi 5.4 ke atas butuh compileSdk 37, jadi dipakai 5.3.2 |
| MockWebServer (`com.squareup.okhttp3:mockwebserver`) | 5.3.2 | Apache-2.0 | Khusus unit test: server HTTP tiruan untuk menguji `KlienApi` |
| [kotlinx.serialization](https://github.com/Kotlin/kotlinx.serialization) (`kotlinx-serialization-json` + plugin Gradle `org.jetbrains.kotlin.plugin.serialization`) | 1.9.0 (plugin mengikuti Kotlin 2.2.10) | Apache-2.0 | Membaca JSON respons server |
| [kotlinx.coroutines](https://github.com/Kotlin/kotlinx.coroutines) (`kotlinx-coroutines-android`) | 1.10.2 | Apache-2.0 | Pengiriman di luar main thread. Sebelumnya sudah ikut tidak langsung lewat lifecycle, sekarang dideklarasikan langsung karena dipakai langsung oleh service |

### Library server (Python, `server/requirements*.txt`)

| Library | Versi | Lisensi | Dipakai untuk |
|---|---|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | 0.141.1 | MIT | Kerangka server |
| [Starlette](https://github.com/encode/starlette) (ikut FastAPI) | 1.6.0 | BSD-3-Clause | Dasar FastAPI |
| [Pydantic](https://github.com/pydantic/pydantic) (ikut FastAPI) | 2.13.5 | MIT | Model data sesuai kontrak |
| [Uvicorn](https://github.com/encode/uvicorn) | 0.53.0 | BSD-3-Clause | Menjalankan server |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.32 | Apache-2.0 | Parser multipart tingkat rendah. Dipakai langsung agar unggahan tetap di memori (`UploadFile` bawaan Starlette menulis unggahan di atas 1 MB ke file sementara) |
| [Pillow](https://github.com/python-pillow/Pillow) | 12.3.0 | MIT-CMU | Memastikan unggahan adalah gambar utuh dan membaca dimensinya, di memori |
| [pytest](https://github.com/pytest-dev/pytest) | 9.1.1 | MIT | Test (khusus pengembangan) |
| [httpx2](https://pypi.org/project/httpx2/) | 2.13.0 | BSD-3-Clause | Dibutuhkan `TestClient` Starlette 1.x (khusus pengembangan) |
