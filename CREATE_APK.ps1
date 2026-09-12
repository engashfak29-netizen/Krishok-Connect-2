Write-Host "Krishok Connect APK তৈরি হচ্ছে... দয়া করে অপেক্ষা করুন।" -ForegroundColor Cyan

$sdkPath = "C:\Users\Ashfakur Rahman\AppData\Local\Android\Sdk"
$env:ANDROID_HOME = $sdkPath
$env:PATH += ";$sdkPath\platform-tools"

cd "C:\Users\Ashfakur Rahman\StudioProjects\Krishok-Connect-2\mobile-app"

# Generate Gradle Wrapper if missing
if (-not (Test-Path "gradlew.bat")) {
    Write-Host "Gradle wrapper তৈরি করা হচ্ছে..."
    gradle wrapper
}

Write-Host "APK বিল্ডিং শুরু হচ্ছে..."
./gradlew assembleDebug

if ($LASTEXITCODE -eq 0) {
    $apkPath = "app\build\outputs\apk\debug"
    Write-Host "`nসফলভাবে APK তৈরি হয়েছে!" -ForegroundColor Green
    Write-Host "লোকেশন: $apkPath"
    explorer $apkPath
} else {
    Write-Host "`nদুঃখিত, বিল্ড ব্যর্থ হয়েছে। অ্যান্ড্রয়েড স্টুডিওতে Gradle Sync হয়েছে কি না চেক করুন।" -ForegroundColor Red
}

Write-Host "`nশেষ করতে যেকোনো কি (key) চাপুন..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
