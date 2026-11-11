package org.ssalimuto.ssalimutoai;

import android.app.Notification;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import org.json.JSONObject;

/** Saves incoming messages (WhatsApp, Telegram, SMS, email...) that appear as notifications.
 *  Only runs after the user turns on Notification Access for Genius in Android Settings. */
public class GeniusNotifListener extends NotificationListenerService {
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        try {
            if (sbn == null || GeniusStore.paused(this)) return;
            String pkg = sbn.getPackageName();
            if (pkg == null || pkg.equals(getPackageName()) || pkg.equals("android")
                    || pkg.startsWith("com.android.systemui") || GeniusStore.privateApp(pkg)) return;
            Notification n = sbn.getNotification();
            if (n == null) return;
            if ((n.flags & Notification.FLAG_ONGOING_EVENT) != 0) return;
            if ((n.flags & Notification.FLAG_GROUP_SUMMARY) != 0) return;
            Bundle e = n.extras;
            if (e == null) return;
            CharSequence title = e.getCharSequence(Notification.EXTRA_TITLE);
            CharSequence text = e.getCharSequence(Notification.EXTRA_BIG_TEXT);
            if (text == null) text = e.getCharSequence(Notification.EXTRA_TEXT);
            StringBuilder body = new StringBuilder();
            if (text != null) body.append(text);
            if (text == null) {
                CharSequence[] lines = e.getCharSequenceArray(Notification.EXTRA_TEXT_LINES);
                if (lines != null) for (CharSequence l : lines) if (l != null) body.append(l).append(" | ");
            }
            String b = body.toString().trim();
            String t = title == null ? "" : title.toString();
            if (b.length() == 0 && t.length() == 0) return;
            if (b.length() > 2000) b = b.substring(0, 2000);
            CharSequence sub = e.getCharSequence(Notification.EXTRA_SUB_TEXT);
            JSONObject o = new JSONObject();
            o.put("pkg", pkg);
            o.put("app", GeniusStore.appName(this, pkg));
            o.put("title", t);
            o.put("text", b);
            o.put("sub", sub == null ? "" : sub.toString());
            o.put("t", sbn.getPostTime());
            GeniusStore.append(this, "genius_notifs.jsonl", o.toString(), 1500);
        } catch (Throwable ignored) { }
    }

    @Override
    public void onListenerConnected() {
        GeniusStore.write(this, "genius_notif_on.txt", String.valueOf(System.currentTimeMillis()));
    }
}
