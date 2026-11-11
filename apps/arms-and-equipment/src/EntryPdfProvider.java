package org.completeguide.armory;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.text.StaticLayout;
import android.text.TextPaint;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.UUID;

public final class EntryPdfProvider extends ContentProvider {
    private static final String AUTHORITY = "org.completeguide.armory.entry-pdf";
    private static final String DIRECTORY = "entry-pdfs";

    static Uri create(Context context, String text) throws IOException {
        File directory = new File(context.getCacheDir(), DIRECTORY);
        if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("PDF cache is unavailable");
        String id = UUID.randomUUID().toString();
        File file = new File(directory, id + ".pdf");
        TextPaint paint = new TextPaint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        paint.setTypeface(Typeface.SERIF);
        paint.setTextSize(12);
        paint.setColor(Color.BLACK);
        StaticLayout layout = StaticLayout.Builder.obtain(text, 0, text.length(), paint, 508)
                .setLineSpacing(3, 1).build();

        PdfDocument document = new PdfDocument();
        try (FileOutputStream output = new FileOutputStream(file)) {
            int pageNumber = 1;
            for (int line = 0; line < layout.getLineCount();) {
                int start = layout.getLineTop(line);
                int end = line + 1;
                while (end < layout.getLineCount() && layout.getLineTop(end + 1) - start <= 666) end++;
                PdfDocument.Page page = document.startPage(new PdfDocument.PageInfo.Builder(612, 792, pageNumber++).create());
                page.getCanvas().drawText("ARMS AND EQUIPMENT GUIDE", 52, 42, paint);
                page.getCanvas().save();
                page.getCanvas().clipRect(52, 66, 560, 66 + layout.getLineTop(end) - start);
                page.getCanvas().translate(52, 66 - start);
                layout.draw(page.getCanvas());
                page.getCanvas().restore();
                document.finishPage(page);
                line = end;
            }
            document.writeTo(output);
        } catch (IOException | RuntimeException error) {
            file.delete();
            throw error;
        } finally {
            document.close();
        }
        return new Uri.Builder().scheme("content").authority(AUTHORITY).appendPath(id).build();
    }

    @Override public boolean onCreate() { return true; }

    private File find(Uri uri) throws FileNotFoundException {
        String id = uri.getLastPathSegment();
        if (!AUTHORITY.equals(uri.getAuthority()) || uri.getPathSegments().size() != 1
                || id == null || !id.matches("[a-f0-9-]{36}")) throw new FileNotFoundException();
        File file = new File(new File(getContext().getCacheDir(), DIRECTORY), id + ".pdf");
        if (!file.isFile()) throw new FileNotFoundException();
        return file;
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"r".equals(mode)) throw new FileNotFoundException();
        return ParcelFileDescriptor.open(find(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
        String[] columns = projection == null ? new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE} : projection;
        MatrixCursor result = new MatrixCursor(columns);
        try {
            File file = find(uri);
            Object[] row = new Object[columns.length];
            for (int index = 0; index < columns.length; index++) {
                if (OpenableColumns.DISPLAY_NAME.equals(columns[index])) row[index] = "Equipment entry.pdf";
                if (OpenableColumns.SIZE.equals(columns[index])) row[index] = file.length();
            }
            result.addRow(row);
        } catch (FileNotFoundException ignored) {
            // The app cache can be cleared by the system.
        }
        return result;
    }

    @Override public String getType(Uri uri) { return "application/pdf"; }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException(); }
}
