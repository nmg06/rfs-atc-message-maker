"""Bound native CI tests and retain real logcat diagnostics before teardown."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', type=Path, required=True)
    args = parser.parse_args()
    command = ['gradlew.bat' if os.name == 'nt' else './gradlew', '--no-daemon',
               'connectedDebugAndroidTest']
    result = 1
    try:
        result = subprocess.run(command, cwd=ROOT/'android', timeout=360).returncode
    finally:
        if result:
            logs = subprocess.run([str(args.adb), 'logcat', '-d', '-t', '3000'],
                text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=30)
            target = ROOT/'build/android-test-logcat.txt'
            target.parent.mkdir(exist_ok=True)
            target.write_text(logs.stdout, encoding='utf-8')
            print('\n'.join(line for line in logs.stdout.splitlines()
                if any(key in line for key in ('rfsatc', 'TestRunner', 'AndroidRuntime', 'ANR')))[-16000:])
    raise SystemExit(result)
