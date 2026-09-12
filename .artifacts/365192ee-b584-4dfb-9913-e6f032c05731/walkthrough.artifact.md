# Walkthrough: Krishok Connect Mobile App

আমি কৃষকদের জন্য Krishok Connect-এর একটি পূর্ণাঙ্গ Android মোবাইল অ্যাপ (WebView-based) তৈরি করেছি। এটি আপনার বর্তমান PWA ফিচারের সাথে Native Android সুবিধা যুক্ত করবে।

## কী কী পরিবর্তন করা হয়েছে:

### ১. Android Project Structure
`mobile-app/` নামে একটি নতুন ডিরেক্টরি তৈরি করা হয়েছে যার মধ্যে সম্পূর্ণ Android প্রোজেক্ট রয়েছে। এতে আধুনিক `Gradle 8.2` এবং `Kotlin 1.9` ব্যবহার করা হয়েছে।

### ২. WebView Wrapper
[MainActivity.kt](file:///C:/Users/Ashfakur%20Rahman/StudioProjects/Krishok-Connect-2/mobile-app/app/src/main/java/com/krishokconnect/MainActivity.kt) ফাইলে Native WebView লজিক যোগ করা হয়েছে:
- **Fast Loading**: অ্যাপের ভেতরের assets থেকে ফাইল লোড হয়।
- **Native Navigation**: ফোনের Back button দিয়ে অ্যাপের ভেতরে নেভিগেট করা যাবে।
- **File Upload Support**: পোস্টে ছবি বা ভিডিও আপলোড করার জন্য গ্যালারি এবং ক্যামেরা ব্যবহারের সুবিধা দেওয়া হয়েছে।

### ৩. Permissions & Security
[AndroidManifest.xml](file:///C:/Users/Ashfakur%20Rahman/StudioProjects/Krishok-Connect-2/mobile-app/app/src/main/AndroidManifest.xml) ফাইলে প্রয়োজনীয় পারমিশন যোগ করা হয়েছে:
- `INTERNET`: ডাটা লোড করার জন্য।
- `CAMERA`: ছবি তোলার জন্য।
- `READ/WRITE STORAGE`: ফাইল আপলোড করার জন্য।

### ৪. Assets Bundling
আপনার `web/` ফোল্ডারের সব ফাইল (HTML, CSS, JS, Icons) অ্যাপের `assets/www/` ফোল্ডারে কপি করা হয়েছে। এতে ইন্টারনেট ছাড়াও অ্যাপের বেসিক UI দ্রুত লোড হবে।

## কিভাবে চালাবেন?

১. **Android Studio** ওপেন করে `mobile-app` ফোল্ডারটি সিলেক্ট করুন।
২. Gradle Sync শেষ হলে আপনার ফোন বা ইমুলেটরে **Run** বাটনে ক্লিক করুন।
৩. বিস্তারিত নির্দেশনার জন্য [README_MOBILE.md](file:///C:/Users/Ashfakur%20Rahman/StudioProjects/Krishok-Connect-2/mobile-app/README_MOBILE.md) দেখুন।

> [!TIP]
> অ্যাপটি ডেভেলপমেন্ট মোডে থাকাকালীন `usesCleartextTraffic="true"` এনাবল করা আছে যাতে আপনি লোকাল IP (`http://192.168.x.x:8000`) দিয়ে ব্যাকএন্ডের সাথে টেস্ট করতে পারেন।
