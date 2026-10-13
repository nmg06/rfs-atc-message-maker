"""Installed WebView compatibility and native-operation recreation tests; dedicated offline emulator."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "com.nmg06.rfsatc"


def run(adb: Path, serial: str) -> None:
    if not serial.startswith("emulator-"):
        raise ValueError("A dedicated emulator is required")
    command = [str(adb), "-s", serial]
    airplane = subprocess.check_output(command + ["shell", "settings", "get", "global", "airplane_mode_on"], text=True, timeout=30).strip()
    if airplane != "1":
        raise ValueError("Enable airplane mode before these tests")
    subprocess.run(command + ["shell", "am", "force-stop", PACKAGE], check=True, timeout=30)
    subprocess.run(command + ["shell", "am", "start", "-W", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"], check=True, timeout=30)
    try:
        report = subprocess.check_output(command + ["shell", "am", "instrument", "-w", "-e", "class", "com.nmg06.rfsatc.LifecycleCompatibilityTest", PACKAGE + ".test/androidx.test.runner.AndroidJUnitRunner"], text=True, encoding="utf-8", errors="replace", timeout=600)
        print(report)
        if "OK (4 tests)" not in report or "FAILURES" in report:
            raise ValueError("Installed lifecycle tests failed: " + report)
    except Exception:
        logs = subprocess.run(command + ["logcat", "-d", "-t", "3000"], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
        target = ROOT / "build/android-lifecycle-logcat.txt"
        target.parent.mkdir(exist_ok=True)
        target.write_text(logs.stdout, encoding="utf-8")
        print("\n".join(line for line in logs.stdout.splitlines() if any(key in line for key in ("rfsatc", "TestRunner", "AndroidRuntime", "ANR")))[-16000:])
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", default="emulator-5554")
    args = parser.parse_args()
    run(args.adb, args.serial)
