package com.example.nutriscan

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {

    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null
    private var webViewRef: WebView? = null

    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (fileUploadCallback != null) {
            val results: Array<Uri>? = if (result.resultCode == Activity.RESULT_OK && result.data != null) {
                val dataUri = result.data?.data
                val clipData = result.data?.clipData
                if (clipData != null) {
                    Array(clipData.itemCount) { i -> clipData.getItemAt(i).uri }
                } else if (dataUri != null) {
                    arrayOf(dataUri)
                } else null
            } else null
            fileUploadCallback?.onReceiveValue(results)
            fileUploadCallback = null
        }
    }

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val cameraGranted = permissions[Manifest.permission.CAMERA] ?: false
        if (cameraGranted) {
            webViewRef?.post {
                webViewRef?.evaluateJavascript("if (window.onCameraPermissionGranted) window.onCameraPermissionGranted();", null)
            }
        } else {
            Toast.makeText(this, "Camera permission is needed for scanning barcodes and labels.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Handle back press within WebView
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webViewRef != null) {
                    webViewRef?.evaluateJavascript(
                        "(function() { if (window.handleAppBack) { return window.handleAppBack(); } return false; })()"
                    ) { result ->
                        if (result == "true" || result == "\"true\"") {
                            // Handled inside webview
                        } else if (webViewRef?.canGoBack() == true) {
                            webViewRef?.goBack()
                        } else {
                            isEnabled = false
                            onBackPressedDispatcher.onBackPressed()
                        }
                    }
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        // Request camera permission on launch
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissionLauncher.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.VIBRATE))
        }

        setContent {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0xFF06090E))
                    .statusBarsPadding()
            ) {
                NutriScanWebView(
                    onWebViewCreated = { webViewRef = it },
                    onOpenFileChooser = { callback, intent ->
                        fileUploadCallback = callback
                        try {
                            fileChooserLauncher.launch(intent)
                        } catch (e: Exception) {
                            fileUploadCallback = null
                            Toast.makeText(this@MainActivity, "Cannot open file picker", Toast.LENGTH_SHORT).show()
                        }
                    }
                )
            }
        }
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun NutriScanWebView(
    onWebViewCreated: (WebView) -> Unit,
    onOpenFileChooser: (ValueCallback<Array<Uri>>, Intent) -> Unit
) {
    val context = LocalContext.current
    val targetUrl = "file:///android_asset/www/index.html"

    val webView = remember {
        WebView(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(android.graphics.Color.parseColor("#06090E"))

            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                databaseEnabled = true
                mediaPlaybackRequiresUserGesture = false
                allowFileAccess = true
                allowContentAccess = true
                allowFileAccessFromFileURLs = true
                allowUniversalAccessFromFileURLs = true
                loadWithOverviewMode = true
                useWideViewPort = true
                builtInZoomControls = false
                displayZoomControls = false
                cacheMode = WebSettings.LOAD_DEFAULT
                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            }

            setLayerType(View.LAYER_TYPE_HARDWARE, null)

            (context as? Activity)?.let { act ->
                addJavascriptInterface(AndroidBridge(act), "AndroidBridge")
            }

            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    return false
                }
            }

            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: PermissionRequest?) {
                    (context as? Activity)?.runOnUiThread {
                        request?.grant(request.resources)
                    }
                }

                override fun onShowFileChooser(
                    webView: WebView?,
                    filePathCallback: ValueCallback<Array<Uri>>?,
                    fileChooserParams: FileChooserParams?
                ): Boolean {
                    if (filePathCallback != null && fileChooserParams != null) {
                        onOpenFileChooser(filePathCallback, fileChooserParams.createIntent())
                        return true
                    }
                    return false
                }
            }

            onWebViewCreated(this)
            loadUrl(targetUrl)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            webView.destroy()
        }
    }

    AndroidView(
        factory = { webView },
        modifier = Modifier.fillMaxSize()
    )
}

class AndroidBridge(private val activity: Activity) {
    @android.webkit.JavascriptInterface
    fun vibrateHaptic(type: String?) {
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = activity.getSystemService(android.content.Context.VIBRATOR_MANAGER_SERVICE) as? android.os.VibratorManager
                vibratorManager?.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                activity.getSystemService(android.content.Context.VIBRATOR_SERVICE) as? android.os.Vibrator
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator?.vibrate(android.os.VibrationEffect.createOneShot(40, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator?.vibrate(40)
            }
        } catch (_: Exception) {}
    }
}



