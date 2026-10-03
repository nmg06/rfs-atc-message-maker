"""Opt-in service verification on the dedicated CI emulator after offline tests."""
import argparse
from pathlib import Path
import subprocess

def check(adb, serial):
    if not serial.startswith('emulator-'):
        raise ValueError('Dedicated emulator required')
    def run(*args):
        return subprocess.check_output([str(adb),'-s',serial,*args],text=True,encoding='utf-8',errors='replace',timeout=120)
    try:
        run('shell','cmd','connectivity','airplane-mode','disable')
        run('shell','svc','wifi','enable')
        report=run('shell','am','instrument','-w','-e','class',
            'com.nmg06.rfsatc.OfflineAppTest#viewportIsOutsideSystemBarsAndCutout',
            '-e','online-services','true','com.nmg06.rfsatc.test/androidx.test.runner.AndroidJUnitRunner')
        print(report)
        if 'OK (1 test)' not in report or 'FAILURES' in report:
            raise ValueError('Live Android services did not pass')
    finally:
        run('shell','cmd','connectivity','airplane-mode','enable')
        run('shell','svc','wifi','disable')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--adb',type=Path,required=True);p.add_argument('--serial',default='emulator-5554')
    a=p.parse_args();check(a.adb,a.serial)
