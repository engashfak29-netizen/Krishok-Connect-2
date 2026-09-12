@echo off
setlocal
chcp 65001 > nul

echo ======================================================
echo       Krishok Connect APK তৈরি হচ্ছে (১-ক্লিক সমাধান)
echo ======================================================
echo.

:: Set Android SDK Path
set "ANDROID_HOME=C:\Users\Ashfakur Rahman\AppData\Local\Android\Sdk"
set "SDK_DIR=C:\Users\Ashfakur Rahman\AppData\Local\Android\Sdk"

:: Manually point to Android Studio's Java
set "JAVA_HOME=C:\Program Files\Android\Android Studio1\jbr"
set "PATH=%JAVA_HOME%\bin;%PATH%"

echo Java পাথ সেট করা হয়েছে: %JAVA_HOME%

:: Go to mobile-app directory
cd /d "%~dp0mobile-app"

:: Ensure local.properties is correct
echo sdk.dir=C\:\\Users\\Ashfakur Rahman\\AppData\\Local\\Android\\Sdk > local.properties

echo.
echo APK বিল্ডিং শুরু হচ্ছে... দয়া করে ৩-৫ মিনিট অপেক্ষা করুন।
echo উইন্ডোটি বন্ধ করবেন না।
echo.

:: Run Gradle Build using the wrapper
call gradlew.bat assembleDebug --stacktrace

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ======================================================
    echo       সফলভাবে APK তৈরি হয়েছে! (BUILD SUCCESSFUL)
    echo ======================================================
    echo.
    echo এখন APK ফোল্ডারটি ওপেন হচ্ছে...
    start "" "app\build\outputs\apk\debug"
    echo.
    echo app-debug.apk ফাইলটি আপনার ফোনের Download ফোল্ডারে নিয়ে ইনস্টল করুন।
) else (
    echo.
    echo [ERROR] অ্যাপ তৈরি করতে সমস্যা হয়েছে।
    echo উপরে লাল রঙের এরর মেসেজগুলো পড়ুন।
)

echo.
echo এই উইন্ডোটি বন্ধ করতে যে কোনো কি (key) চাপুন...
pause > nul
