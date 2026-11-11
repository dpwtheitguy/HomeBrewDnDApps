package org.completeguide.armory;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteException;
import android.os.Bundle;
import android.os.Build;
import android.os.CancellationSignal;
import android.os.OperationCanceledException;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class MainActivity extends Activity {
    private static final String ORIGIN = "https://armory.local";
    private static final Pattern SEARCH_WORD = Pattern.compile("[\\p{L}\\p{N}]+");
    private WebView web;
    private CatalogBridge bridge;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        WebView.setWebContentsDebuggingEnabled(
                (getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0);
        web = new WebView(this);
        if (Build.PRODUCT.startsWith("sdk") || Build.HARDWARE.equals("ranchu")) {
            web.setLayerType(android.view.View.LAYER_TYPE_SOFTWARE, null);
        }
        web.setBackgroundColor(0xff161311);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setBlockNetworkLoads(true);
        bridge = new CatalogBridge();
        web.addJavascriptInterface(bridge, "Armory");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return true;
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String path = request.getUrl().getEncodedPath();
                if (!ORIGIN.equals(request.getUrl().getScheme() + "://" + request.getUrl().getAuthority())
                        || path == null || !path.matches("/[a-zA-Z0-9_/.-]+") || path.contains("..")) {
                    return new WebResourceResponse("text/plain", "UTF-8", null);
                }
                String mime = "text/plain";
                if (path.endsWith(".html")) mime = "text/html";
                if (path.endsWith(".css")) mime = "text/css";
                if (path.endsWith(".js")) mime = "application/javascript";
                if (path.endsWith(".json")) mime = "application/json";
                if (path.endsWith(".svg")) mime = "image/svg+xml";
                if (path.endsWith(".webp")) mime = "image/webp";
                if (path.endsWith(".png")) mime = "image/png";
                try {
                    return new WebResourceResponse(mime, mime.startsWith("image/") ? null : "UTF-8",
                            getAssets().open("web" + path));
                } catch (IOException error) {
                    return new WebResourceResponse("text/plain", "UTF-8", null);
                }
            }
        });
        setContentView(web);
        web.loadUrl(ORIGIN + "/index.html");
    }

    @Override protected void onDestroy() {
        bridge.close();
        web.destroy();
        super.onDestroy();
    }

    @Override public void onBackPressed() {
        web.evaluateJavascript("window.closeInspection && window.closeInspection()", closed -> {
            if (!"true".equals(closed)) super.onBackPressed();
        });
    }

    private String readAsset(String path) throws IOException {
        try (InputStream input = getAssets().open(path);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[32768];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            return output.toString("UTF-8");
        }
    }

    private final class CatalogBridge {
        private final SharedPreferences notes = getSharedPreferences("item-notes", MODE_PRIVATE);
        private final SharedPreferences preferences = getSharedPreferences("catalog-preferences", MODE_PRIVATE);
        private SQLiteDatabase database;
        private boolean fullText;
        private final ExecutorService searchWorker = Executors.newSingleThreadExecutor();
        private final Object catalogLock = new Object();
        private CancellationSignal pending;
        private boolean closed;

        private SQLiteDatabase catalog() throws IOException, JSONException {
            synchronized (catalogLock) {
                return openCatalog();
            }
        }

        private SQLiteDatabase openCatalog() throws IOException, JSONException {
            if (database != null) return database;
            JSONObject manifest = new JSONObject(readAsset("manifest.json"));
            String version = manifest.getString("content_version");
            if (manifest.getInt("format_version") != 1 || !version.matches("[0-9]+([.-][0-9]+)*")) {
                throw new IOException("Unsupported catalog release");
            }
            String path = manifest.getString("database");
            File target = new File(getFilesDir(), "catalog-" + version + "-search7.sqlite3");
            if (!target.isFile()) {
                File staging = new File(getFilesDir(), "catalog-install.tmp");
                try (ZipInputStream zip = new ZipInputStream(getAssets().open("database.zip"));
                     FileOutputStream output = new FileOutputStream(staging)) {
                    ZipEntry entry = zip.getNextEntry();
                    if (entry == null || !path.equals(entry.getName())) throw new IOException("Catalog database is missing");
                    byte[] buffer = new byte[65536];
                    int count;
                    while ((count = zip.read(buffer)) != -1) output.write(buffer, 0, count);
                    output.getFD().sync();
                } catch (IOException error) {
                    staging.delete();
                    throw error;
                }
                if (!staging.renameTo(target)) throw new IOException("Could not install the catalog");
            }
            database = SQLiteDatabase.openDatabase(target.getPath(), null, SQLiteDatabase.OPEN_READONLY);
            try (Cursor probe = database.rawQuery("SELECT id FROM item_search LIMIT 1", null)) {
                fullText = probe.moveToFirst();
            } catch (SQLiteException unsupported) {
                fullText = false;
            }
            return database;
        }

        @JavascriptInterface public String metadata() {
            try {
                return new JSONObject().put("manifest", new JSONObject(readAsset("manifest.json")))
                        .put("sources", new JSONArray(readAsset("sources.json")))
                        .put("taxonomy", new JSONObject(readAsset("entities.json"))).toString();
            } catch (IOException | JSONException error) {
                return failure(error);
            }
        }

        @JavascriptInterface public synchronized void search(int requestId, String request) {
            if (closed) return;
            if (pending != null) pending.cancel();
            CancellationSignal signal = new CancellationSignal();
            pending = signal;
            searchWorker.execute(() -> {
                try {
                    signal.throwIfCanceled();
                    String result = query(request, signal);
                    runOnUiThread(() -> {
                        if (!isDestroyed() && !signal.isCanceled()) {
                            web.evaluateJavascript("window.receiveSearch(" + requestId + "," + JSONObject.quote(result) + ")", null);
                        }
                    });
                } catch (OperationCanceledException ignored) {
                    // A newer query superseded this request.
                }
            });
        }

        private synchronized void close() {
            closed = true;
            if (pending != null) pending.cancel();
            searchWorker.execute(() -> {
                if (database != null) database.close();
            });
            searchWorker.shutdown();
        }

        private String query(String request, CancellationSignal signal) {
            try {
                SQLiteDatabase db = catalog();
                signal.throwIfCanceled();
                JSONObject query = new JSONObject(request);
                StringBuilder where = new StringBuilder(" WHERE 1=1");
                ArrayList<String> arguments = new ArrayList<>();
                ArrayList<String> words = new ArrayList<>();
                String term = query.optString("term");
                Matcher matcher = SEARCH_WORD.matcher(term.substring(0, Math.min(term.length(), 120)));
                while (matcher.find() && words.size() < 12) words.add(matcher.group());
                String scope = query.optString("scope");
                boolean useFullText = fullText && !"name".equals(scope) && !"exact".equals(scope);
                if ("exact".equals(scope) && !term.trim().isEmpty()) {
                    where.append(" AND i.name COLLATE NOCASE=?");
                    arguments.add(term.trim());
                } else if (!words.isEmpty() && useFullText) {
                    where.append(" AND i.id IN (SELECT id FROM item_search WHERE item_search MATCH ?)");
                    ArrayList<String> prefixes = new ArrayList<>();
                    for (String word : words) prefixes.add(word + "*");
                    arguments.add(android.text.TextUtils.join(" AND ", prefixes));
                } else {
                    for (String word : words) {
                        where.append(" AND lower(i.name) LIKE ?");
                        arguments.add("%" + word.toLowerCase(Locale.ROOT) + "%");
                    }
                }
                JSONArray types = query.optJSONArray("types");
                if (types != null && types.length() > 0 && types.length() <= 60) {
                    where.append(" AND i.type IN (").append(android.text.TextUtils.join(",", Collections.nCopies(types.length(), "?"))).append(")");
                    for (int index = 0; index < types.length(); index++) arguments.add(types.getString(index));
                }
                addFilter(where, arguments, "i.ruleset", query.optString("ruleset"));
                addFilter(where, arguments, "i.rarity_key", query.optString("rarity"));
                addFilter(where, arguments, "i.source_id", query.optString("source"));
                String initial = query.optString("initial");
                if (initial.matches("[a-z#]")) addFilter(where, arguments, "i.name_initial", initial);
                addPriceLimit(where, arguments, ">=", query.optString("minBuyCopper"));
                addPriceLimit(where, arguments, "<=", query.optString("maxBuyCopper"));
                String proficiency = query.optString("proficiency");
                if (!proficiency.isEmpty()) {
                    where.append(" AND i.id IN (SELECT item_id FROM item_proficiencies WHERE profile=?)");
                    arguments.add(proficiency);
                }
                for (String field : new String[]{"setting", "region", "culture"}) {
                    String value = query.optString(field);
                    if (value.isEmpty()) continue;
                    where.append(" AND EXISTS (SELECT 1 FROM associations a WHERE a.item_id=i.id AND a.entity_id=?)");
                    arguments.add(value);
                }
                JSONArray tags = query.optJSONArray("tags");
                if (tags != null && tags.length() <= 5) {
                    for (int index = 0; index < tags.length(); index++) {
                        where.append(" AND EXISTS (SELECT 1 FROM tags t WHERE t.item_id=i.id AND t.tag=?)");
                        arguments.add(tags.getString(index));
                    }
                }
                String order = "i.name_key, i.id";
                String sort = query.optString("sort");
                if ("reverse".equals(sort)) order = "i.name_key DESC, i.id";
                if ("price-asc".equals(sort)) order = "i.price_copper, i.name_key, i.id";
                if ("price-desc".equals(sort)) order = "i.price_copper DESC, i.name_key DESC, i.id DESC";
                if ("relevance".equals(sort)) {
                    if (!words.isEmpty()) {
                        order = "CASE WHEN lower(i.name)=? THEN 0 WHEN lower(i.name) LIKE ? THEN 1 ELSE 2 END, " + order;
                    }
                    order = order.replace("i.name_key, i.id", "i.edition_rank, i.name_key, i.id");
                }
                int offset = Math.max(0, query.optInt("offset"));
                int total = -1;
                if (offset == 0) {
                    try (Cursor count = db.rawQuery("SELECT count(*) FROM item_cards i" + where, arguments.toArray(new String[0]), signal)) {
                        count.moveToFirst();
                        total = count.getInt(0);
                    }
                }
                if (order.contains("lower(i.name)")) {
                    String normalized = term.trim().toLowerCase(Locale.ROOT);
                    arguments.add(normalized);
                    arguments.add(normalized + "%");
                }
                arguments.add(Integer.toString(offset));
                JSONArray items = new JSONArray();
                try (Cursor rows = db.rawQuery("SELECT i.id,i.name,i.type,i.ruleset,i.rarity,i.image_path,i.source_id,i.price_copper,i.buy_copper FROM item_cards i"
                        + where + " ORDER BY " + order + " LIMIT 48 OFFSET ?", arguments.toArray(new String[0]), signal)) {
                    while (rows.moveToNext()) {
                        JSONObject item = new JSONObject();
                        String[] keys = {"id", "name", "type", "ruleset", "rarity", "image", "source", "price_copper", "buy_copper"};
                        for (int column = 0; column < keys.length; column++) {
                            item.put(keys[column], rows.isNull(column) ? JSONObject.NULL : rows.getString(column));
                        }
                        items.put(item);
                    }
                }
                return new JSONObject().put("items", items).put("total", total).put("fullText", fullText).toString();
            } catch (IOException | JSONException | SQLiteException error) {
                return failure(error);
            }
        }

        private void addFilter(StringBuilder where, ArrayList<String> arguments, String field, String value) {
            if (value.isEmpty()) return;
            where.append(" AND ").append(field).append("=?");
            arguments.add(value);
        }

        private void addPriceLimit(StringBuilder where, ArrayList<String> arguments, String operator, String value) {
            if (!value.matches("[0-9]{1,13}")) return;
            where.append(" AND i.buy_copper ").append(operator).append(" CAST(? AS INTEGER)");
            arguments.add(value);
        }

        @JavascriptInterface public String item(String id) {
            String sql = "SELECT i.data_json,p.price_json FROM items i JOIN item_prices p ON p.item_id=i.id WHERE i.id=?";
            try (Cursor row = catalog().rawQuery(sql, new String[]{id})) {
                if (!row.moveToFirst()) return "{}";
                return new JSONObject(row.getString(0)).put("market_price", new JSONObject(row.getString(1))).toString();
            } catch (IOException | JSONException | SQLiteException error) {
                return failure(error);
            }
        }

        @JavascriptInterface public String note(String id) { return notes.getString(id, ""); }

        @JavascriptInterface public String defaults() { return preferences.getString("search-defaults", "{}"); }

        @JavascriptInterface public boolean saveDefaults(String defaults) {
            return defaults.length() <= 4096
                    && preferences.edit().putString("search-defaults", defaults).commit();
        }

        @JavascriptInterface public void saveNote(String id, String note) {
            if (note.isEmpty()) notes.edit().remove(id).apply();
            else notes.edit().putString(id, note.substring(0, Math.min(note.length(), 4000))).apply();
        }

        @JavascriptInterface public void share(String subject, String text) {
            runOnUiThread(() -> {
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_SUBJECT, subject);
                send.putExtra(Intent.EXTRA_TEXT, text);
                startActivity(Intent.createChooser(send, "Share equipment entry"));
            });
        }

        @JavascriptInterface public boolean copyEntry(String title, String text) {
            ClipboardManager clipboard = getSystemService(ClipboardManager.class);
            if (clipboard == null) return false;
            try {
                clipboard.setPrimaryClip(ClipData.newPlainText(title, text));
                return true;
            } catch (RuntimeException error) {
                android.util.Log.e("Armory", "Clipboard write failed", error);
                return false;
            }
        }

        @JavascriptInterface public void openSource(String url) {
            android.net.Uri uri = android.net.Uri.parse(url);
            String scheme = uri.getScheme();
            if (!("https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme))
                    || uri.getHost() == null || uri.getUserInfo() != null) return;
            runOnUiThread(() -> {
                Intent view = new Intent(Intent.ACTION_VIEW, uri);
                view.addCategory(Intent.CATEGORY_BROWSABLE);
                try {
                    startActivity(view);
                } catch (android.content.ActivityNotFoundException error) {
                    android.widget.Toast.makeText(MainActivity.this, "Install a browser to open this source.", android.widget.Toast.LENGTH_SHORT).show();
                }
            });
        }

        @JavascriptInterface public String sharePdf(String subject, String text) {
            try {
                android.net.Uri pdf = EntryPdfProvider.create(MainActivity.this, text);
                runOnUiThread(() -> {
                    Intent send = new Intent(Intent.ACTION_SEND);
                    send.setType("application/pdf");
                    send.putExtra(Intent.EXTRA_SUBJECT, subject);
                    send.putExtra(Intent.EXTRA_STREAM, pdf);
                    send.setClipData(android.content.ClipData.newRawUri(subject, pdf));
                    send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(Intent.createChooser(send, "Share equipment PDF"));
                });
                return "";
            } catch (IOException | RuntimeException error) {
                android.util.Log.e("Armory", "PDF export failed", error);
                return "The PDF could not be prepared.";
            }
        }

        private String failure(Exception error) {
            android.util.Log.e("Armory", "Catalog request failed", error);
            return "{\"error\":\"The catalog could not be read. Check available device storage and reopen the guide.\"}";
        }
    }
}
