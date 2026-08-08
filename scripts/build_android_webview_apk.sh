#!/usr/bin/env bash
# Build a signed Android WebView APK for NAJJAR (sideload).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/scripts/najjar_app_url.sh"

APP_DIR="$ROOT/mobile/android-webview"
OUT_DIR="$ROOT/public/releases/android"
SDK_ROOT="${ANDROID_SDK_ROOT:-$ROOT/tools/android/sdk}"
CMDLINE_ZIP="$ROOT/tools/android/cmdline-tools.zip"
APP_URL="$NAJJAR_APP_URL"
APP_ID="com.najjar.trading"
APP_NAME="NAJJAR Trading"
VERSION_NAME="${LQ_APP_VERSION:-70.5.0}"
VERSION_CODE="${LQ_APP_VERSION_CODE:-7050}"

mkdir -p "$SDK_ROOT" "$OUT_DIR" "$APP_DIR" "$ROOT/tools/android"

export ANDROID_HOME="$SDK_ROOT"
export ANDROID_SDK_ROOT="$SDK_ROOT"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$SDK_ROOT/cmdline-tools/latest/bin:$SDK_ROOT/platform-tools:$SDK_ROOT/build-tools/34.0.0:$PATH"

install_sdk() {
  if [[ -x "$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" ]]; then
    return 0
  fi
  echo "==> Downloading Android cmdline-tools"
  curl -fsSL -o "$CMDLINE_ZIP" \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  rm -rf "$SDK_ROOT/cmdline-tools"
  mkdir -p "$SDK_ROOT/cmdline-tools"
  unzip -q "$CMDLINE_ZIP" -d "$SDK_ROOT/cmdline-tools"
  # Google zip extracts to cmdline-tools/cmdline-tools — rename to latest
  if [[ -d "$SDK_ROOT/cmdline-tools/cmdline-tools" ]]; then
    mv "$SDK_ROOT/cmdline-tools/cmdline-tools" "$SDK_ROOT/cmdline-tools/latest"
  fi
  yes | sdkmanager --sdk_root="$SDK_ROOT" --licenses >/tmp/android-licenses.log 2>&1 || true
  sdkmanager --sdk_root="$SDK_ROOT" \
    "platform-tools" \
    "platforms;android-34" \
    "build-tools;34.0.0"
}

