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
import org.junit.Rule;
import org.junit.rules.TestName;
import org.junit.rules.Timeout;
import org.junit.runner.RunWith;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class OfflineAppTest {
    @Rule public final TestName testName=new TestName();
    @Rule public final Timeout boundedTest=Timeout.seconds(240);
    private String shell(String command) throws Exception {
        try (ParcelFileDescriptor descriptor=InstrumentationRegistry.getInstrumentation()
                .getUiAutomation().executeShellCommand(command);
             FileInputStream stream=new FileInputStream(descriptor.getFileDescriptor())) {
            return new String(stream.readAllBytes(),StandardCharsets.UTF_8);
        }
    }
    @Before public void prepareForeground() throws Exception {
        System.out.println("ANDROID TEST START: "+testName.getMethodName());
        // Dedicated test device only. Reset the lock screen/previous clipboard
        // overlay before each ActivityScenario, rather than relying on boot focus.
        shell("input keyevent KEYCODE_WAKEUP");
        shell("wm dismiss-keyguard");
        // HOME key injection returns while the previous task is still moving.
        // Wait for the real launcher Activity before starting the next scenario.
        String home=shell("am start -W -a android.intent.action.MAIN -c android.intent.category.HOME");
        assertTrue("Launcher not ready: "+home,home.contains("Status: ok"));
        // ActivityScenario waits for the launched Activity's lifecycle itself.
        // A global waitForIdleSync can wait forever after launcher icon changes.
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
        // Optional online layers now have a normal INTERNET permission, but
        // all these real engine/UI operations run with radios disabled in CI.
        try (ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            MainActivity a=activity(scenario);
            assertEquals("Offline launch must make zero provider requests",0,a.networkRequestsForTest());
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
            // Free copying preserves text even when required fields are empty.
            state.getJSONObject("per_type").getJSONObject("ATC ACTIVE").put("airport_icao","");
            state.put("strict_validation",true);
            assertFalse(call(a,"render",new JSONObject().put("state",state)).getJSONObject("render").getBoolean("can_copy"));
            state.put("strict_validation",false);
            state.getJSONObject("preview_edits").put("ATC ACTIVE","ANDROID FREE COPY incomplete Z");
            JSONObject free=call(a,"render",new JSONObject().put("state",state)).getJSONObject("render");
            assertTrue(free.getBoolean("can_copy"));assertTrue(free.getJSONArray("issues").length()>0);
            a.new Bridge().request("99996","native.copy",new JSONObject().put("state",state).toString());
            for(int i=0;i<100;i++) {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                    if(clipboard.hasPrimaryClip())copied.set(clipboard.getPrimaryClip().getItemAt(0).coerceToText(a).toString());
                });
                if(copied.get().equals("ANDROID FREE COPY incomplete Z"))break;
                Thread.sleep(100);
            }
            assertEquals("ANDROID FREE COPY incomplete Z",copied.get());
        }
    }
    @Test public void viewportIsOutsideSystemBarsAndCutout() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            MainActivity a=activity(scenario);call(a,"bootstrap",new JSONObject());
            InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
                android.view.WindowInsets insets=a.getWindow().getDecorView().getRootWindowInsets();
                android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars()|android.view.WindowInsets.Type.displayCutout());
                int[] location=new int[2];a.webForTest().getLocationOnScreen(location);
                android.util.DisplayMetrics display=new android.util.DisplayMetrics();a.getWindowManager().getDefaultDisplay().getRealMetrics(display);
                assertTrue("Header under status bar",location[1]>=bars.top);
                assertTrue("Bottom navigation under system bar",location[1]+a.webForTest().getHeight()<=display.heightPixels-bars.bottom);
                assertTrue("Content under landscape cutout",location[0]>=bars.left);
                assertEquals(0,a.webForTest().getPaddingTop());
                assertTrue(a.webForTest().getHeight()>200);
            });
            if("true".equals(InstrumentationRegistry.getArguments().getString("online-services","false"))){
                OnlineMap service=new OnlineMap();service.enabled=true;
                JSONObject tile=service.request("native.tile",new JSONObject().put("z",2).put("x",2).put("y",1));
                assertTrue(tile.getString("data").startsWith("data:image/jpeg;base64,"));
                JSONObject wind=service.request("native.wind",new JSONObject().put("level",250)
                    .put("points",new org.json.JSONArray("[[48.8566,2.3522]]")));
                assertEquals(250,wind.getInt("level"));assertTrue(wind.getJSONArray("samples").length()>0);
                assertTrue(wind.getJSONArray("samples").getJSONObject(0).getDouble("height_m")>0);
                assertEquals(2,service.requestCount());
                System.out.println("LIVE ANDROID: EOX JPEG and Open-Meteo 250 hPa/UTC/AMSL verified");
            }
        }
    }
    @Test public void localReminderAndLauncherIconAreExplicitAndReversible() throws Exception {
        Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            MainActivity a=activity(scenario);call(a,"bootstrap",new JSONObject());
            shell("pm grant "+context.getPackageName()+" android.permission.POST_NOTIFICATIONS");
            long when=System.currentTimeMillis()+3600000;
            a.getSharedPreferences("interface",0).edit().putString("language","en").apply();
            FlightReminder.schedule(a,when,"LFPG → KJFK · offline test");
            assertEquals(when,a.getSharedPreferences("flight-reminder",0).getLong("when",0));
            new FlightReminder().onReceive(a,new android.content.Intent(a,FlightReminder.class));
            android.app.NotificationManager manager=(android.app.NotificationManager)a.getSystemService(Context.NOTIFICATION_SERVICE);
            for(int i=0;i<100&&manager.getActiveNotifications().length==0;i++)Thread.sleep(100);
            assertTrue("Local notification was not posted",manager.getActiveNotifications().length>0);
            assertEquals("RFS Flightdeck · Preparation",manager.getActiveNotifications()[0].getNotification().extras.getString(android.app.Notification.EXTRA_TITLE));
            manager.cancel(4);
            assertEquals(0,a.getSharedPreferences("flight-reminder",0).getLong("when",0));
            a.new Bridge().request("99998","native.icon","{\"icon\":\"Ocean\"}");
            android.content.ComponentName alias=new android.content.ComponentName(a,a.getPackageName()+".IconOcean");
            for(int i=0;i<100&&a.getPackageManager().getComponentEnabledSetting(alias)!=android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_ENABLED;i++)Thread.sleep(100);
            assertEquals(android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_ENABLED,a.getPackageManager().getComponentEnabledSetting(alias));
            a.new Bridge().request("99997","native.icon","{\"icon\":\"Default\"}");
            android.content.ComponentName original=new android.content.ComponentName(a,a.getPackageName()+".IconDefault");
            for(int i=0;i<100&&a.getPackageManager().getComponentEnabledSetting(original)!=android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_ENABLED;i++)Thread.sleep(100);
            assertEquals(android.content.pm.PackageManager.COMPONENT_ENABLED_STATE_ENABLED,a.getPackageManager().getComponentEnabledSetting(original));
        }finally{
            FlightReminder.cancel(context);
            // Revoking a permission kills this package (and instrumentation).
            // The dedicated emulator is destroyed after the job instead.
        }
    }
}
