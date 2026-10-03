package com.nmg06.rfsatc;

import android.app.*;
import android.content.*;
import android.os.Build;

/** One local opt-in reminder, survives process shutdown and reschedules on reboot. */
public class FlightReminder extends BroadcastReceiver {
    private static PendingIntent alarm(Context c){return PendingIntent.getBroadcast(c,4,new Intent(c,FlightReminder.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);}
    static void schedule(Context c,long when,String text){
        c.getSharedPreferences("flight-reminder",0).edit().putLong("when",when).putString("text",text).apply();
        ((AlarmManager)c.getSystemService(Context.ALARM_SERVICE)).setWindow(AlarmManager.RTC_WAKEUP,when,600_000,alarm(c));
    }
    static void cancel(Context c){((AlarmManager)c.getSystemService(Context.ALARM_SERVICE)).cancel(alarm(c));c.getSharedPreferences("flight-reminder",0).edit().clear().apply();}
    @Override public void onReceive(Context c,Intent intent){
        android.content.SharedPreferences p=c.getSharedPreferences("flight-reminder",0);
        long when=p.getLong("when",0);if(when==0)return;
        if(Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())){if(when>System.currentTimeMillis())schedule(c,when,p.getString("text","RFS Flightdeck"));else cancel(c);return;}
        if(Build.VERSION.SDK_INT>=33&&c.checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED){cancel(c);return;}
        NotificationManager manager=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
        if(Build.VERSION.SDK_INT>=26)manager.createNotificationChannel(new NotificationChannel("preparation","Flight preparation / Préparation du vol",NotificationManager.IMPORTANCE_DEFAULT));
        Notification.Builder b=Build.VERSION.SDK_INT>=26?new Notification.Builder(c,"preparation"):new Notification.Builder(c);
        Intent open=new Intent(c,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP);
        b.setSmallIcon(R.drawable.notification_icon).setContentTitle("RFS Flightdeck · Préparation / Preparation").setContentText(p.getString("text","Votre vol"))
            .setContentIntent(PendingIntent.getActivity(c,4,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE)).setAutoCancel(true);
        manager.notify(4,b.build());cancel(c);
    }
}
