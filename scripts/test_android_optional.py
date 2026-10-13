"""Test opt-in notifications/icons last: package changes can restart tasks."""
import argparse
from pathlib import Path
import subprocess

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--serial', default='emulator-5554')
    args = parser.parse_args()
    if not args.serial.startswith('emulator-'):
        raise ValueError('Dedicated emulator required')
    command = [str(args.adb), '-s', args.serial]
    subprocess.run(command+['shell','am','force-stop','com.nmg06.rfsatc'],check=True,timeout=30)
    report = subprocess.check_output(command+['shell','am','instrument','-w','-e','class',
        'com.nmg06.rfsatc.OfflineAppTest#localReminderAndLauncherIconAreExplicitAndReversible',
        'com.nmg06.rfsatc.test/androidx.test.runner.AndroidJUnitRunner'],
        text=True,encoding='utf-8',errors='replace',timeout=90)
    print(report)
    if 'OK (1 test)' not in report or 'FAILURES' in report:
        raise ValueError('Installed notifications and launcher icons did not pass')
