package org.ssalimuto.ssalimutoai;

import android.content.Context;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.util.ArrayList;
import java.util.List;

/** Small private files Genius (Python) reads. Everything stays on the phone. */
public class GeniusStore {
    public static synchronized void append(Context c, String name, String line, int maxLines) {
        try {
            File f = new File(c.getFilesDir(), name);
            FileWriter w = new FileWriter(f, true);
            w.write(line.replace("\n", " ").replace("\r", " ") + "\n");
            w.close();
            if (f.length() > (long) maxLines * 900L) {
                List<String> all = new ArrayList<String>();
                BufferedReader r = new BufferedReader(new FileReader(f));
                String s;
                while ((s = r.readLine()) != null) all.add(s);
                r.close();
                int start = Math.max(0, all.size() - maxLines / 2);
                FileWriter w2 = new FileWriter(f, false);
                for (int i = start; i < all.size(); i++) w2.write(all.get(i) + "\n");
                w2.close();
            }
        } catch (Throwable t) { }
    }

    public static synchronized void write(Context c, String name, String text) {
        try {
            File tmp = new File(c.getFilesDir(), name + ".tmp");
            FileWriter w = new FileWriter(tmp, false);
            w.write(text);
            w.close();
            tmp.renameTo(new File(c.getFilesDir(), name));
        } catch (Throwable t) { }
    }

    public static boolean paused(Context c) {
        return new File(c.getFilesDir(), "genius_apps_paused.flag").exists();
    }

    public static String appName(Context c, String pkg) {
        try {
            return c.getPackageManager().getApplicationLabel(
                    c.getPackageManager().getApplicationInfo(pkg, 0)).toString();
        } catch (Throwable t) {
            return pkg;
        }
    }

    /** Money and security apps are never read. */
    public static boolean privateApp(String pkg) {
        String p = pkg.toLowerCase();
        String[] skip = {"bank", "equity", "momo", "mobilemoney", "wallet", "airtel.money", "mtn",
                "authenticator", "authy", "keepass", "bitwarden", "lastpass", "1password", "xeno",
                "binance", "chipper", "paypal", ".pay", "pay.", "stanbic", "absa", "centenary",
                "dfcu", "kcb", "packageinstaller", "permissioncontroller", "settings"};
        for (String s : skip) if (p.contains(s)) return true;
        return false;
    }
}
