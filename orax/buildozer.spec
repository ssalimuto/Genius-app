[app]
title = Orax
package.name = orax
package.domain = org.ssalimuto
source.dir = .
source.include_exts = py,png
source.exclude_dirs = tests,bin,.buildozer,p4a-src,android_extra,art,fonts,out,.github
source.exclude_patterns = tests/*,art/*,fonts/*
version = 1.0.0
android.numeric_version = 102500001
# Light on purpose for low-RAM phones: no pillow, no plyer.
requirements = python3,kivy==2.3.0,pyjnius,android,certifi
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0B1530
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 34
android.minapi = 21
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False
android.release_artifact = apk
android.extra_manifest_xml = ./android_extra/queries.xml
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
