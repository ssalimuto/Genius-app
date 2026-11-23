package org.ssalimuto.ssalimutoai;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.pm.ProviderInfo;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.List;

/**
 * Hands one downloaded app update to Android's installer, read-only.
 * Serves only files named *.apk inside the app's own cache/updates folder, nothing else.
 * Not exported: the installer can read a file only through a one-time read grant.
 */
public class GeniusApkProvider extends ContentProvider {
    private static final String MIME = "application/vnd.android.package-archive";

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public void attachInfo(Context context, ProviderInfo info) {
        super.attachInfo(context, info);
        if (info.exported) throw new SecurityException("Provider must not be exported");
        if (!info.grantUriPermissions) throw new SecurityException("Provider must grant URI permissions");
    }

    private File fileFor(Uri uri) throws FileNotFoundException {
        List<String> seg = uri.getPathSegments();
        if (seg == null || seg.size() != 2 || !"updates".equals(seg.get(0))) throw new FileNotFoundException("not found");
        String name = seg.get(1);
        if (!name.matches("[A-Za-z0-9._-]{1,80}\\.apk") || name.startsWith(".")) throw new FileNotFoundException("not found");
        try {
            File dir = new File(getContext().getCacheDir(), "updates").getCanonicalFile();
            File f = new File(dir, name).getCanonicalFile();
            if (!dir.equals(f.getParentFile()) || !f.isFile()) throw new FileNotFoundException("not found");
            return f;
        } catch (IOException e) {
            throw new FileNotFoundException("not found");
        }
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (mode == null || !mode.equals("r")) throw new SecurityException("read only");
        return ParcelFileDescriptor.open(fileFor(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public String getType(Uri uri) {
        return uri.getLastPathSegment() != null && uri.getLastPathSegment().endsWith(".apk") ? MIME : null;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        File f;
        try {
            f = fileFor(uri);
        } catch (FileNotFoundException e) {
            return null;
        }
        String[] cols = projection != null ? projection : new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE};
        MatrixCursor c = new MatrixCursor(cols, 1);
        Object[] row = new Object[cols.length];
        for (int i = 0; i < cols.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(cols[i])) row[i] = f.getName();
            else if (OpenableColumns.SIZE.equals(cols[i])) row[i] = f.length();
            else row[i] = null;
        }
        c.addRow(row);
        return c;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("read only");
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("read only");
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("read only");
    }
}
