# App Maker shell

A tiny WebView Android app (Java, no Gradle plugin needed) that shows `assets/app.html` full screen.
CI builds it with `build_template.sh` into `apk_template.bin` (unsigned, no META-INF) next to each
app's `main.py`; on the phone `apk_maker.py` swaps in the user's HTML, patches the package id
(`org.ssalimuto.mkapp.zzzzzzzzzzzz`) and label (30 `#`) placeholders, and v1-signs it.
minSdk 21, targetSdk 29 (so v1 signing alone installs on Android 11+), compiled against android-33.
Keep the placeholder lengths unchanged.
