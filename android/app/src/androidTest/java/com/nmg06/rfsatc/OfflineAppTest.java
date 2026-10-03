package com.nmg06.rfsatc;

import android.content.ClipboardManager;
import android.content.Context;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class OfflineAppTest {
    private MainActivity activity(ActivityScenario<MainActivity> scenario) {
        AtomicReference<MainActivity> result = new AtomicReference<>();
        scenario.onActivity(result::set); return result.get();
    }
    private JSONObject call(MainActivity a, String method, JSONObject args) throws Exception {
        JSONObject envelope = new JSONObject(a.requestForTest(method,args.toString()).get(120,TimeUnit.SECONDS));
        assertTrue(envelope.optString("error"),envelope.getBoolean("ok"));
        return envelope.getJSONObject("result");
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
            String payload=new JSONObject().put("state",state).toString();
            a.new Bridge().request("99999","native.copy",payload);
            ClipboardManager clipboard=(ClipboardManager)a.getSystemService(Context.CLIPBOARD_SERVICE);
            AtomicReference<String> copied=new AtomicReference<>("");
            for(int i=0;i<100;i++) {
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
