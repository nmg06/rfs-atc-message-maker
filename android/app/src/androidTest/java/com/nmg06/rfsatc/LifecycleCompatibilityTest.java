package com.nmg06.rfsatc;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.view.WindowManager;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.Timeout;
import org.junit.runner.RunWith;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

/** Real WebView/engine/lifecycle callbacks. No remote services or general storage permissions. */
@RunWith(AndroidJUnit4.class)
public class LifecycleCompatibilityTest {
    @Rule public final Timeout boundedTest=Timeout.seconds(240);
    private MainActivity activity(ActivityScenario<MainActivity> scenario) {
        AtomicReference<MainActivity> result=new AtomicReference<>();
        scenario.onActivity(a->{a.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);result.set(a);});return result.get();
    }
    private JSONObject call(MainActivity a,String method,JSONObject value) throws Exception {
        JSONObject response=new JSONObject(a.requestForTest(method,value.toString()).get(180,TimeUnit.SECONDS));
        assertTrue(response.toString(),response.getBoolean("ok"));return response.getJSONObject("result");
    }
    private String javascript(MainActivity a,String code) throws Exception {
        AtomicReference<String> response=new AtomicReference<>();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->a.webForTest().evaluateJavascript(code,response::set));
        for(int i=0;i<300&&response.get()==null;i++)Thread.sleep(100);
        assertNotNull("JavaScript callback missing",response.get());return response.get();
    }
    private void visible(MainActivity a) throws Exception {
        for(int i=0;i<900;i++){if("true".equals(javascript(a,"typeof model!=='undefined' && model!==null && document.getElementById('route').textContent.includes(' → ')")))return;Thread.sleep(100);}
        fail("Application did not bootstrap in real WebView");
    }
    private void until(MainActivity a,String condition) throws Exception {
        for(int i=0;i<600;i++){if("true".equals(javascript(a,condition)))return;Thread.sleep(100);}fail("UI condition missing: "+condition);
    }
    private String read(File file) throws Exception {return read(new FileInputStream(file));}
    private String read(InputStream source) throws Exception {
        try(InputStream in=source;ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] bytes=new byte[8192];int count;while((count=in.read(bytes))!=-1)out.write(bytes,0,count);return new String(out.toByteArray(),StandardCharsets.UTF_8);
        }
    }
    private void write(File file,String text) throws Exception {try(OutputStream out=new FileOutputStream(file)){out.write(text.getBytes(StandardCharsets.UTF_8));}}
    private void result(MainActivity a,File file) {
        InstrumentationRegistry.getInstrumentation().runOnMainSync(()->a.onActivityResult(10,Activity.RESULT_OK,new Intent().setData(Uri.fromFile(file))));
    }
    @Test public void localFallbacksAndUnsupportedEngineMessagePreserveData() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            MainActivity a=activity(scenario);call(a,"bootstrap",new JSONObject());visible(a);
            String original=call(a,"export",new JSONObject()).getString("text");
            javascript(a,"(()=>{window.compatTest=undefined;const display=Intl.DisplayNames,replace=String.prototype.replaceAll,resume=window.FlightdeckNativeResume;Intl.DisplayNames=undefined;String.prototype.replaceAll=undefined;const script=document.createElement('script');script.src='compat.js';script.onload=()=>{try{window.compatTest=new Intl.DisplayNames(['en'],{type:'region'}).of('RO')==='Romania' && 'a.b.a.b'.replaceAll('.','X')==='aXbXaXb' && 'abc'.replaceAll('','-')==='-a-b-c-' && 'aba'.replaceAll('a','$&x')==='axbax';try{'a'.replaceAll(/a/,'b');window.compatTest=false;}catch(expected){}}finally{Intl.DisplayNames=display;String.prototype.replaceAll=replace;window.FlightdeckNativeResume=resume;script.remove();}};document.head.appendChild(script);})()");
            until(a,"window.compatTest===true");
            a.getSharedPreferences("interface",Context.MODE_PRIVATE).edit().putString("language","en").commit();
            a.new Bridge().compatibilityReady(false);
            AtomicReference<Boolean> message=new AtomicReference<>(false);
            for(int i=0;i<100&&!message.get();i++){
                scenario.onActivity(current->{android.view.ViewGroup decor=(android.view.ViewGroup)current.getWindow().getDecorView();message.set(containsText(decor,"newer Android System WebView"));});Thread.sleep(100);
            }
            assertTrue("Unsupported WebView needs a readable local recovery message",message.get());
            assertEquals("Compatibility guard must not modify flight data",new JSONObject(original).getJSONObject("payload").toString(),new JSONObject(call(a,"export",new JSONObject()).getString("text")).getJSONObject("payload").toString());
            a.new Bridge().compatibilityReady(true);visible(a);assertEquals(0,a.networkRequestsForTest());
            // A changed/corrupt previous private snapshot must be replaced from
            // the bundled asset at the next start, without touching the profile.
            // Only the dedicated emulator's installed DB is altered, never a source asset.
            JSONObject databaseManifest=new JSONObject(read(a.getAssets().open("database-manifest.json")));
            File installed=new File(a.getFilesDir(),"aviation.sqlite");write(installed,"OLD SNAPSHOT FIXTURE: REINSTALL FROM BUNDLED ASSET");
            scenario.recreate();MainActivity updated=activity(scenario);visible(updated);call(updated,"bootstrap",new JSONObject());
            java.security.MessageDigest digest=java.security.MessageDigest.getInstance("SHA-256");
            try(InputStream in=new FileInputStream(installed)){byte[] bytes=new byte[65536];int count;while((count=in.read(bytes))!=-1)digest.update(bytes,0,count);}
            StringBuilder checksum=new StringBuilder();for(byte value:digest.digest())checksum.append(String.format("%02x",value&255));
            assertEquals("Previous DB was not replaced with the actual verified asset",databaseManifest.getString("database_sha256"),checksum.toString());
            try(android.database.sqlite.SQLiteDatabase database=android.database.sqlite.SQLiteDatabase.openDatabase(installed.getAbsolutePath(),null,android.database.sqlite.SQLiteDatabase.OPEN_READONLY);
                android.database.Cursor integrity=database.rawQuery("PRAGMA integrity_check",null);
                android.database.Cursor schema=database.rawQuery("PRAGMA user_version",null)){
                assertTrue(integrity.moveToFirst());assertEquals("ok",integrity.getString(0));assertTrue(schema.moveToFirst());assertEquals(1,schema.getInt(0));
            }
            assertEquals("DB update must retain the exact current profile",new JSONObject(original).getJSONObject("payload").toString(),new JSONObject(call(updated,"export",new JSONObject()).getString("text")).getJSONObject("payload").toString());
            assertEquals("DB replacement must not download anything",0,updated.networkRequestsForTest());
        }
    }
    private boolean containsText(android.view.View view,String text){
        if(view instanceof android.widget.TextView&&((android.widget.TextView)view).getText().toString().contains(text))return true;
        if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++)if(containsText(group.getChildAt(i),text))return true;}return false;
    }
    @Test public void recreatedExportRetainsImmutableSnapshotAndRejectsSecondExport() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            MainActivity a=activity(scenario);call(a,"bootstrap",new JSONObject());visible(a);
            String text=call(a,"export",new JSONObject()).getString("text");
            a.reserveDocumentForTest("export",text).get(180,TimeUnit.SECONDS);
            a.new Bridge().request("98762","native.designExport","{\"design\":{\"name\":\"MUST NOT REPLACE FIRST EXPORT\"}}");
            call(a,"bootstrap",new JSONObject()); // Same worker: concurrent request has completed.
            scenario.recreate();MainActivity restored=activity(scenario);visible(restored);
            assertNotSame(a,restored);assertTrue(read(new File(restored.getFilesDir(),"native-session.json")).contains("rfs-flightdeck-backup"));
            File output=new File(restored.getFilesDir(),"lifecycle-export.json");result(restored,output);
            for(int i=0;i<300&&!output.isFile();i++)Thread.sleep(100);
            call(restored,"bootstrap",new JSONObject());assertEquals("Wrong export snapshot written after recreation",text,read(output));
            until(restored,"!document.getElementById('native-recovery-dialog')");
            assertEquals(0,restored.networkRequestsForTest());output.delete();
            // A valid image followed by an invalid one must not commit unseen
            // attachments. The provider exists solely in this test APK.
            Uri image=Uri.parse("content://"+LifecycleFixtures.AUTHORITY+"/image"),invalid=Uri.parse("content://"+LifecycleFixtures.AUTHORITY+"/invalid");
            restored.reserveDocumentForTest("images",null).get(180,TimeUnit.SECONDS);
            android.content.ClipData clips=android.content.ClipData.newUri(restored.getContentResolver(),"fixture",image);clips.addItem(new android.content.ClipData.Item(invalid));
            final MainActivity picker=restored;
            final Intent selectedImages=new Intent();selectedImages.setClipData(clips);
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->picker.onActivityResult(10,Activity.RESULT_OK,selectedImages));
            call(restored,"bootstrap",new JSONObject());assertEquals("Failed image selection retained a hidden attachment",0,new JSONObject(read(new File(restored.getFilesDir(),"native-session.json"))).getJSONArray("images").length());
            restored.reserveDocumentForTest("images",null).get(180,TimeUnit.SECONDS);
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->picker.onActivityResult(10,Activity.RESULT_OK,new Intent().setData(image)));
            call(restored,"bootstrap",new JSONObject());assertEquals(1,new JSONObject(read(new File(restored.getFilesDir(),"native-session.json"))).getJSONArray("images").length());
            JSONObject report=new JSONObject().put("summary","Original report").put("observed","Original observation");
            restored.reserveReportForTest(report,true).get(180,TimeUnit.SECONDS);scenario.recreate();restored=activity(scenario);visible(restored);
            restored.new Bridge().request("98764","native.clearImages","{}");call(restored,"bootstrap",new JSONObject());
            File zipFile=new File(restored.getFilesDir(),"lifecycle-report.zip");result(restored,zipFile);call(restored,"bootstrap",new JSONObject());
            boolean attachment=false,manifest=false;
            try(java.util.zip.ZipInputStream zip=new java.util.zip.ZipInputStream(new FileInputStream(zipFile))){
                java.util.zip.ZipEntry entry;while((entry=zip.getNextEntry())!=null){ByteArrayOutputStream content=new ByteArrayOutputStream();byte[] bytes=new byte[1024];int count;while((count=zip.read(bytes))!=-1)content.write(bytes,0,count);
                    if(entry.getName().equals("report.json")){JSONObject saved=new JSONObject(new String(content.toByteArray(),StandardCharsets.UTF_8));assertEquals("Original observation",saved.getString("observed"));assertEquals("image-1.png",saved.getJSONArray("attachments").getString(0));manifest=true;}
                    if(entry.getName().equals("image-1.png")){assertArrayEquals(LifecycleFixtures.PNG,content.toByteArray());attachment=true;}
                }
            }
            assertTrue("Report snapshot lost its consented attachment after recreation/clear",manifest&&attachment);zipFile.delete();
        }
    }
    @Test public void recreatedImportReopensPreviewWithoutApplyingAndMergeRetainsCurrentFlight() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            MainActivity a=activity(scenario);JSONObject bootstrap=call(a,"bootstrap",new JSONObject());visible(a);
            String original=call(a,"export",new JSONObject()).getString("text");
            try {
                JSONObject local=bootstrap.getJSONObject("value").getJSONObject("state");
                local.put("intro_seen",true).put("joke_seen",true).put("tutorial_seen",true).put("language","en");
                local.getJSONObject("flight").put("callsign","LOCAL-LIFECYCLE");
                javascript(a,"model.state="+local.toString()+";paint()");call(a,"save",new JSONObject().put("state",local));
                JSONObject incoming=new JSONObject(call(a,"export",new JSONObject()).getString("text"));
                incoming.getJSONObject("payload").getJSONObject("state").getJSONObject("flight").put("callsign","REMOTE-LIFECYCLE");
                File input=new File(a.getFilesDir(),"lifecycle-import.json");write(input,incoming.toString());
                a.reserveDocumentForTest("import",null).get(180,TimeUnit.SECONDS);
                scenario.recreate();MainActivity restored=activity(scenario);visible(restored);result(restored,input);
                until(restored,"Boolean(document.getElementById('backup-import-dialog'))");
                JSONObject before=call(restored,"bootstrap",new JSONObject()).getJSONObject("value").getJSONObject("state");
                assertEquals("Preview must never apply data automatically","LOCAL-LIFECYCLE",before.getJSONObject("flight").getString("callsign"));
                // Recreate once again with an already open import preview: retain the token/text,
                // reopen one dialog, and still ask the user to choose Merge/Replace.
                scenario.recreate();restored=activity(scenario);visible(restored);
                until(restored,"document.querySelectorAll('#backup-import-dialog').length===1");
                assertEquals("LOCAL-LIFECYCLE",call(restored,"bootstrap",new JSONObject()).getJSONObject("value").getJSONObject("state").getJSONObject("flight").getString("callsign"));
                javascript(restored,"document.getElementById('backup-merge').click()");
                until(restored,"!document.getElementById('backup-import-dialog') && !document.getElementById('native-recovery-dialog')");
                JSONObject after=call(restored,"bootstrap",new JSONObject()).getJSONObject("value").getJSONObject("state");
                assertEquals("LOCAL-LIFECYCLE",after.getJSONObject("flight").getString("callsign"));
                boolean imported=false;org.json.JSONArray flights=after.getJSONArray("saved_flights");
                for(int i=0;i<flights.length();i++)if("REMOTE-LIFECYCLE".equals(flights.getJSONObject(i).getJSONObject("flight").optString("callsign")))imported=true;
                assertTrue("Merge lost the incoming current flight",imported);assertEquals(0,restored.networkRequestsForTest());input.delete();
            } finally {MainActivity current=activity(scenario);JSONObject restored=call(current,"import",new JSONObject().put("text",original).put("mode","replace"));javascript(current,"setResult("+restored.toString()+");paint()");}
        }
    }
    @Test public void recreatedPermissionCallbackRetainsRequestedReminder() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            MainActivity a=activity(scenario);call(a,"bootstrap",new JSONObject());visible(a);
            long when=System.currentTimeMillis()+3600000;a.reserveReminderForTest(when,"LFPG → KJFK · lifecycle reminder").get(180,TimeUnit.SECONDS);
            scenario.recreate();MainActivity restored=activity(scenario);visible(restored);
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->restored.onRequestPermissionsResult(42,new String[]{"android.permission.POST_NOTIFICATIONS"},new int[]{android.content.pm.PackageManager.PERMISSION_GRANTED}));
            assertEquals(when,restored.getSharedPreferences("flight-reminder",0).getLong("when",0));
            assertEquals("LFPG → KJFK · lifecycle reminder",restored.getSharedPreferences("flight-reminder",0).getString("text",""));
            until(restored,"!document.getElementById('native-recovery-dialog')");assertEquals(0,restored.networkRequestsForTest());FlightReminder.cancel(restored);
        }
    }
}
