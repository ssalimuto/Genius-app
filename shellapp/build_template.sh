#!/usr/bin/env bash
# Builds the WebView shell app and writes it, unsigned, as apk_template.bin.
#   usage: shellapp/build_template.sh OUT_PATH
# Needs a JDK (javac) and the Android SDK (build-tools with aapt2 + d8, and a platform android.jar).
# GitHub's ubuntu runners already have both ($ANDROID_HOME). No Gradle plugin downloads, no keys.
# Optional overrides: BUILD_TOOLS=<dir with aapt2,d8>  ANDROID_JAR=<path>  AAPT2=<command>
set -euo pipefail

OUT="${1:?usage: build_template.sh OUT_PATH}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"

if [ -z "${BUILD_TOOLS:-}" ]; then
  [ -n "$SDK" ] || { echo "Set ANDROID_HOME or BUILD_TOOLS" >&2; exit 1; }
  # Prefer build-tools 33.x/34.x, else the newest present.
  BUILD_TOOLS=""
  for want in 34.0.0 33.0.2 33.0.1 33.0.0 33.0.3; do
    [ -x "$SDK/build-tools/$want/aapt2" ] && { BUILD_TOOLS="$SDK/build-tools/$want"; break; }
  done
  [ -n "$BUILD_TOOLS" ] || BUILD_TOOLS="$(ls -d "$SDK"/build-tools/* | sort -V | tail -1)"
fi
if [ -z "${ANDROID_JAR:-}" ]; then
  [ -f "$SDK/platforms/android-33/android.jar" ] || \
    (yes | "$SDK/cmdline-tools/latest/bin/sdkmanager" "platforms;android-33" >/dev/null) || true
  if [ -f "$SDK/platforms/android-33/android.jar" ]; then
    ANDROID_JAR="$SDK/platforms/android-33/android.jar"
  else
    ANDROID_JAR="$(ls -d "$SDK"/platforms/android-*/android.jar | sort -V | tail -1)"
  fi
fi
AAPT2="${AAPT2:-$BUILD_TOOLS/aapt2}"
D8="$BUILD_TOOLS/d8"
echo "build-tools: $BUILD_TOOLS"
echo "android.jar: $ANDROID_JAR"

B="$(mktemp -d)"
trap 'rm -rf "$B"' EXIT

# 1. resources + manifest
$AAPT2 compile --dir "$HERE/res" -o "$B/res.zip"
$AAPT2 link -o "$B/base.apk" -I "$ANDROID_JAR" \
  --manifest "$HERE/AndroidManifest.xml" -A "$HERE/assets" \
  --min-sdk-version 21 --target-sdk-version 29 \
  "$B/res.zip"

# 2. java -> dex
mkdir -p "$B/classes" "$B/dex"
javac -nowarn -source 8 -target 8 -bootclasspath "$ANDROID_JAR" -classpath "$ANDROID_JAR" \
  -d "$B/classes" $(find "$HERE/src" -name '*.java')
"$D8" --release --min-api 21 --lib "$ANDROID_JAR" --output "$B/dex" $(find "$B/classes" -name '*.class')

# 3. add classes.dex, make sure there is no signature, write the template
(cd "$B/dex" && zip -q -X "$B/base.apk" classes.dex)
zip -q -d "$B/base.apk" 'META-INF/*' >/dev/null 2>&1 || true
mkdir -p "$(dirname "$OUT")"
cp "$B/base.apk" "$OUT"
unzip -l "$OUT"
echo "template written: $OUT"
