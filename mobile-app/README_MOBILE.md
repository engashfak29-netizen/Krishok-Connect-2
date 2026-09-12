# Krishok Connect Mobile App

This is the Android version of the Krishok Connect PWA, wrapped in a native WebView.

## How to Build and Run

1.  **Open in Android Studio**:
    *   Open Android Studio and select **Open**.
    *   Navigate to the `mobile-app` folder in this repository.
2.  **Sync Gradle**:
    *   Android Studio will automatically sync Gradle. Wait for it to finish.
3.  **Set Backend IP**:
    *   The app connects to the backend. If you are testing locally, ensure the backend is running.
    *   Update the `KC_API_BASE` in the web assets if necessary, or ensure the backend is accessible at the expected IP.
    *   Currently, the app loads `file:///android_asset/www/index.html`.
4.  **Run on Device/Emulator**:
    *   Connect an Android device or start an emulator.
    *   Click the **Run** button in Android Studio.

## Features
- **Native WebView**: Fast and responsive UI.
- **Full Access**: Access to camera and gallery for posting.
- **PWA Integration**: Uses existing HTML/JS/CSS assets.

## Project Structure
- `app/src/main/assets/www/`: Bundled frontend code.
- `app/src/main/java/com/krishokconnect/MainActivity.kt`: Native logic for WebView and file choosing.
- `app/src/main/AndroidManifest.xml`: Permissions and app configuration.
