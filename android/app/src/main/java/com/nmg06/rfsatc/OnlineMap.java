package com.nmg06.rfsatc;

import com.chaquo.python.Python;
import org.json.JSONObject;
import org.json.JSONArray;
import java.net.URL;
import java.net.HttpURLConnection;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import android.util.Base64;

/** Only explicitly enabled imagery/weather; never called by offline engines. */
final class OnlineMap {
    volatile boolean enabled;
    private final LinkedHashMap<String,byte[]> cache=new LinkedHashMap<>(16,.75f,true);
    private long bytes;
    private int requests;
    synchronized int requestCount(){return requests;}
    private byte[] fetch(String location) throws Exception {
        URL url=new URL(location);
        if(!enabled)throw new IllegalStateException("Enable optional online layers first");
        if(!url.getProtocol().equals("https") || !(url.getHost().equals("tiles.maps.eox.at") || url.getHost().equals("api.open-meteo.com"))
                || url.getUserInfo()!=null || (url.getPort()!=-1&&url.getPort()!=443))throw new IllegalArgumentException("Unsupported service");
        boolean tile=url.getHost().equals("tiles.maps.eox.at");
        synchronized(this){if(tile&&cache.containsKey(location))return cache.get(location);requests++;}
        HttpURLConnection connection=(HttpURLConnection)url.openConnection();
        connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(4000);connection.setReadTimeout(6000);
        connection.setRequestProperty("User-Agent","RFS-Flightdeck/0.4 (optional map)");
        try {
            if(connection.getResponseCode()!=200)throw new java.io.IOException("Map service unavailable ("+connection.getResponseCode()+")");
            try(InputStream input=connection.getInputStream();ByteArrayOutputStream output=new ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int n;
                while((n=input.read(buffer))!=-1){if(output.size()+n>2_000_000)throw new java.io.IOException("Map response exceeds limit");output.write(buffer,0,n);}
                byte[] result=output.toByteArray();
                if(tile)synchronized(this){cache.put(location,result);bytes+=result.length;while(bytes>16_000_000||cache.size()>64){String first=cache.keySet().iterator().next();bytes-=cache.remove(first).length;}}
                return result;
            }
        }finally{connection.disconnect();}
    }
    JSONObject request(String method,JSONObject args) throws Exception {
        if(method.equals("native.tile")){
            int z=args.getInt("z"),x=args.getInt("x"),y=args.getInt("y");
            if(z<0||z>15||x<0||y<0||x>=(1<<z)||y>=(1<<z))throw new IllegalArgumentException("Invalid tile");
            String location="https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/"+z+"/"+y+"/"+x+".jpg";
            byte[] data=fetch(location);
            if(data.length<3||(data[0]&255)!=255||(data[1]&255)!=216)throw new java.io.IOException("JPEG required");
            return new JSONObject().put("data","data:image/jpeg;base64,"+Base64.encodeToString(data,Base64.NO_WRAP));
        }
        int level=args.getInt("level");
        if(!java.util.Arrays.asList(850,700,500,400,300,250,200,150).contains(level))throw new IllegalArgumentException("Invalid pressure level");
        JSONArray points=args.getJSONArray("points");if(points.length()<1||points.length()>32)throw new IllegalArgumentException("Invalid grid");
        StringBuilder lat=new StringBuilder(),lon=new StringBuilder();
        for(int i=0;i<points.length();i++){
            double a=points.getJSONArray(i).getDouble(0),b=points.getJSONArray(i).getDouble(1);
            if(!Double.isFinite(a)||!Double.isFinite(b)||a< -85||a>85||b< -180||b>180)throw new IllegalArgumentException("Invalid coordinates");
            if(i>0){lat.append(',');lon.append(',');}lat.append(a);lon.append(b);
        }
        String location="https://api.open-meteo.com/v1/forecast?latitude="+lat+"&longitude="+lon+
            "&hourly=wind_speed_"+level+"hPa,wind_direction_"+level+"hPa,geopotential_height_"+level+
            "hPa&wind_speed_unit=kn&forecast_hours=1&timezone=UTC";
        String raw=new String(fetch(location),StandardCharsets.UTF_8);
        return new JSONObject(Python.getInstance().getModule("map_services").callAttr("wind_json",raw,level).toString());
    }
}
