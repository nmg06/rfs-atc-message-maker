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
    // One engine queue per process: a recreated Activity must not initialise or
    // mutate the shared Python engine concurrently with its predecessor.
    private static final ExecutorService ENGINE_WORKER = Executors.newSingleThreadExecutor();
    private final ExecutorService worker = ENGINE_WORKER;
    private final java.util.concurrent.ThreadPoolExecutor network = new java.util.concurrent.ThreadPoolExecutor(3,3,0L,java.util.concurrent.TimeUnit.MILLISECONDS,new java.util.concurrent.ArrayBlockingQueue<>(24));
    private final OnlineMap online=new OnlineMap();
    private UpdateChecker updates;
    private WebView web;
    private FrameLayout root;
    private String startupError;
    private NativeSession session;
    private final String generation=java.util.UUID.randomUUID().toString();

    /** Payloads stay in private storage, never in Android's size-limited Bundle. */
    private static final class NativeSession {
        volatile MainActivity owner;
        volatile String pickerId;
        String pickerMode, pickerGeneration, documentText, importText, importToken, importGeneration;
        String reminderId, reminderText, reminderGeneration;
        long reminderWhen;
        JSONObject report;
        boolean consent;
        final List<Uri> images=new ArrayList<>();
        List<Uri> reportImages=new ArrayList<>();
        final List<JSONObject> completed=new ArrayList<>();
        synchronized JSONObject snapshot() throws Exception {
            JSONObject value=new JSONObject().put("format","flightdeck-native-session").put("schema",1)
                .put("pickerId",pickerId).put("pickerMode",pickerMode).put("pickerGeneration",pickerGeneration)
                .put("documentText",documentText).put("importText",importText).put("importToken",importToken)
                .put("importGeneration",importGeneration).put("reminderId",reminderId)
                .put("reminderText",reminderText).put("reminderGeneration",reminderGeneration)
                .put("reminderWhen",reminderWhen).put("report",report).put("consent",consent);
            JSONArray picked=new JSONArray(), attached=new JSONArray(), results=new JSONArray();
            for(Uri uri:images)picked.put(uri.toString());
            for(Uri uri:reportImages)attached.put(uri.toString());
            for(JSONObject result:completed)results.put(result);
            return value.put("images",picked).put("reportImages",attached).put("completed",results);
        }
        synchronized void restore(JSONObject value) throws Exception {
            if(!"flightdeck-native-session".equals(value.getString("format"))||value.getInt("schema")!=1)throw new IOException("Invalid native session");
            pickerId=nullable(value,"pickerId");pickerMode=nullable(value,"pickerMode");pickerGeneration=nullable(value,"pickerGeneration");
            documentText=nullable(value,"documentText");importText=nullable(value,"importText");importToken=nullable(value,"importToken");
            importGeneration=nullable(value,"importGeneration");reminderId=nullable(value,"reminderId");
            reminderText=nullable(value,"reminderText");reminderGeneration=nullable(value,"reminderGeneration");
            reminderWhen=value.optLong("reminderWhen");report=value.optJSONObject("report");consent=value.optBoolean("consent");
            for(String key:new String[]{"images","reportImages"}) {
                JSONArray list=value.optJSONArray(key);if(list==null)continue;
                if(list.length()>5)throw new IOException("Invalid image selection");
                List<Uri> target=key.equals("images")?images:reportImages;
                for(int i=0;i<list.length();i++)target.add(Uri.parse(list.getString(i)));
            }
            JSONArray results=value.optJSONArray("completed");
            if(results!=null)for(int i=0;i<Math.min(results.length(),8);i++)completed.add(results.getJSONObject(i));
        }
        private static String nullable(JSONObject value,String key){return value.isNull(key)?null:value.optString(key,null);}
    }

    private File sessionFile(){return new File(getFilesDir(),"native-session.json");}
    private void persistSession() {
        synchronized(session) {try {
            byte[] bytes=session.snapshot().toString().getBytes(StandardCharsets.UTF_8);
            android.util.AtomicFile file=new android.util.AtomicFile(sessionFile());
            FileOutputStream out=null;
            try {out=file.startWrite();out.write(bytes);file.finishWrite(out);}
            catch(Exception e){if(out!=null)file.failWrite(out);throw e;}
        } catch(Exception e) {android.util.Log.w("Flightdeck","Could not retain native operation",e);}}
    }
    @Override public Object onRetainNonConfigurationInstance(){return session;}
    @Override protected void onSaveInstanceState(Bundle saved){
        persistSession();saved.putBoolean("nativeSession",true);super.onSaveInstanceState(saved);
    }
    private void restoreSession(Bundle saved) {
        Object retained=getLastNonConfigurationInstance();
        session=retained instanceof NativeSession?(NativeSession)retained:new NativeSession();
        if(retained==null&&saved!=null&&saved.getBoolean("nativeSession")) {
            try {
                // openRead also recovers AtomicFile's older-Android .bak after an
                // interrupted write; reading its base file directly would bypass it.
                NativeSession restored=new NativeSession();
                restored.restore(new JSONObject(new String(readLimited(new android.util.AtomicFile(sessionFile()).openRead(),8*1024*1024),StandardCharsets.UTF_8)));
                session=restored;
            } catch(Exception e) {
                android.util.Log.w("Flightdeck","Native operation could not be restored",e);
                try{boolean english="en".equals(getSharedPreferences("interface",0).getString("language","fr"));session.completed.add(new JSONObject().put("mode","restore").put("response",new JSONObject().put("ok",false).put("error",english?"The interrupted file selection could not be restored. Please select the file again; your flight data has not been changed.":"La sélection interrompue n’a pas pu être reprise. Sélectionnez à nouveau le fichier ; les données de votre vol n’ont pas été modifiées.")));}catch(Exception ignored){}
            }
        }
        session.owner=this;
    }
    private void notifyResumedOperation(){
        runOnUiThread(()->{if(!isDestroyed()&&web!=null)web.evaluateJavascript("window.FlightdeckNativeResume && window.FlightdeckNativeResume()",null);});
    }
    private void operationReply(String id,String mode,String page,String json) {
        MainActivity active=session.owner;
        if(active==this&&!isDestroyed()&&generation.equals(page)){reply(id,json);return;}
        try {
            synchronized(session){session.completed.add(new JSONObject().put("mode",mode).put("response",new JSONObject(json)));}
            persistSession();if(active!=null)active.notifyResumedOperation();
        }catch(Exception e){android.util.Log.w("Flightdeck","Native operation result unavailable",e);}
    }
    private boolean supportedWebView() {
        android.content.pm.PackageInfo provider=androidx.webkit.WebViewCompat.getCurrentWebViewPackage(this);
        if(provider==null||provider.versionName==null)return false;
        try{return Integer.parseInt(provider.versionName.split("\\.")[0])>=80;}catch(Exception e){return false;}
    }
    private void showWebViewError() {
        final boolean english="en".equals(getSharedPreferences("interface",0).getString("language","fr"));
        android.widget.LinearLayout panel=new android.widget.LinearLayout(this);panel.setOrientation(1);panel.setPadding(24,32,24,24);
        android.widget.TextView message=new android.widget.TextView(this);message.setTextColor(0xffedf4fa);message.setTextSize(18);
        message.setText(english?"RFS Flightdeck needs a newer Android System WebView to display this application. Update Android System WebView or Chrome, then reopen the app. Your saved flights remain on this device.":"RFS Flightdeck a besoin d’un Android System WebView plus récent pour afficher l’application. Mettez à jour Android System WebView ou Chrome, puis relancez l’application. Vos vols sauvegardés restent sur cet appareil.");
        panel.addView(message);android.widget.Button button=new android.widget.Button(this);button.setText(english?"Open Android settings":"Ouvrir les paramètres Android");
        button.setOnClickListener(v->{try{startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+(androidx.webkit.WebViewCompat.getCurrentWebViewPackage(this)==null?getPackageName():androidx.webkit.WebViewCompat.getCurrentWebViewPackage(this).packageName))));}catch(Exception ignored){startActivity(new Intent(android.provider.Settings.ACTION_SETTINGS));}});
        panel.addView(button);root.removeAllViews();root.addView(panel,new FrameLayout.LayoutParams(-1,-1));
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        restoreSession(saved);
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
        if(!supportedWebView()){showWebViewError();return;}
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
        web.loadUrl(ORIGIN + "/assets/www/compat-check.html");
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
        @JavascriptInterface public String countryNames() {
            JSONObject names=new JSONObject();
            try{for(String country:java.util.Locale.getISOCountries())names.put(country,new java.util.Locale("",country).getDisplayCountry(java.util.Locale.ENGLISH));names.put("XK","Kosovo");}catch(Exception ignored){}
            return names.toString();
        }
        @JavascriptInterface public void compatibilityReady(boolean supported) {
            runOnUiThread(()->{if(isDestroyed())return;if(supported)web.loadUrl(ORIGIN+"/assets/www/index.html");else showWebViewError();});
        }
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
        if(session.pickerId!=null && java.util.Arrays.asList("native.export","native.import","native.pcImport","native.designExport","native.designImport","native.images","native.report").contains(method)) {
            reply(id,error("A document selection is already open"));return;
        }
        switch (method) {
            case "native.resume": {
                JSONArray values=new JSONArray(), names=new JSONArray();
                synchronized(session){
                    for(JSONObject result:session.completed){values.put(result);if("import".equals(result.optString("mode"))&&result.getJSONObject("response").optBoolean("ok"))session.importGeneration=generation;}
                    session.completed.clear();
                }
                if(session.importText!=null&&session.importToken!=null&&!generation.equals(session.importGeneration)) {
                    JSONObject preview=new JSONObject(command("import_preview",new JSONObject().put("text",session.importText).toString()));
                    if(preview.optBoolean("ok"))values.put(new JSONObject().put("mode","import").put("response",new JSONObject().put("ok",true).put("result",new JSONObject().put("import_preview",preview.getJSONObject("result")).put("token",session.importToken))));
                    session.importGeneration=generation;
                }
                for(int i=0;i<session.images.size();i++)names.put("image-"+(i+1));
                persistSession();reply(id,new JSONObject().put("ok",true).put("result",new JSONObject().put("completed",values).put("images",names).put("pending",session.pickerId!=null||session.reminderId!=null)).toString());break;
            }
            case "native.updatesGet": reply(id,new JSONObject().put("ok",true).put("result",updates.get()).toString());break;
            case "native.updatesConfigure": reply(id,new JSONObject().put("ok",true).put("result",updates.configure(args.getBoolean("enabled"))).toString());break;
            case "native.updatesOpen": {
                String target=updates.approvedDownload(args.getString("url"));
                runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(target)));reply(id,"{\"ok\":true,\"result\":{}}");}catch(Exception e){reply(id,error("Could not open download"));}});
                break;
            }
            case "native.importCancel": session.importText=null;session.importToken=null;persistSession();reply(id,"{\"ok\":true,\"result\":{}}");break;
            case "native.importApply": {
                if(session.importText==null||session.importToken==null||!session.importToken.equals(args.getString("token")))throw new IllegalArgumentException("Select a backup first");
                String mode=args.getString("mode");if(!mode.equals("merge")&&!mode.equals("replace"))throw new IllegalArgumentException("Unknown import mode");
                String response=command("import",new JSONObject().put("text",session.importText).put("mode",mode).toString());
                if(new JSONObject(response).getBoolean("ok")){session.importText=null;session.importToken=null;persistSession();}
                operationReply(id,"importApply",generation,response);break;
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
                    if(session.reminderId!=null)throw new IllegalStateException("Notification permission request already open");
                    session.reminderWhen=when;session.reminderText=text;session.reminderGeneration=generation;session.reminderId=id;persistSession();runOnUiThread(()->requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},42));
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
                session.documentText = result.getJSONObject("result").getString("text");
                picker(id, "export", "application/json", "rfs-flightdeck-backup.json"); break;
            }
            case "native.import": session.importText=null;session.importToken=null;picker(id, "import", "application/json", null); break;
            case "native.pcImport": picker(id, "pcImport", "application/json", null); break;
            case "native.designExport": {
                session.documentText = args.getJSONObject("design").toString(2);
                picker(id, "export", "application/json", "rfs-design.json"); break;
            }
            case "native.designImport": picker(id, "design", "application/json", null); break;
            case "native.images": picker(id, "images", "image/*", null); break;
            case "native.clearImages":
                for(Uri uri:session.images)if(!session.reportImages.contains(uri))try{getContentResolver().releasePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException ignored){}
                session.images.clear();persistSession();reply(id, "{\"ok\":true,\"result\":{\"images\":[]}}"); break;
            case "native.report": {
                session.report = args.getJSONObject("report"); session.consent = args.optBoolean("consent", false);
                session.reportImages=new ArrayList<>(session.images);
                if (session.report.optString("summary").trim().isEmpty() || session.report.optString("observed").trim().isEmpty()) throw new IllegalArgumentException("Summary and observed result required");
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
        if(session.pickerId!=null){reply(id,error("A document selection is already open"));return;}
        session.pickerMode=mode;session.pickerGeneration=generation;session.pickerId=id;persistSession();
        runOnUiThread(() -> {
            Intent intent = new Intent(name == null ? Intent.ACTION_OPEN_DOCUMENT : Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE).setType(mime);
            if (name != null) intent.putExtra(Intent.EXTRA_TITLE, name);
            if (mode.equals("images") || mode.equals("pcImport")) intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
            try { startActivityForResult(intent, DOCUMENT); }
            catch (Exception e) {session.pickerId=null;persistSession();operationReply(id,mode,session.pickerGeneration,error(e.toString()));}
        });
    }

    private String imageName(int index) {
        return imageName(index,session.images);
    }
    private String imageName(int index,List<Uri> source) {
        String mime = getContentResolver().getType(source.get(index));
        String extension = android.webkit.MimeTypeMap.getSingleton().getExtensionFromMimeType(mime);
        return "image-" + (index + 1) + (extension == null ? "" : "." + extension);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != DOCUMENT || session.pickerId == null) return;
        String id=session.pickerId,mode=session.pickerMode,selectedText=session.documentText,page=session.pickerGeneration;
        final JSONObject selectedReport=session.report;
        final boolean selectedConsent=session.consent;
        final List<Uri> selectedImages=new ArrayList<>(session.reportImages);
        session.pickerId=null;persistSession();
        if (result != RESULT_OK || data == null) { operationReply(id,mode,page, "{\"ok\":true,\"result\":{\"cancelled\":true}}"); return; }
        worker.execute(() -> {
            try {
                if (mode.equals("images")) {
                    ClipData clips = data.getClipData();
                    List<Uri> selected = new ArrayList<>();
                    if (clips == null) selected.add(data.getData());
                    else for (int i = 0; i < clips.getItemCount(); i++) selected.add(clips.getItemAt(i).getUri());
                    // Validate the full accepted selection before committing it. If a
                    // provider returns a bad/oversized image, never retain unseen partial
                    // attachments after reporting an error to the user.
                    List<Uri> accepted=new ArrayList<>(session.images);
                    for (Uri uri : selected) {
                        if(accepted.contains(uri))continue;
                        if(accepted.size()>=5)break;
                        if(uri==null)throw new IOException("Image required");
                        String mime=getContentResolver().getType(uri);
                        if(mime==null||!mime.startsWith("image/"))throw new IOException("Image required");
                        readLimited(getContentResolver().openInputStream(uri),10*1024*1024);accepted.add(uri);
                    }
                    int flags=data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
                    if(flags!=0)for(Uri uri:accepted)if(!session.images.contains(uri))try{getContentResolver().takePersistableUriPermission(uri,flags);}catch(SecurityException ignored){}
                    session.images.clear();session.images.addAll(accepted);persistSession();
                    JSONArray list = new JSONArray();
                    for (int i = 0; i < session.images.size(); i++) list.put("image-" + (i + 1));
                    operationReply(id,mode,page, new JSONObject().put("ok", true).put("result", new JSONObject().put("images", list)).toString());
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
                    operationReply(id,mode,page, command("import_pc", new JSONObject().put("files", files).toString()));
                } else if (mode.equals("import")) {
                    String text=new String(readLimited(getContentResolver().openInputStream(data.getData()),2*1024*1024),StandardCharsets.UTF_8);
                    JSONObject preview=new JSONObject(command("import_preview",new JSONObject().put("text",text).toString()));
                    if(!preview.getBoolean("ok")){operationReply(id,mode,page,preview.toString());return;}
                    session.importText=text;session.importGeneration=page;session.importToken=java.util.UUID.randomUUID().toString();persistSession();
                    operationReply(id,mode,page,new JSONObject().put("ok",true).put("result",new JSONObject().put("import_preview",preview.getJSONObject("result")).put("token",session.importToken)).toString());
                } else if (mode.equals("design")) {
                    String text = new String(readLimited(getContentResolver().openInputStream(data.getData()), 2 * 1024 * 1024), StandardCharsets.UTF_8);
                    JSONObject args = new JSONObject().put(mode.equals("import") ? "text" : "design", mode.equals("import") ? text : new JSONObject(text));
                    operationReply(id,mode,page, command(mode.equals("import") ? "import" : "design", args.toString()));
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
                    operationReply(id,mode,page, "{\"ok\":true,\"result\":{\"saved\":true}}");
                } else {
                    try (OutputStream out = getContentResolver().openOutputStream(data.getData(), "wt")) {
                        out.write(selectedText.getBytes(StandardCharsets.UTF_8));
                    }
                    operationReply(id,mode,page, "{\"ok\":true,\"result\":{\"saved\":true}}");
                }
            } catch (Exception e) { operationReply(id,mode,page, error(e.toString())); }
            finally {
                if(mode.equals("report")) {
                    for(Uri uri:selectedImages)if(!session.images.contains(uri))try{getContentResolver().releasePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(SecurityException ignored){}
                    session.reportImages.clear();persistSession();
                }
            }
        });
    }

    // Instrumentation uses the same serialized worker/engine as the UI.
    Future<String> requestForTest(String method, String payload) {
        return worker.submit(() -> command(method, payload));
    }
    // Deterministic instrumentation reserves the same operation/snapshot, then
    // delivers a real URI through onActivityResult after ActivityScenario.recreate.
    Future<?> reserveDocumentForTest(String mode,String text) {
        return worker.submit(()->{session.documentText=text;session.pickerMode=mode;session.pickerGeneration=generation;session.pickerId="98760";persistSession();});
    }
    Future<?> reserveReportForTest(JSONObject report,boolean consent) {
        return worker.submit(()->{session.report=report;session.consent=consent;session.reportImages=new ArrayList<>(session.images);session.pickerMode="report";session.pickerGeneration=generation;session.pickerId="98763";persistSession();});
    }
    Future<?> reserveReminderForTest(long when,String text) {
        return worker.submit(()->{session.reminderWhen=when;session.reminderText=text;session.reminderGeneration=generation;session.reminderId="98761";persistSession();});
    }
    WebView webForTest() { return web; }
    int networkRequestsForTest(){return online.requestCount();}
    int updateRequestsForTest(){return updates.requestCount();}
    JSONObject updatePolicyForTest() throws Exception{return updates.get();}
    JSONObject checkUpdatesForTest(boolean automatic) throws Exception{return updates.check(automatic);}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants){
        super.onRequestPermissionsResult(request,permissions,grants);
        if(request==42&&session.reminderId!=null){
            String id=session.reminderId,page=session.reminderGeneration;session.reminderId=null;persistSession();
            if(grants.length>0&&grants[0]==android.content.pm.PackageManager.PERMISSION_GRANTED){FlightReminder.schedule(this,session.reminderWhen,session.reminderText);operationReply(id,"reminder",page,"{\"ok\":true,\"result\":{}}");}
            else operationReply(id,"reminder",page,error("Notifications disabled. No reminder scheduled."));
        }
    }

    @Override protected void onPause() {
        if(web!=null)web.evaluateJavascript("window.flushState && window.flushState()",null);
        super.onPause();
    }

    @Override protected void onDestroy() {
        online.enabled=false;network.shutdownNow();
        // Release the JS timers and native bridge with their Activity.
        if(web!=null){web.removeJavascriptInterface("Android");web.stopLoading();web.destroy();}
        super.onDestroy();
    }
    @Override public void onBackPressed() {
        if(web==null||startupError!=null){super.onBackPressed();return;}
        web.evaluateJavascript("window.goBack && window.goBack()", handled -> {
            if (!"true".equals(handled)) super.onBackPressed();
        });
    }
}
