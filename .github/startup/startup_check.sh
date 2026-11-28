#!/bin/bash
# Cold-start each app on an Android 11 emulator using the 32-bit (armeabi-v7a) libraries,
# like a low-RAM Android Go phone. Saves logcat, a screenshot and any crash.txt per app.
set +e
OUT=startup_out; mkdir -p $OUT
BT=$(ls -d $ANDROID_HOME/build-tools/* | sort -V | tail -1)
adb shell getprop ro.product.cpu.abilist | tee $OUT/abilist.txt
adb shell getprop ro.build.version.release | tee -a $OUT/abilist.txt
adb shell cat /proc/meminfo | head -3 | tee -a $OUT/abilist.txt
for F in apks/*.apk; do
  N=$(basename $F .apk)
  P=$("$BT/aapt" dump badging $F | sed -n "s/^package: name='\([^']*\)'.*/\1/p")
  echo "=== $N ($P)" | tee -a $OUT/summary.txt
  adb uninstall $P >/dev/null 2>&1
  adb install --abi armeabi-v7a $F 2>&1 | tee -a $OUT/summary.txt
  adb shell pm grant $P android.permission.READ_EXTERNAL_STORAGE >/dev/null 2>&1
  adb shell pm grant $P android.permission.WRITE_EXTERNAL_STORAGE >/dev/null 2>&1
  adb logcat -c
  adb shell monkey -p $P -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
  ALIVE=""
  for s in 10 20 30 45 60 90; do
    sleep 10
    PID=$(adb shell pidof $P | tr -d '\r')
    echo "t~${s}s pid=${PID:-none}" | tee -a $OUT/summary.txt
  done
  adb exec-out screencap -p > $OUT/$N.png
  adb logcat -d > $OUT/$N.logcat.txt
  grep -E "python|Python|SDL|kivy|Kivy|FATAL|AndroidRuntime|DEBUG  :|libc  |Traceback|Error|crash" $OUT/$N.logcat.txt | grep -v "^.*I chatty" | tail -150 > $OUT/$N.short.txt
  tail -60 $OUT/$N.short.txt | tee -a $OUT/summary.txt
  adb shell dumpsys meminfo $P | head -25 > $OUT/$N.meminfo.txt
  adb shell "ls -R /sdcard/Download 2>/dev/null" > $OUT/$N.download_ls.txt
  for d in Genius SsalimutoAI "Ssalimuto AI" SsalimutoProfits "Ssalimuto Profits"; do adb pull "/sdcard/Download/$d/crash.txt" "$OUT/$N.crash_$d.txt" >/dev/null 2>&1; done
  adb shell am force-stop $P
done
exit 0
