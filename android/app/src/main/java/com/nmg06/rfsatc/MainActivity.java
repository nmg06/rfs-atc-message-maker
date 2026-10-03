package com.nmg06.rfsatc;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.webkit.WebViewAssetLoader;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.zip.GZIPInputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** A local mobile interface; native storage, clipboard and the existing Python engines. */
public class MainActivity extends Activity {
    private static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final int DOCUMENT = 10;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final List<Uri> images = new ArrayList<>();
    private WebView web;
    private String startupError;
    private String pickerId, pickerMode, documentText;
    private JSONObject report;
    private boolean consent;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        web = new WebView(this);
        web.setBackgroundColor(0xff10151d);
        web.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        setContentView(web);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(false);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setAllowFileAccessFromFileURLs(false);
        web.getSettings().setAllowUniversalAccessFromFileURLs(false);
        web.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return true; // Navigation, including external URLs, is never a bridge surface.
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest r) {
                if (ORIGIN.equals(r.getUrl().getScheme() + "://" + r.getUrl().getHost())) {
                    WebResourceResponse result = loader.shouldInterceptRequest(r.getUrl());
                    if (result != null) return result;
                }
                return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
            }
        });
        web.setWebChromeClient(new android.webkit.WebChromeClient());
        worker.execute(() -> {
            try {
                File database = installDatabase();
                if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                Python.getInstance().getModule("android_engine").callAttr("initialise", getFilesDir().getAbsolutePath(), database.getAbsolutePath());
            } catch (Exception e) { startupError = e.toString(); }
        });
        web.addJavascriptInterface(new Bridge(), "Android");
        web.loadUrl(ORIGIN + "/assets/www/index.html");
    }

    private File installDatabase() throws Exception {
        JSONObject manifest = new JSONObject(new String(readLimited(getAssets().open("database-manifest.json"), 65536), StandardCharsets.UTF_8));
        File target = new File(getFilesDir(), "aviation.sqlite");
        String expected = manifest.getString("database_sha256");
        if (target.isFile() && hash(target).equals(expected)) return target;
        File temporary = new File(getFilesDir(), "aviation.sqlite.installing");
        try (InputStream in = new GZIPInputStream(getAssets().open("aviation.database")); FileOutputStream out = new FileOutputStream(temporary)) {
            byte[] buffer = new byte[65536]; int count;
            while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
            out.getFD().sync();
        }
        if (temporary.length() != manifest.getLong("database_bytes") || !hash(temporary).equals(expected)) {
            temporary.delete(); throw new IOException("Bundled aviation database checksum mismatch");
        }
        android.system.Os.rename(temporary.getAbsolutePath(), target.getAbsolutePath());
        return target;
    }

    private String hash(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(file)) {
            byte[] bytes = new byte[65536]; int n;
            while ((n = in.read(bytes)) != -1) digest.update(bytes, 0, n);
        }
        StringBuilder result = new StringBuilder();
        for (byte b : digest.digest()) result.append(String.format("%02x", b & 255));
        return result.toString();
    }

    private static byte[] readLimited(InputStream in, int limit) throws IOException {
        try (InputStream input = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int n;
            while ((n = input.read(buffer)) != -1) {
                if (out.size() + n > limit) throw new IOException("File exceeds size limit");
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }

    private String command(String method, String payload) {
        if (startupError != null) return error(startupError);
        return Python.getInstance().getModule("android_engine").callAttr("request", method, payload).toString();
    }

    private String error(String message) {
        try { return new JSONObject().put("ok", false).put("error", message).toString(); }
        catch (Exception impossible) { throw new RuntimeException(impossible); }
    }

    private void reply(String id, String json) {
        runOnUiThread(() -> { if (!isDestroyed()) web.evaluateJavascript("window.androidReply(" + JSONObject.quote(id) + "," + json + ")", null); });
    }

    public class Bridge {
        @JavascriptInterface public void request(String id, String method, String payload) {
            if (!id.matches("[0-9]{1,12}") || payload.length() > 2 * 1024 * 1024) return;
            worker.execute(() -> {
                try {
                    JSONObject args = new JSONObject(payload);
                    if (method.startsWith("native.")) nativeRequest(id, method, args);
                    else reply(id, command(method, payload));
                } catch (Exception e) { reply(id, error(e.toString())); }
            });
        }
    }

    private void nativeRequest(String id, String method, JSONObject args) throws Exception {
        switch (method) {
            case "native.copy": case "native.share": {
                JSONObject result = new JSONObject(command("copy", args.toString()));
                if (!result.getBoolean("ok")) { reply(id, result.toString()); return; }
                String text = result.getJSONObject("result").getString("text");
                runOnUiThread(() -> {
                    try {
                        if (method.equals("native.copy")) {
                            ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                            clipboard.setPrimaryClip(ClipData.newPlainText("RFS ATC", text));
                        } else {
                            Intent intent = new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text);
                            startActivity(Intent.createChooser(intent, "RFS ATC"));
                        }
                        reply(id, result.toString());
                    } catch (Exception e) { reply(id, error(e.toString())); }
                });
                break;
            }
            case "native.export": {
                JSONObject result = new JSONObject(command("export", args.toString()));
                if (!result.getBoolean("ok")) { reply(id, result.toString()); return; }
                documentText = result.getJSONObject("result").getString("text");
                picker(id, "export", "application/json", "rfs-android-backup.json"); break;
            }
            case "native.import": picker(id, "import", "application/json", null); break;
            case "native.pcImport": picker(id, "pcImport", "application/json", null); break;
            case "native.designExport": {
                documentText = args.getJSONObject("design").toString(2);
                picker(id, "export", "application/json", "rfs-design.json"); break;
            }
            case "native.designImport": picker(id, "design", "application/json", null); break;
            case "native.images": picker(id, "images", "image/*", null); break;
            case "native.clearImages": images.clear(); reply(id, "{\"ok\":true,\"result\":{\"images\":[]}}"); break;
            case "native.report": {
                report = args.getJSONObject("report"); consent = args.optBoolean("consent", false);
                if (report.optString("summary").trim().isEmpty() || report.optString("observed").trim().isEmpty()) throw new IllegalArgumentException("Summary and observed result required");
                picker(id, "report", "application/zip", "rfs-android-report.zip"); break;
            }
            case "native.forms": {
                runOnUiThread(() -> {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://docs.google.com/forms/d/e/1FAIpQLSf5Btz-JubaPy9n8g2kpYvFSojD6ngSq3ruS0KEAzgxcUpHAw/viewform?usp=header")));
                        reply(id, "{\"ok\":true,\"result\":{}}");
                    } catch (Exception e) { reply(id, error(e.toString())); }
                }); break;
            }
            default: throw new IllegalArgumentException("Unknown native operation");
        }
    }

    private void picker(String id, String mode, String mime, String name) {
        runOnUiThread(() -> {
            if (pickerId != null) { reply(id, error("A document selection is already open")); return; }
            pickerId = id; pickerMode = mode;
            Intent intent = new Intent(name == null ? Intent.ACTION_OPEN_DOCUMENT : Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE).setType(mime);
            if (name != null) intent.putExtra(Intent.EXTRA_TITLE, name);
            if (mode.equals("images") || mode.equals("pcImport")) intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
            try { startActivityForResult(intent, DOCUMENT); }
            catch (Exception e) { pickerId = null; reply(id, error(e.toString())); }
        });
    }

    private String imageName(int index) {
        String mime = getContentResolver().getType(images.get(index));
        String extension = android.webkit.MimeTypeMap.getSingleton().getExtensionFromMimeType(mime);
        return "image-" + (index + 1) + (extension == null ? "" : "." + extension);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != DOCUMENT || pickerId == null) return;
        String id = pickerId, mode = pickerMode; pickerId = null;
        if (result != RESULT_OK || data == null) { reply(id, "{\"ok\":true,\"result\":{\"cancelled\":true}}"); return; }
        worker.execute(() -> {
            try {
                if (mode.equals("images")) {
                    ClipData clips = data.getClipData();
                    List<Uri> selected = new ArrayList<>();
                    if (clips == null) selected.add(data.getData());
                    else for (int i = 0; i < clips.getItemCount(); i++) selected.add(clips.getItemAt(i).getUri());
                    for (Uri uri : selected) {
                        if (images.size() >= 5) break;
                        String mime = getContentResolver().getType(uri);
                        if (mime == null || !mime.startsWith("image/")) throw new IOException("Image required");
                        readLimited(getContentResolver().openInputStream(uri), 10 * 1024 * 1024);
                        if (!images.contains(uri)) images.add(uri);
                    }
                    JSONArray list = new JSONArray();
                    for (int i = 0; i < images.size(); i++) list.put("image-" + (i + 1));
                    reply(id, new JSONObject().put("ok", true).put("result", new JSONObject().put("images", list)).toString());
                } else if (mode.equals("pcImport")) {
                    List<Uri> selected = new ArrayList<>();
                    ClipData clips = data.getClipData();
                    if (clips == null) selected.add(data.getData());
                    else for (int i = 0; i < clips.getItemCount(); i++) selected.add(clips.getItemAt(i).getUri());
                    if (selected.size() != 4) throw new IOException("Select the four PC JSON files together");
                    JSONObject files = new JSONObject();
                    int remaining = 2 * 1024 * 1024;
                    for (Uri uri : selected) {
                        String name;
                        try (android.database.Cursor cursor = getContentResolver().query(uri,
                                new String[]{android.provider.OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                            if (cursor == null || !cursor.moveToFirst()) throw new IOException("File name unavailable");
                            name = cursor.getString(0);
                        }
                        if (files.has(name)) throw new IOException("Duplicate PC file name");
                        byte[] bytes = readLimited(getContentResolver().openInputStream(uri), remaining);
                        remaining -= bytes.length;
                        files.put(name, new String(bytes, StandardCharsets.UTF_8));
                    }
                    reply(id, command("import_pc", new JSONObject().put("files", files).toString()));
                } else if (mode.equals("import") || mode.equals("design")) {
                    String text = new String(readLimited(getContentResolver().openInputStream(data.getData()), 2 * 1024 * 1024), StandardCharsets.UTF_8);
                    JSONObject args = new JSONObject().put(mode.equals("import") ? "text" : "design", mode.equals("import") ? text : new JSONObject(text));
                    reply(id, command(mode.equals("import") ? "import" : "design", args.toString()));
                } else if (mode.equals("report")) {
                    try (ZipOutputStream zip = new ZipOutputStream(getContentResolver().openOutputStream(data.getData(), "wt"))) {
                        JSONObject content = new JSONObject(report.toString());
                        content.put("application", "RFS Flightdeck Android " + BuildConfig.VERSION_NAME);
                        JSONArray attachments = new JSONArray();
                        if (consent) for (int i = 0; i < images.size(); i++) attachments.put(imageName(i));
                        content.put("attachments", attachments);
                        zip.putNextEntry(new ZipEntry("report.json"));
                        zip.write(content.toString(2).getBytes(StandardCharsets.UTF_8)); zip.closeEntry();
                        if (consent) for (int i = 0; i < images.size(); i++) {
                            zip.putNextEntry(new ZipEntry(imageName(i)));
                            zip.write(readLimited(getContentResolver().openInputStream(images.get(i)), 10 * 1024 * 1024)); zip.closeEntry();
                        }
                    }
                    reply(id, "{\"ok\":true,\"result\":{\"saved\":true}}");
                } else {
                    try (OutputStream out = getContentResolver().openOutputStream(data.getData(), "wt")) {
                        out.write(documentText.getBytes(StandardCharsets.UTF_8));
                    }
                    reply(id, "{\"ok\":true,\"result\":{\"saved\":true}}");
                }
            } catch (Exception e) { reply(id, error(e.toString())); }
        });
    }

    // Instrumentation uses the same serialized worker/engine as the UI.
    Future<String> requestForTest(String method, String payload) {
        return worker.submit(() -> command(method, payload));
    }
    WebView webForTest() { return web; }

    @Override protected void onDestroy() {
        worker.shutdown(); super.onDestroy();
    }
    @Override public void onBackPressed() {
        web.evaluateJavascript("window.goBack && window.goBack()", handled -> {
            if (!"true".equals(handled)) super.onBackPressed();
        });
    }
}
