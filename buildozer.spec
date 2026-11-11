[app]
title = Genius
package.name = genius
package.domain = org.ssalimuto
source.dir = .
source.include_exts = py,png,jpg,json,txt,ttf
source.exclude_dirs = .github,bin,.buildozer,p4a-src,android_extra,ssalimuto
version = 115.1
requirements = python3,kivy==2.3.0,plyer,pyjnius,certifi,android,pillow
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,REQUEST_INSTALL_PACKAGES,CAMERA,SYSTEM_ALERT_WINDOW,RECORD_AUDIO,VIBRATE,POST_NOTIFICATIONS,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,QUERY_ALL_PACKAGES,READ_SMS
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False

p4a.source_dir = p4a-src
android.add_src = android_extra/java
android.add_resources = android_extra/res
android.manifest.intent_filters = android_extra/intent_filters.xml
android.manifest.launch_mode = singleTask

[buildozer]
log_level = 2
warn_on_root = 0
