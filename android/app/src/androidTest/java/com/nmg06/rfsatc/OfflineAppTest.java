package com.nmg06.rfsatc;

import android.content.ClipboardManager;
import android.content.Context;
import android.view.WindowManager;
import android.os.ParcelFileDescriptor;
import java.io.FileInputStream;
import java.nio.charset.StandardCharsets;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.Before;
import org.junit.runner.RunWith;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class OfflineAppTest {
    private String shell(String command) throws Exception {
        try (ParcelFileDescriptor descriptor=InstrumentationRegistry.getInstrumentation()
                .getUiAutomation().executeShellCommand(command);
             FileInputStream stream=new FileInputStream(descriptor.getFileDescriptor())) {
            return new String(stream.readAllBytes(),StandardCharsets.UTF_8);
        }
    }
    @Before public void prepareForeground() throws Exception {
        // Dedicated test device only. Reset the lock screen/previous clipboard
        // overlay before each ActivityScenario, rather than relying on boot focus.
        shell("input keyevent KEYCODE_WAKEUP");
        shell("wm dismiss-keyguard");
        shell("input keyevent KEYCODE_HOME");
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
    }
    private MainActivity activity(ActivityScenario<MainActivity> scenario) {
        AtomicReference<MainActivity> result = new AtomicReference<>();
        scenario.onActivity(a -> {
            // Only this test activity: slow emulator work must not let the screen
            // lock and remove focus required by Android's clipboard privacy rule.
            a.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            if (android.os.Build.VERSION.SDK_INT >= 27) {
                a.setShowWhenLocked(true); a.setTurnScreenOn(true);
            }
            result.set(a);
        });
        return result.get();
    }
    private JSONObject call(MainActivity a, String method, JSONObject args) throws Exception {
        JSONObject envelope = new JSONObject(a.requestForTest(method,args.toString()).get(120,TimeUnit.SECONDS));
        assertTrue(envelope.optString("error"),envelope.getBoolean("ok"));
        return envelope.getJSONObject("result");
    }
    @Test public void offlineMapRendersLocalBordersRouteAndCountrySelection() throws Exception {
        try (ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            MainActivity a=activity(scenario);
            JSONObject original=call(a,"bootstrap",new JSONObject()).getJSONObject("value");
            try {
                JSONObject state=new JSONObject(original.getJSONObject("state").toString());
                state.put("intro_seen",true).put("joke_seen",true);
                state.getJSONObject("flight").put("departure_icao","LFPG").put("arrival_icao","KJFK");
                call(a,"save",new JSONObject().put("state",state));
                assertEquals(97,call(a,"map_route",new JSONObject()).getJSONArray("route").length());
                AtomicReference<String> ready=new AtomicReference<>("false");
                for(int i=0;i<300;i++) {
                    InstrumentationRegistry.getInstrumentation().runOnMainSync(()->a.webForTest().evaluateJavascript(
                        "typeof rpc==='function' && typeof model!=='undefined' && Boolean(model)", ready::set));
                    if("true".equals(ready.get()))break;
                    Thread.sleep(100);
                }
                assertEquals("WebView bootstrap unavailable", "true",ready.get());
                InstrumentationRegistry.getInstrumentation().runOnMainSync(()->a.webForTest().evaluateJavascript(
                    "rpc('bootstrap').then(r=>{setResult(r);screen='map';paint();})",null));
                AtomicReference<String> rendered=new AtomicReference<>("false");
                String assertion="Boolean(mobileMap && countryGeometry && countryGeometry.length===242 && mobileMap.data.route.length===97 && mobileMap.canvas.width>0)";
                for(int i=0;i<600;i++) {
                    InstrumentationRegistry.getInstrumentation().runOnMainSync(()->a.webForTest().evaluateJavascript(assertion,rendered::set));
                    if("true".equals(rendered.get()))break;
                    Thread.sleep(100);
                }
                assertEquals("Actual offline WebView map did not render", "true",rendered.get());
                AtomicReference<String> country=new AtomicReference<>();
                InstrumentationRegistry.getInstrumentation().runOnMainSync(()->a.webForTest().evaluateJavascript(
                    "(()=>{const s=mobileMap.scale(),p=[mobileMap.canvas.clientWidth/2+(2.3522-mobileMap.center[0])*s,mobileMap.canvas.clientHeight/2+(MapProjection.y(48.8566)-mobileMap.center[1])*s];return mobileMap.countryAt(p);})()",country::set));
                for(int i=0;i<100&&country.get()==null;i++)Thread.sleep(100);
                assertEquals("\"FR\"",country.get());
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(()->a.webForTest().evaluateJavascript("stopMobileMap()",null));
                call(a,"import",new JSONObject().put("text",original.toString()));
            }
        }
    }
    @Test public void launchEngineDatabaseFinderFuelAndRestartWithoutInternetPermission() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        assertEquals(android.content.pm.PackageManager.PERMISSION_DENIED,
            context.checkSelfPermission("android.permission.INTERNET"));
        try (ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            MainActivity a=activity(scenario);
            JSONObject bootstrap=call(a,"bootstrap",new JSONObject());
            assertEquals(11,bootstrap.getJSONObject("metadata").getJSONArray("types").length());
            JSONObject state=bootstrap.getJSONObject("value").getJSONObject("state");
            state.put("intro_seen",true).put("joke_seen",true).put("pilot_name","ANDROID-RESTART-TEST");
            state.put("finder_filters",new JSONObject().put("origin","LFPG").put("max_minutes","2h"));
            call(a,"save",new JSONObject().put("state",state));
            JSONObject found=call(a,"finder",new JSONObject());
            assertEquals(577,found.getInt("matches"));
            assertEquals(100,found.getJSONArray("results").length());
            JSONObject more=call(a,"finder",new JSONObject().put("more",true));
            assertEquals(100,more.getInt("offset"));
            JSONObject transferred=call(a,"finder_use",new JSONObject().put("index",100));
            state=transferred.getJSONObject("value").getJSONObject("state");
            assertEquals("LFPG",state.getJSONObject("flight").getString("departure_icao"));
            state.put("fuel_inputs",new JSONObject().put("aircraft","airbus_a220_300").put("duration","5h").put("arrival","EGLL"));
            call(a,"save",new JSONObject().put("state",state));
            assertEquals(12285,call(a,"fuel",new JSONObject()).getDouble("total_block_fuel_kg_exact"),0.0);
            call(a,"fuel_use",new JSONObject());
        }
        try (ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            JSONObject saved=call(activity(scenario),"bootstrap",new JSONObject()).getJSONObject("value").getJSONObject("state");
            assertEquals("ANDROID-RESTART-TEST",saved.getString("pilot_name"));
            assertEquals("12285",saved.getJSONObject("flight").getString("fuel"));
        }
    }

    @Test public void nativeClipboardUsesEditedPreviewExactly() throws Exception {
        try (ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            MainActivity a=activity(scenario);
            JSONObject state=call(a,"bootstrap",new JSONObject()).getJSONObject("value").getJSONObject("state");
            state.put("message_type","ATC ACTIVE");
            state.getJSONObject("per_type").getJSONObject("ATC ACTIVE").put("airport_icao","LFPG").put("city","Paris").put("positions","Tower");
            state.getJSONObject("presentation").put("discord_aligned",false);
            state.getJSONObject("preview_edits").put("ATC ACTIVE","ANDROID CLIPBOARD last character Z");
            assertTrue(call(a,"render",new JSONObject().put("state",state)).getJSONObject("render").getBoolean("can_copy"));
            AtomicReference<Boolean> focused=new AtomicReference<>(false);
            for(int i=0;i<300;i++) {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(()->focused.set(a.hasWindowFocus()));
                if(focused.get())break;
                Thread.sleep(100);
            }
            if(!focused.get()) {
                System.err.println("Clipboard focus diagnostics: "+shell("dumpsys window windows"));
                System.err.println(shell("dumpsys power"));
            }
            assertTrue("Clipboard reads require the resumed activity to have window focus",focused.get());
            String payload=new JSONObject().put("state",state).toString();
            a.new Bridge().request("99999","native.copy",payload);
            ClipboardManager clipboard=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);
            AtomicReference<String> copied=new AtomicReference<>("");
            for(int i=0;i<300;i++) {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                    if(clipboard.hasPrimaryClip())copied.set(clipboard.getPrimaryClip().getItemAt(0).coerceToText(a).toString());
                });
                if(copied.get().equals("ANDROID CLIPBOARD last character Z"))break;
                Thread.sleep(100);
            }
            assertEquals("ANDROID CLIPBOARD last character Z",copied.get());
        }
    }
}
