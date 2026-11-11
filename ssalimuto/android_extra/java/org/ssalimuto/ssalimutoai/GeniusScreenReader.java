package org.ssalimuto.ssalimutoai;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import org.json.JSONObject;

/** Remembers the words on screen in the app you used last, so Genius can read or explain it.
 *  Only runs after the user turns on Genius under Android Settings > Accessibility.
 *  Never reads password boxes, and skips banking, mobile money and security apps. */
public class GeniusScreenReader extends AccessibilityService {
    private long last = 0;
    private String lastPkg = "";

    @Override
    public void onAccessibilityEvent(AccessibilityEvent ev) {
        try {
            if (ev == null || GeniusStore.paused(this)) return;
            CharSequence p = ev.getPackageName();
            if (p == null) return;
            String pkg = p.toString();
            if (pkg.equals(getPackageName()) || pkg.startsWith("com.android.systemui")
                    || pkg.contains("launcher") || pkg.contains("inputmethod") || pkg.contains("keyboard")
                    || GeniusStore.privateApp(pkg)) return;
            long now = System.currentTimeMillis();
            if (pkg.equals(lastPkg) && now - last < 1500) return;
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root == null) return;
            CharSequence rp = root.getPackageName();
            if (rp != null && !rp.toString().equals(pkg)) return;
            StringBuilder sb = new StringBuilder();
            walk(root, sb, 0);
            String txt = sb.toString().trim();
            if (txt.length() < 3) return;
            last = now;
            lastPkg = pkg;
            JSONObject o = new JSONObject();
            o.put("pkg", pkg);
            o.put("app", GeniusStore.appName(this, pkg));
            o.put("t", now);
            o.put("text", txt);
            GeniusStore.write(this, "genius_screen.json", o.toString());
            GeniusStore.append(this, "genius_screens.jsonl", o.toString(), 60);
        } catch (Throwable ignored) { }
    }

    private void walk(AccessibilityNodeInfo n, StringBuilder sb, int depth) {
        if (n == null || depth > 45 || sb.length() > 8000) return;
        try {
            if (!n.isPassword()) {
                CharSequence t = n.getText();
                if (t == null || t.length() == 0) t = n.getContentDescription();
                if (t != null && t.length() > 0) sb.append(t).append("\n");
            }
            int c = n.getChildCount();
            for (int i = 0; i < c; i++) {
                AccessibilityNodeInfo ch = n.getChild(i);
                walk(ch, sb, depth + 1);
            }
        } catch (Throwable ignored) { }
    }

    @Override
    public void onInterrupt() { }

    @Override
    protected void onServiceConnected() {
        GeniusStore.write(this, "genius_screen_on.txt", String.valueOf(System.currentTimeMillis()));
    }
}
