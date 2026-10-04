package com.nmg06.rfsatc;

import android.content.Context;
import android.content.SharedPreferences;
import com.chaquo.python.Python;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

/** Optional public release metadata only. Never downloads or installs an APK. */
final class UpdateChecker {
    private static final String ENDPOINT="https://api.github.com/repos/nmg06/rfs-atc-message-maker/releases?per_page=100";
    private static final long DAY=86400000L;
    private static final int LIMIT=2*1024*1024;
    private final SharedPreferences prefs;
    private int requests;

    UpdateChecker(Context context) { prefs=context.getSharedPreferences("updates",Context.MODE_PRIVATE); }
    synchronized int requestCount() { return requests; }
    private JSONObject cachedResult() throws Exception {
        JSONObject cached;
        try { cached=new JSONObject(prefs.getString("last_result","{}")); }
        catch(org.json.JSONException error) { return new JSONObject().put("status","unavailable").put("reason","invalid_cache"); }
        if(cached.length()==0)return cached;
        Python python=Python.getInstance();
        com.chaquo.python.PyObject policy=python.getModule("json").callAttr("loads",
            new JSONObject().put("last_result",cached).toString());
        com.chaquo.python.PyObject normalised=python.getModule("updates").callAttr("normalise_preferences",policy,BuildConfig.VERSION_NAME);
        return new JSONObject(python.getModule("json").callAttr("dumps",normalised).toString()).getJSONObject("last_result");
    }
    JSONObject get() throws Exception {
        return new JSONObject().put("version",BuildConfig.VERSION_NAME)
            .put("enabled",prefs.getBoolean("enabled",false))
            .put("last_attempt",prefs.getLong("last_attempt",0))
            .put("last_result",cachedResult());
    }
    JSONObject configure(boolean enabled) throws Exception {
        prefs.edit().putBoolean("enabled",enabled).apply();
        return get();
    }
    synchronized JSONObject check(boolean automatic) throws Exception {
        long now=System.currentTimeMillis(), previous=prefs.getLong("last_attempt",0);
        if(automatic && (!prefs.getBoolean("enabled",false) || (previous>0 && now-previous<DAY)))
            return new JSONObject().put("status","skipped");
        prefs.edit().putLong("last_attempt",now).apply();
        JSONObject result;
        HttpURLConnection connection=null;
        try {
            connection=(HttpURLConnection)new URL(ENDPOINT).openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(6000); connection.setReadTimeout(6000);
            connection.setRequestProperty("Accept","application/vnd.github+json");
            connection.setRequestProperty("User-Agent","RFSFlightdeck-update-check");
            connection.setRequestProperty("X-GitHub-Api-Version","2022-11-28");
            requests++;
            if(connection.getResponseCode()!=200)throw new java.io.IOException("Release metadata unavailable");
            byte[] raw;
            try(InputStream input=connection.getInputStream();ByteArrayOutputStream output=new ByteArrayOutputStream()) {
                byte[] buffer=new byte[8192];int n;
                while((n=input.read(buffer))!=-1) {
                    if(output.size()+n>LIMIT)throw new java.io.IOException("Release metadata too large");
                    output.write(buffer,0,n);
                }
                raw=output.toByteArray();
            }
            Python python=Python.getInstance();
            com.chaquo.python.PyObject releases=python.getModule("json").callAttr("loads",new String(raw,StandardCharsets.UTF_8));
            com.chaquo.python.PyObject selected=python.getModule("updates").callAttr("select_release",releases,"android");
            result=new JSONObject(python.getModule("json").callAttr("dumps",selected).toString());
        } catch(Exception error) {
            result=new JSONObject().put("status","unavailable").put("reason","network");
        } finally { if(connection!=null)connection.disconnect(); }
        prefs.edit().putString("last_result",result.toString()).apply();
        return result;
    }
    String approvedDownload(String location) throws Exception {
        JSONObject result=cachedResult();
        if(!"available".equals(result.optString("status")) || !location.equals(result.optString("download_url")))
            throw new IllegalArgumentException("No checked download available");
        URL url=new URL(location);
        if(!"https".equals(url.getProtocol()) || !"github.com".equals(url.getHost()) || url.getUserInfo()!=null
            || url.getPort()!=-1 || !url.getPath().startsWith("/nmg06/rfs-atc-message-maker/releases/download/"))
            throw new IllegalArgumentException("Unsupported download source");
        return location;
    }
}
