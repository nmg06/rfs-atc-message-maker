"""Real installed APK/process restart and rendered UI check on a dedicated emulator."""
import argparse
import html
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'com.nmg06.rfsatc'


def run(adb, serial):
    if not serial.startswith('emulator-'):
        raise ValueError('This automated test requires a dedicated emulator')
    def command(*args, timeout=90):
        return subprocess.check_output([str(adb), '-s', serial, *args], text=True,
            encoding='utf-8', errors='replace', timeout=timeout).strip()
    if command('shell', 'settings', 'get', 'global', 'airplane_mode_on') != '1':
        raise ValueError('Enable airplane mode before this test')
    # The previous runner has just finished. Stop its target and test process
    # before replacing their packages; retain all private saved data.
    command('shell', 'am', 'force-stop', PACKAGE)
    command('shell', 'am', 'force-stop', PACKAGE+'.test')
    command('install', '-r', str(ROOT/'android/app/build/outputs/apk/debug/app-debug.apk'))
    command('install', '-r', str(ROOT/'android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'))
    core_tests = ','.join('com.nmg06.rfsatc.OfflineAppTest#'+name for name in (
        'launchEngineDatabaseFinderFuelAndRestartWithoutInternetPermission',
        'nativeClipboardUsesEditedPreviewExactly',
        'offlineMapRendersLocalBordersRouteAndCountrySelection',
        'viewportIsOutsideSystemBarsAndCutout',
        'multipleAircraftListOpensWithoutTypingAndRestoresOffline',
        'recentRoutesKeepUnknownFieldsAndManualFlightOffline'))
    report = command('shell', 'am', 'instrument', '-w', '-e', 'class', core_tests,
                     PACKAGE+'.test/androidx.test.runner.AndroidJUnitRunner', timeout=360)
    print(report)
    if 'OK (6 tests)' not in report or 'FAILURES' in report:
        raise ValueError('Instrumentation did not pass: ' + report)
    def saved():
        return json.loads(command('shell', 'run-as', PACKAGE, 'cat', 'files/rfs_android.json'))
    original = saved()
    if original['state']['flight']['fuel'] != '12285' or original['state']['pilot_name'] != 'ANDROID-RESTART-TEST':
        raise ValueError('Test data missing before process restart')
    command('shell', 'am', 'force-stop', PACKAGE)
    command('shell', 'am', 'start', '-n', PACKAGE+'/.MainActivity')
    deadline = time.monotonic() + 90
    callsign = original['state']['flight']['callsign']
    visible = False
    xml = ''
    while time.monotonic() < deadline:
        try:
            command('shell', 'uiautomator', 'dump', '/sdcard/rfs-test-window.xml')
            xml = command('shell', 'cat', '/sdcard/rfs-test-window.xml')
            texts = [html.unescape(text) for text in re.findall(r' text="([^"]*)"', xml)]
            # Header route is set only after the real JS/native bootstrap succeeds.
            visible = any(callsign in text for text in texts) and any(
                text in ('Préparez votre prochain départ.', 'Prepare your next departure.') for text in texts)
            if visible:
                break
        except subprocess.CalledProcessError:
            pass
        time.sleep(1)
    if not visible:
        (ROOT/'build/android-restart-window.xml').write_text(xml, encoding='utf-8')
        raise ValueError('Restored flight UI not visible after process restart')
    if saved() != original:
        raise ValueError('Persistent data changed across process restart')
    print(json.dumps({'airplane_mode': True, 'instrumentation_tests': 6,
        'process_restart_persistent': True, 'restored_webview_rendered': True,
        'callsign': callsign, 'fuel': original['state']['flight']['fuel']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--serial', default='emulator-5554')
    args = parser.parse_args()
    try:
        run(args.adb, args.serial)
    except Exception as error:
        if not args.serial.startswith('emulator-'):
            raise
        if isinstance(error, subprocess.TimeoutExpired):
            output=error.stdout or ''
            print(output.decode('utf-8',errors='replace') if isinstance(output,bytes) else output)
        # Collect diagnostics here, while the emulator is still running: the
        # workflow runner tears it down before the next Actions step.
        logs=subprocess.run([str(args.adb),'-s',args.serial,'logcat','-d','-t','3000'],
            text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=30)
        target=ROOT/'build/android-test-logcat.txt'
        target.parent.mkdir(exist_ok=True)
        target.write_text(logs.stdout,encoding='utf-8')
        print('\n'.join(line for line in logs.stdout.splitlines()
            if any(key in line for key in ('rfsatc','TestRunner','AndroidRuntime','ANR')))[-16000:])
        raise
