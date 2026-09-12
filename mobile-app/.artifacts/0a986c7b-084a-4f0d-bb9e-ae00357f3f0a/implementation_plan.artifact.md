# Fix Build Error: Cannot mutate dependencies after resolution

The project is currently failing to build with the error `Cannot mutate the dependencies of configuration ':app:debugCompileClasspath' after the configuration was resolved`. This is caused by an incompatibility between **Android Gradle Plugin (AGP) 8.2.2** and **Gradle 9.3.0**.

AGP 8.2.2 expects a Gradle 8.x environment. Gradle 9.x introduced stricter immutability for configurations once they are resolved, which conflicts with how AGP 8.2.2 manages dependency constraints.

## Proposed Changes

### Build Configuration

#### [MODIFY] [gradle-wrapper.properties](file:///C:/Users/Ashfakur Rahman/StudioProjects/Krishok-Connect-2/mobile-app/gradle/wrapper/gradle-wrapper.properties)
- Downgrade Gradle from `9.3.0` to `8.7`. This version is fully compatible with AGP 8.2.2 and is the latest stable release in the 8.x branch.

#### [MODIFY] [gradle.properties](file:///C:/Users/Ashfakur Rahman/StudioProjects/Krishok-Connect-2/mobile-app/gradle.properties)
- Add `android.dependency.useConstraints=false` as a secondary measure if the Gradle downgrade alone isn't sufficient, or to improve build performance by disabling AGP's legacy constraint handler which is the source of the mutation error.

## Verification Plan

### Automated Tests
- Run `./gradlew clean assembleDebug` to verify the build completes successfully.

### Manual Verification
- Sync the project in Android Studio to ensure the IDE correctly recognizes the new Gradle version.
