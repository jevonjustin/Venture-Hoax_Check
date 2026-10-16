package com.example.cekhoaks

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.view.Gravity
import android.view.KeyEvent
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.window.OnBackInvokedCallback
import android.window.OnBackInvokedDispatcher
import androidx.annotation.RequiresApi

/**
 * Akar tampilan sebuah jendela overlay layar penuh; menerjemahkan tombol Back menjadi [onKembali].
 * Dipakai layar pilih area dan semua lembar hasil.
 */
@SuppressLint("ViewConstructor")
internal open class AkarOverlay(context: Context, private val onKembali: () -> Unit) : FrameLayout(context) {

    // Bertipe Any agar kelas OnBackInvokedCallback (Android 13+) tidak dimuat di versi lama.
    private var callbackKembali: Any? = null

    // Android 12 ke bawah (dan 13+ yang belum memakai "predictive back") mengirim Back
    // sebagai KeyEvent biasa.
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode == KeyEvent.KEYCODE_BACK) {
            if (event.action == KeyEvent.ACTION_UP && !event.isCanceled) onKembali()
            return true
        }
        return super.dispatchKeyEvent(event)
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) daftarkanKembali()
    }

    override fun onDetachedFromWindow() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) lepaskanKembali()
        super.onDetachedFromWindow()
    }

    // Aplikasi dengan targetSdk 36 di Android 16 tidak lagi menerima Back sebagai KeyEvent,
    // melainkan lewat OnBackInvokedCallback yang didaftarkan ke jendela.
    @RequiresApi(Build.VERSION_CODES.TIRAMISU)
    private fun daftarkanKembali() {
        val callback = OnBackInvokedCallback { onKembali() }
        findOnBackInvokedDispatcher()?.registerOnBackInvokedCallback(
            OnBackInvokedDispatcher.PRIORITY_DEFAULT,
            callback,
        )
        callbackKembali = callback
    }

    @RequiresApi(Build.VERSION_CODES.TIRAMISU)
    private fun lepaskanKembali() {
        val callback = callbackKembali as? OnBackInvokedCallback ?: return
        findOnBackInvokedDispatcher()?.unregisterOnBackInvokedCallback(callback)
        callbackKembali = null
    }
}

/**
 * Parameter jendela overlay yang menutupi seluruh layar fisik dan bisa menerima fokus.
 *
 * LAYOUT_IN_SCREEN + LAYOUT_NO_LIMITS: jendela menutupi seluruh layar fisik, termasuk di bawah
 * status bar dan navigation bar. Tanpa FLAG_NOT_FOCUSABLE, jendela ini menerima fokus sehingga
 * tombol Back sampai ke sini. Fokus kembali ke aplikasi di bawahnya begitu jendela dilepas.
 */
internal fun buatParamsLayarPenuh(): WindowManager.LayoutParams =
    WindowManager.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
            WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
        PixelFormat.TRANSLUCENT,
    ).apply {
        gravity = Gravity.TOP or Gravity.START
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            // Izinkan jendela menutupi area cutout (poni kamera). Mode ALWAYS baru ada di Android 11.
            layoutInDisplayCutoutMode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            } else {
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // Sejak Android 11, jendela otomatis dijauhkan dari status bar dan navigation bar.
            // Nilai 0 mematikan perilaku itu agar jendela benar-benar selebar layar fisik.
            fitInsetsTypes = 0
        }
    }
