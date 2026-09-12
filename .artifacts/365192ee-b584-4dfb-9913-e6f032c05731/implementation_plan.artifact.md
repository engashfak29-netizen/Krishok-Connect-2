# Implementation Plan: Mobile App for Krishok Connect

This plan outlines the steps to create a native Android wrapper (WebView-based) for the existing Krishok Connect PWA. This will allow the platform to be installed as a standalone `.apk` on Android devices, providing a more integrated mobile experience.

## User Review Required

> [!IMPORTANT]
> **API Connectivity**: For the mobile app to communicate with the backend, the backend must be accessible over the network (not just `localhost`). You will need to host the backend or use your computer's IP address (e.g., `http://192.168.x.x:8000`) in the app configuration.

> [!NOTE]
> The app will bundle the HTML/JS/CSS files in its assets to ensure it works fast and offline, but it will still call the backend API for live data.

## Proposed Changes

We will create a new Android project structure within the repository.

### [NEW] Android Module

#### [NEW] [build.gradle](file:///C:/Users/Ashfakur%20Rahman/StudioProjects/Krishok-Connect-2/android/app/build.gradle)
- Basic Android configuration.
- Dependencies: `androidx.appcompat`, `androidx.webkit`, `androidx.activity-ktx`.

#### [NEW] [AndroidManifest.xml](file:///C:/Users/Ashfakur%20Rahman/StudioProjects/Krishok-Connect-2/android/app/src/main/AndroidManifest.xml)
- Internet and Camera permissions.
- Main activity declaration.
- `usesCleartextTraffic` enabled for local development.

#### [NEW] [MainActivity.kt](file:///C:/Users/Ashfakur%20Rahman/StudioProjects/Krishok-Connect-2/android/app/src/main/java/com/krishokconnect/MainActivity.kt)
- `WebView` setup with JavaScript and DOM storage.
- `WebViewClient` to keep navigation inside the app.
- `WebChromeClient` for file uploads (camera/gallery).
- Handle the Android Back button to navigate back in the WebView history.

### [Assets] Resource Bundling

#### [COPY] Web files to Assets
- All files from `web/` will be copied to `android/app/src/main/assets/www/`.

## Verification Plan

### Manual Verification
1.  **Build**: Run `./gradlew assembleDebug` (if Gradle is available).
2.  **Install**: Install the generated `.apk` on an emulator or physical device.
3.  **App Launch**: Verify that the app opens to the `index.html` home feed.
4.  **Navigation**: Test bottom navigation and action sheets.
5.  **Connectivity**: Log in and check if it pulls data from the backend.
6.  **Media Upload**: Try creating a post with a picture to verify camera/gallery access.
