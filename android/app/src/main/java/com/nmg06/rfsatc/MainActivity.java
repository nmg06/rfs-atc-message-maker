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
import android.widget.FrameLayout;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.graphics.Insets;
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
    private final java.util.concurrent.ThreadPoolExecutor network = new java.util.concurrent.ThreadPoolExecutor(3,3,0L,java.util.concurrent.TimeUnit.MILLISECONDS,new java.util.concurrent.ArrayBlockingQueue<>(24));
    private final OnlineMap online=new OnlineMap();
    private UpdateChecker updates;
    private String importText, importToken;
    private String reminderId;
    private long reminderWhen;
    private String reminderText;
    private final List<Uri> images = new ArrayList<>();
    private WebView web;
    private FrameLayout root;
    private String startupError;
    private volatile String pickerId;
    private String pickerMode, documentText;
    private JSONObject report;
    private List<Uri> reportImages=new ArrayList<>();
    private boolean consent;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        updates=new UpdateChecker(this);
        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(getWindow(),false);
        web = new WebView(this);
        web.setBackgroundColor(0xff10151d);
        // Padding on WebView does not inset its CSS viewport/fixed navigation.
        // Give the WebView a genuinely smaller viewport through its parent.
        root = new FrameLayout(this);
        root.setBackgroundColor(0xff10151d);
        root.addView(web,new FrameLayout.LayoutParams(-1,-1));
        ViewCompat.setOnApplyWindowInsetsListener(root,(view,insets)->{
            Insets bars=insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            Insets ime=insets.getInsets(WindowInsetsCompat.Type.ime());
            view.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,ime.bottom));
            return WindowInsetsCompat.CONSUMED;
        });
        setContentView(root);
        ViewCompat.requestApplyInsets(root);
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
            if(method.equals("native.updatesCheck")) {
                try{network.execute(()->{try{reply(id,new JSONObject().put("ok",true).put("result",updates.check(new JSONObject(payload).optBoolean("automatic",false))).toString());}catch(Exception e){reply(id,error("Update check unavailable"));}});}
                catch(java.util.concurrent.RejectedExecutionException e){reply(id,error("Update check busy"));}
                return;
            }
            if(method.equals("native.tile")||method.equals("native.wind")){
                try{network.execute(()->{try{reply(id,new JSONObject().put("ok",true).put("result",online.request(method,new JSONObject(payload))).toString());}catch(Exception e){reply(id,error(e.toString()));}});}
                catch(java.util.concurrent.RejectedExecutionException e){reply(id,error("Map request queue full"));}
                return;
            }
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
        // Reserve a picker before computing/replacing its payload. A rejected
        // second export must never change the file the first export will write.
        if(pickerId!=null && java.util.Arrays.asList("native.export","native.import","native.pcImport","native.designExport","native.designImport","native.images","native.report").contains(method)) {
            reply(id,error("A document selection is already open"));return;
        }
        switch (method) {
            case "native.updatesGet": reply(id,new JSONObject().put("ok",true).put("result",updates.get()).toString());break;
            case "native.updatesConfigure": reply(id,new JSONObject().put("ok",true).put("result",updates.configure(args.getBoolean("enabled"))).toString());break;
            case "native.updatesOpen": {
                String target=updates.approvedDownload(args.getString("url"));
                runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(target)));reply(id,"{\"ok\":true,\"result\":{}}");}catch(Exception e){reply(id,error("Could not open download"));}});
                break;
            }
            case "native.importCancel": importText=null;importToken=null;reply(id,"{\"ok\":true,\"result\":{}}");break;
            case "native.importApply": {
                if(importText==null||importToken==null||!importToken.equals(args.getString("token")))throw new IllegalArgumentException("Select a backup first");
                String mode=args.getString("mode");if(!mode.equals("merge")&&!mode.equals("replace"))throw new IllegalArgumentException("Unknown import mode");
                String response=command("import",new JSONObject().put("text",importText).put("mode",mode).toString());
                if(new JSONObject(response).getBoolean("ok")){importText=null;importToken=null;}
                reply(id,response);break;
            }
            case "native.finish":
                // Called only after the UI has awaited its final atomic save.
                reply(id,"{\"ok\":true,\"result\":{}}");
                runOnUiThread(this::finish);
                break;
            case "native.online": online.enabled=args.getBoolean("enabled");reply(id,"{\"ok\":true,\"result\":{}}");break;
            case "native.appearance": {
                int color=android.graphics.Color.parseColor(args.getString("color"));boolean light=args.optBoolean("light");
                String locale=args.optString("language","fr");
                if(!locale.equals("fr")&&!locale.equals("en"))throw new IllegalArgumentException("Unknown language");
                android.content.SharedPreferences preferences=getSharedPreferences("interface",0);
                if(!locale.equals(preferences.getString("language","fr")))preferences.edit().putString("language",locale).apply();
                runOnUiThread(()->{
                    root.setBackgroundColor(color);
                    // API 35 uses transparent bars over the parent. Older
                    // versions honour these colours and need matching contrast.
                    getWindow().setStatusBarColor(color);
                    getWindow().setNavigationBarColor(light&&android.os.Build.VERSION.SDK_INT<26?0xff10151d:color);
                    androidx.core.view.WindowInsetsControllerCompat controller=new androidx.core.view.WindowInsetsControllerCompat(getWindow(),root);
                    controller.setAppearanceLightStatusBars(light);controller.setAppearanceLightNavigationBars(light);
                });
                reply(id,"{\"ok\":true,\"result\":{}}");break;
            }
            case "native.icon": {
                String selected=args.getString("icon");if(!java.util.Arrays.asList("Default","Ocean","Sunset").contains(selected))throw new IllegalArgumentException("Unknown icon");
                android.content.pm.PackageManager pm=getPackageManager();
                // Enable the new alias before disabling others: never lose launch access.
                pm.setComponentEnabledSetting(new android.content.ComponentName(this,getPackageName()+".Icon"+selected),android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_ENABLED,android.content.pm.PackageManager.DONT_KILL_APP);
                for(String name:new String[]{"Default","Ocean","Sunset"})if(!name.equals(selected))pm.setComponentEnabledSetting(new android.content.ComponentName(this,getPackageName()+".Icon"+name),android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_DISABLED,android.content.pm.PackageManager.DONT_KILL_APP);
                reply(id,"{\"ok\":true,\"result\":{}}");break;
            }
            case "native.reminderCancel": FlightReminder.cancel(this);reply(id,"{\"ok\":true,\"result\":{}}");break;
            case "native.reminder": {
                long when=args.getLong("when");String text=args.getString("text");
                if(when<=System.currentTimeMillis()||when>System.currentTimeMillis()+365L*86400000||text.length()>1000)throw new IllegalArgumentException("Invalid reminder");
                if(android.os.Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED){
                    if(reminderId!=null)throw new IllegalStateException("Notification permission request already open");
                    reminderId=id;reminderWhen=when;reminderText=text;runOnUiThread(()->requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},42));
                }else{FlightReminder.schedule(this,when,text);reply(id,"{\"ok\":true,\"result\":{}}");}break;
            }
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
                picker(id, "export", "application/json", "rfs-flightdeck-backup.json"); break;
            }
            case "native.import": importText=null;importToken=null;picker(id, "import", "application/json", null); break;
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
                reportImages=new ArrayList<>(images);
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
        if(pickerId!=null){reply(id,error("A document selection is already open"));return;}
        pickerId=id;pickerMode=mode;
        runOnUiThread(() -> {
            Intent intent = new Intent(name == null ? Intent.ACTION_OPEN_DOCUMENT : Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE).setType(mime);
            if (name != null) intent.putExtra(Intent.EXTRA_TITLE, name);
            if (mode.equals("images") || mode.equals("pcImport")) intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
            try { startActivityForResult(intent, DOCUMENT); }
            catch (Exception e) { pickerId = null; reply(id, error(e.toString())); }
        });
    }

    private String imageName(int index) {
        return imageName(index,images);
    }
    private String imageName(int index,List<Uri> source) {
        String mime = getContentResolver().getType(source.get(index));
        String extension = android.webkit.MimeTypeMap.getSingleton().getExtensionFromMimeType(mime);
        return "image-" + (index + 1) + (extension == null ? "" : "." + extension);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != DOCUMENT || pickerId == null) return;
        String id=pickerId,mode=pickerMode,selectedText=documentText;
        final JSONObject selectedReport=report;
        final boolean selectedConsent=consent;
        final List<Uri> selectedImages=new ArrayList<>(reportImages);
        pickerId=null;
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
                } else if (mode.equals("import")) {
                    String text=new String(readLimited(getContentResolver().openInputStream(data.getData()),2*1024*1024),StandardCharsets.UTF_8);
                    JSONObject preview=new JSONObject(command("import_preview",new JSONObject().put("text",text).toString()));
                    if(!preview.getBoolean("ok")){reply(id,preview.toString());return;}
                    importText=text;importToken=java.util.UUID.randomUUID().toString();
                    reply(id,new JSONObject().put("ok",true).put("result",new JSONObject().put("import_preview",preview.getJSONObject("result")).put("token",importToken)).toString());
                } else if (mode.equals("design")) {
                    String text = new String(readLimited(getContentResolver().openInputStream(data.getData()), 2 * 1024 * 1024), StandardCharsets.UTF_8);
                    JSONObject args = new JSONObject().put(mode.equals("import") ? "text" : "design", mode.equals("import") ? text : new JSONObject(text));
                    reply(id, command(mode.equals("import") ? "import" : "design", args.toString()));
                } else if (mode.equals("report")) {
                    try (ZipOutputStream zip = new ZipOutputStream(getContentResolver().openOutputStream(data.getData(), "wt"))) {
                        JSONObject content = new JSONObject(selectedReport.toString());
                        content.put("application", "RFS Flightdeck Android " + BuildConfig.VERSION_NAME);
                        JSONArray attachments = new JSONArray();
                        if (selectedConsent) for (int i = 0; i < selectedImages.size(); i++) attachments.put(imageName(i,selectedImages));
                        content.put("attachments", attachments);
                        zip.putNextEntry(new ZipEntry("report.json"));
                        zip.write(content.toString(2).getBytes(StandardCharsets.UTF_8)); zip.closeEntry();
                        if (selectedConsent) for (int i = 0; i < selectedImages.size(); i++) {
                            zip.putNextEntry(new ZipEntry(imageName(i,selectedImages)));
                            zip.write(readLimited(getContentResolver().openInputStream(selectedImages.get(i)), 10 * 1024 * 1024)); zip.closeEntry();
                        }
                    }
                    reply(id, "{\"ok\":true,\"result\":{\"saved\":true}}");
                } else {
                    try (OutputStream out = getContentResolver().openOutputStream(data.getData(), "wt")) {
                        out.write(selectedText.getBytes(StandardCharsets.UTF_8));
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
    int networkRequestsForTest(){return online.requestCount();}
    int updateRequestsForTest(){return updates.requestCount();}
    JSONObject updatePolicyForTest() throws Exception{return updates.get();}
    JSONObject checkUpdatesForTest(boolean automatic) throws Exception{return updates.check(automatic);}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants){
        super.onRequestPermissionsResult(request,permissions,grants);
        if(request==42&&reminderId!=null){String id=reminderId;reminderId=null;if(grants.length>0&&grants[0]==android.content.pm.PackageManager.PERMISSION_GRANTED){FlightReminder.schedule(this,reminderWhen,reminderText);reply(id,"{\"ok\":true,\"result\":{}}");}else reply(id,error("Notifications disabled. No reminder scheduled."));}
    }

    @Override protected void onPause() {
        if(web!=null)web.evaluateJavascript("window.flushState && window.flushState()",null);
        super.onPause();
    }

    @Override protected void onDestroy() {
        online.enabled=false;network.shutdownNow();
        // Release the JS timers and native bridge with their Activity.
        if(web!=null){web.removeJavascriptInterface("Android");web.stopLoading();web.destroy();}
        worker.shutdown(); super.onDestroy();
    }
    @Override public void onBackPressed() {
        web.evaluateJavascript("window.goBack && window.goBack()", handled -> {
            if (!"true".equals(handled)) super.onBackPressed();
        });
    }
}
