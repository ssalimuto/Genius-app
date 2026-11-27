[app]
title = Ssalimuto Profits
package.name = profits
package.domain = org.ssalimuto
source.dir = .
source.include_exts = py,png,json,ttf,txt
source.exclude_dirs = tests,bin,.buildozer,p4a-src,android_extra,.github
source.exclude_patterns = tests/*,tests/*/*
version = 1.0
requirements = python3,kivy==2.3.0,pyjnius,certifi
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0B0B0D
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False
android.release_artifact = apk
android.extra_manifest_xml = ./android_extra/queries.xml
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
