@echo off
setlocal

echo Krishok Connect APK Build Started...
echo Checking for Java...

:: Try to find Java from Android Studio's default paths
set "STUDIO_JAVA=C:\Program Files\Android\Android Studio\jbr\bin\java.exe"
if not exist "%STUDIO_JAVA%" set "STUDIO_JAVA=C:\Program Files\Android\Android Studio\jre\bin\java.exe"
if not exist "%STUDIO_JAVA%" set "STUDIO_JAVA=C:\Program Files\Android\Android Studio 1\jbr\bin\java.exe"

if exist "%STUDIO_JAVA%" (
    echo Using Android Studio Java: %STUDIO_JAVA%
    set "JAVA_HOME=%STUDIO_JAVA:\bin\java.exe=%"
) else (
    echo Java not found in default Android Studio paths.
    echo Please make sure Android Studio is installed at C:\Program Files\Android\Android Studio
)

:: Run Gradle Build
call gradlew.bat assembleDebug

if %ERRORLEVEL% EQU 0 (
    echo.
    echo BUILD SUCCESSFUL!
    echo Opening APK folder...
    start "" "app\build\outputs\apk\debug"
) else (
    echo.
    echo BUILD FAILED!
    echo Please check the errors above.
    pause
)
