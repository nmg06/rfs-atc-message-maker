# Install and use RFS Flightdeck

Flightdeck helps you find an RFS flight, prepare its fuel and optionally write
ATC messages. The main tools work offline, without an account or telemetry.
You do not need Python to install the packaged apps.

| Device | Download | Availability |
|---|---|---|
| Windows 10/11, 64 bit | Windows ZIP | Portable test version |
| Android 7+, ARM64 | Android APK | Installable test version |
| iPhone / iPad | No native package | iOS app not currently available |

Verified 0.4.2 test downloads: [Android APK](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427403/artifacts/11314783690) · [Windows ZIP](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427393/artifacts/11315221754). GitHub sign-in required; these artifacts expire on 3 November 2026.

## Download from GitHub

Open the [Windows builds](https://github.com/nmg06/rfs-atc-message-maker/actions/workflows/flightdeck.yml)
or [Android builds](https://github.com/nmg06/rfs-atc-message-maker/actions/workflows/android.yml).
Choose a successful green run for **feat/flightdeck-map-performance**, then scroll
to **Artifacts**. Download **RFSFlightdeck-Windows-x64-test** or
**RFS-ATC-Android-debug** and extract the downloaded ZIP.

GitHub requires sign-in to download these test artifacts; Flightdeck itself
does not require an account. Artifacts expire after 30 days. A future approved
public release can provide permanent download links. Do not use a failed red run.

## Windows

1. Extract both the artifact ZIP and the Windows package inside it into a new folder.
2. Open **RFSFlightdeck → RFSATCMessageMaker.exe**.
3. Keep **_internal**, **finder-data** and the other files beside the EXE.
4. Create a desktop shortcut to that EXE if you want quick access.

The executable retains its historical filename; the displayed app name is
RFS Flightdeck. Your data is in **data** beside the EXE unless
RFS_MESSAGE_MAKER_DATA_DIR overrides it. Close the old app normally, back up
its data folder, then copy its four **rfs_*.json** files into the new data folder
to migrate. Keep the old version and backup.

## Android

1. Extract the artifact ZIP to get **app-debug.apk**, or use the APK supplied by the owner.
2. Put it in **Downloads** on your phone, using USB file transfer if needed.
3. Open **Files → Downloads**, tap the APK and allow installation from that source if prompted.
4. Tap **Install**, then **Open**. Later, launch **RFS Flightdeck** from your app list.

Install an update over the previous app when the signing key matches. If Android
reports an incompatible update, export your data before uninstalling. Local test
APKs and GitHub builds may use different debug keys. Uninstalling removes private data.
The first launch unpacks the included Finder database locally; it downloads nothing.

## Prepare your first flight

1. Choose English in Settings if needed. You can skip the tutorial and replay it later.
2. In Finder, choose an airline or airports and search. Results are historical profiles.
3. Review **Details**, then **Use this flight**. Check retained manual values.
4. Choose an exact RFS aircraft variant and open Fuel Helper. Review total duration and arrival.
5. Calculate, then apply aircraft and fuel. This tool is for simulation only.
6. If you need ATC, choose a message, review its preview and copy it to Discord or RFS.

**Check before copying** enforces required fields and message limits. Disable it
to copy incomplete text with warnings retained. Tap a warning to locate its field.
**ETE 5 min in ARRIVAL BOARD means arrival in about five minutes**; total flight
duration used by Fuel Helper is a separate value.

## Help, backups and optional online tools

**Understand this screen** explains each section. Reopen the tutorial or search
the 30 FAQs from **Help** on Windows or **Settings → Onboard help** on Android.
The current flight saves automatically; Save flight also creates a named copy.
Export before changing phones or uninstalling. Review the warning before importing.

Finder, fuel, messages, local map, borders and help work in airplane mode.
Satellite and real-world wind layers use Internet only when enabled. Game weather
may differ. A listed runway is not an ATC assignment; gates are not in the database.
Android reminders are optional and approximate. After Force stop, schedule again.

The web prototype has the same bilingual help and PC-derived fuel calculation,
but remains incomplete and has no offline SQLite Finder. An APK cannot run on iPhone.
Physical-phone keyboard, landscape, file/photo selection and sharing still need testing.