write_project() {
  echo "==> Writing Android WebView project"
  rm -rf "$APP_DIR"
  mkdir -p \
    "$APP_DIR/app/src/main/java/com/najjar/trading" \
    "$APP_DIR/app/src/main/res/layout" \
    "$APP_DIR/app/src/main/res/values" \
    "$APP_DIR/app/src/main/res/xml" \
    "$APP_DIR/gradle/wrapper"

  cat > "$APP_DIR/settings.gradle" <<'EOF'
pluginManagement {
  repositories {
    google()
    mavenCentral()
    gradlePluginPortal()
  }
}
dependencyResolutionManagement {
  repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
  repositories {
    google()
    mavenCentral()
  }
}
rootProject.name = "NajjarTrading"
include(":app")
EOF

  cat > "$APP_DIR/build.gradle" <<'EOF'
plugins {
  id 'com.android.application' version '8.2.2' apply false
}
EOF

  cat > "$APP_DIR/gradle.properties" <<'EOF'
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.nonTransitiveRClass=true
EOF

  cat > "$APP_DIR/app/build.gradle" <<EOF
plugins {
  id 'com.android.application'
}
android {
  namespace '$APP_ID'
  compileSdk 34
  defaultConfig {
    applicationId '$APP_ID'
    minSdk 24
    targetSdk 34
    versionCode $VERSION_CODE
    versionName '$VERSION_NAME'
    buildConfigField "String", "APP_URL", "\"${APP_URL}\""
  }
  buildFeatures { buildConfig true }
  signingConfigs {
    release {
      storeFile file("${ROOT}/tools/android/launchquality-release.jks")
      storePassword 'launchquality'
      keyAlias 'launchquality'
      keyPassword 'launchquality'
    }
  }
  buildTypes {
    release {
      minifyEnabled false
      signingConfig signingConfigs.release
    }
    debug {
      signingConfig signingConfigs.release
    }
  }
  compileOptions {
    sourceCompatibility JavaVersion.VERSION_17
    targetCompatibility JavaVersion.VERSION_17
  }
}
dependencies {
  implementation 'androidx.appcompat:appcompat:1.6.1'
  implementation 'com.google.android.material:material:1.11.0'
}
EOF

  cat > "$APP_DIR/app/src/main/AndroidManifest.xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
  <uses-permission android:name="android.permission.INTERNET" />
  <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
  <application
      android:allowBackup="true"
      android:icon="@android:drawable/sym_def_app_icon"
      android:label="@string/app_name"
      android:networkSecurityConfig="@xml/network_security_config"
      android:supportsRtl="true"
      android:theme="@style/Theme.NajjarTrading"
      android:usesCleartextTraffic="false">
    <activity
        android:name=".MainActivity"
        android:exported="true"
        android:configChanges="orientation|screenSize|keyboardHidden"
        android:windowSoftInputMode="adjustResize">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
    </activity>
  </application>
</manifest>
EOF

  cat > "$APP_DIR/app/src/main/res/values/strings.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<resources>
  <string name="app_name">$APP_NAME</string>
</resources>
EOF

  cat > "$APP_DIR/app/src/main/res/values/themes.xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<resources>
  <style name="Theme.NajjarTrading" parent="Theme.MaterialComponents.DayNight.NoActionBar">
    <item name="android:statusBarColor">#06111F</item>
    <item name="android:navigationBarColor">#06111F</item>
    <item name="android:windowBackground">#06111F</item>
  </style>
</resources>
EOF

  cat > "$APP_DIR/app/src/main/res/layout/activity_main.xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="#06111F">
  <WebView
      android:id="@+id/webview"
      android:layout_width="match_parent"
      android:layout_height="match_parent" />
  <ProgressBar
      android:id="@+id/progress"
      style="?android:attr/progressBarStyleHorizontal"
      android:layout_width="match_parent"
      android:layout_height="3dp"
      android:layout_gravity="top"
      android:indeterminate="true"
      android:visibility="gone" />
</FrameLayout>
EOF

  cat > "$APP_DIR/app/src/main/res/xml/network_security_config.xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="false">
    <trust-anchors>
      <certificates src="system" />
    </trust-anchors>
  </base-config>
</network-security-config>
EOF

  cat > "$APP_DIR/app/src/main/java/com/najjar/trading/MainActivity.java" <<EOF
package com.najjar.trading;

import android.annotation.SuppressLint;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
  private WebView webView;
  private ProgressBar progress;

  @SuppressLint("SetJavaScriptEnabled")
  @Override
  protected void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);
    setContentView(R.layout.activity_main);
    webView = findViewById(R.id.webview);
    progress = findViewById(R.id.progress);

    CookieManager.getInstance().setAcceptCookie(true);
    CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);

    WebSettings settings = webView.getSettings();
    settings.setJavaScriptEnabled(true);
    settings.setDomStorageEnabled(true);
    settings.setDatabaseEnabled(true);
    settings.setLoadWithOverviewMode(true);
    settings.setUseWideViewPort(true);
    settings.setSupportZoom(false);
    settings.setBuiltInZoomControls(false);
    settings.setDisplayZoomControls(false);
    settings.setMediaPlaybackRequiresUserGesture(false);
    settings.setAllowFileAccess(false);
    settings.setAllowContentAccess(true);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
    settings.setUserAgentString(settings.getUserAgentString() + " NajjarTrading/${VERSION_NAME}");

    webView.setWebChromeClient(new WebChromeClient());
    webView.setWebViewClient(new WebViewClient() {
      @Override
      public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
        return false;
      }

      @Override
      public void onPageStarted(WebView view, String url, Bitmap favicon) {
        progress.setVisibility(View.VISIBLE);
      }

      @Override
      public void onPageFinished(WebView view, String url) {
        progress.setVisibility(View.GONE);
      }
    });

    webView.loadUrl(BuildConfig.APP_URL);
  }

  @Override
  public void onBackPressed() {
    if (webView != null && webView.canGoBack()) {
      webView.goBack();
    } else {
      super.onBackPressed();
    }
  }
}
EOF

  # Gradle wrapper properties + jar bootstrap via gradle if available, else download wrapper
  cat > "$APP_DIR/gradle/wrapper/gradle-wrapper.properties" <<'EOF'
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.2-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
EOF
}

ensure_keystore() {
  local ks="$ROOT/tools/android/launchquality-release.jks"
  if [[ -f "$ks" ]]; then
    return 0
  fi
  keytool -genkeypair -v \
    -keystore "$ks" \
    -alias launchquality \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass launchquality -keypass launchquality \
    -dname "CN=Launch Quality LLC, OU=Mobile, O=Launch Quality, L=Nizwa, ST=Ad Dakhiliyah, C=OM"
}

ensure_gradle_wrapper() {
  if [[ -x "$APP_DIR/gradlew" ]]; then
    return 0
  fi
  # Use temporary gradle to generate wrapper
  if ! command -v gradle >/dev/null 2>&1; then
    echo "==> Installing Gradle via SDKMAN-less bootstrap"
    local gver=8.2
    local gzip="$ROOT/tools/android/gradle-${gver}-bin.zip"
    curl -fsSL -o "$gzip" "https://services.gradle.org/distributions/gradle-${gver}-bin.zip"
    rm -rf "$ROOT/tools/android/gradle-${gver}"
    unzip -q "$gzip" -d "$ROOT/tools/android"
    export PATH="$ROOT/tools/android/gradle-${gver}/bin:$PATH"
  fi
  (
    cd "$APP_DIR"
    gradle wrapper --gradle-version 8.2
  )
}

build_apk() {
  echo "==> Building release APK"
  (
    cd "$APP_DIR"
    ./gradlew --no-daemon assembleRelease
  )
  local built="$APP_DIR/app/build/outputs/apk/release/app-release.apk"
  if [[ ! -f "$built" ]]; then
    echo "APK not found at $built" >&2
    exit 1
  fi
  cp "$built" "$OUT_DIR/NAJJAR-Trading.apk"
  cp "$built" "$OUT_DIR/NAJJAR-Trading-v${VERSION_NAME}.apk"
  ls -la "$OUT_DIR/NAJJAR-Trading.apk"
  echo "OK: $OUT_DIR/NAJJAR-Trading.apk"
}

install_sdk
write_project
ensure_keystore
ensure_gradle_wrapper
build_apk
