# 📱 NutriScan · Android APK Project & Build Guide

This directory contains the complete, standalone native Android APK project for **NutriScan · NY**.

---

## 🚀 Features in Android App
- ⚡ **Real-Time Barcode & 1D Line Code Scanner**: High-speed camera scan with automatic Open Food Facts lookup.
- 📷 **Label OCR Scanner**: High-resolution camera capture for unlisted or custom ingredient lists.
- 🛡️ **Instant AI Safety Analysis**: Health Grades (A/B/C/D), Additive and E-number warnings, and Allergen alerts.
- 💎 **Ultra-Modern Glassmorphic Dark UI**: High-framerate fluid animations, luxury emerald/cyan theme.

---

## 🛠️ How to Build the APK (2 Simple Ways)

### Option 1: Using Android Studio (Easiest)
1. Open **Android Studio**.
2. Click **Open** and select the folder: `d:\My_Projects\Nutriscan\android_app`.
3. Wait a few seconds for Gradle to sync.
4. Click menu **Build** ➔ **Build Bundle(s) / APK(s)** ➔ **Build APK(s)**.
5. Android Studio will generate the installable `app-debug.apk` file!
6. Click **locate** and transfer `app-debug.apk` to any Android phone to install!

---

### Option 2: Using Command Line (Gradle)
From the `android_app` directory, run:
```bash
./gradlew assembleDebug
```
The compiled APK will be at:
`android_app/app/build/outputs/apk/debug/app-debug.apk`

---

### 🌐 Setting your Server URL
In `MainActivity.java`, update `DEFAULT_URL` to your production URL (or local WiFi IP like `http://192.168.1.X:8501`) so the mobile app can connect seamlessly:
```java
private static final String DEFAULT_URL = "http://YOUR_SERVER_IP:8501";
```
