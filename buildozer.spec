[app]
title = Genius
package.name = genius
package.domain = org.ssalimuto
source.dir = .
source.include_exts = py,png,jpg,json,txt
source.exclude_dirs = .github,bin,.buildozer
version = 106.0
requirements = python3,kivy==2.3.0,plyer,pyjnius,certifi,android,pillow
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,CAMERA,SYSTEM_ALERT_WINDOW,RECORD_AUDIO,VIBRATE,POST_NOTIFICATIONS,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,QUERY_ALL_PACKAGES
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
