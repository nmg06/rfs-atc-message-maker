"""Opt-in service verification on the dedicated CI emulator after offline tests."""
import argparse
from pathlib import Path
import subprocess
import time

def check(adb, serial):
    if not serial.startswith('emulator-'):
        raise ValueError('Dedicated emulator required')
    def run(*args):
        return subprocess.check_output([str(adb),'-s',serial,*args],text=True,encoding='utf-8',errors='replace',timeout=120)
    try:
        run('shell','cmd','connectivity','airplane-mode','disable')
        run('shell','svc','wifi','enable')
        # Enabling Wi-Fi returns before connection/DNS are ready after airplane
        # mode. Inspect the actual emulator state instead of guessing a delay.
        deadline=time.monotonic()+30
        while 'Wifi is connected to' not in run('shell','cmd','wifi','status'):
            if time.monotonic()>=deadline:
                raise ValueError('Emulator Wi-Fi did not reconnect')
            time.sleep(1)
        for attempt in range(3):
            report=run('shell','am','instrument','-w','-e','class',
                'com.nmg06.rfsatc.OfflineAppTest#viewportIsOutsideSystemBarsAndCutout',
                '-e','online-services','true','com.nmg06.rfsatc.test/androidx.test.runner.AndroidJUnitRunner')
            print(report)
            if 'OK (1 test)' in report and 'FAILURES' not in report:
                break
            if attempt==2 or not any(e in report for e in ('UnknownHostException','SocketTimeoutException','ConnectException')):
                raise ValueError('Live Android services did not pass')
            print('Retrying real provider requests after network transition')
            run('shell','am','force-stop','com.nmg06.rfsatc')
            time.sleep(10)
    finally:
        run('shell','cmd','connectivity','airplane-mode','enable')
        run('shell','svc','wifi','disable')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--adb',type=Path,required=True);p.add_argument('--serial',default='emulator-5554')
    a=p.parse_args();check(a.adb,a.serial)
