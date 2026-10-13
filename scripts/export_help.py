"""Export one bilingual catalogue to local browser scripts, deterministically."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from help_content import CONTENT


def export():
    from export_web_fuel import export as export_fuel
    export_fuel()
    source = 'window.FLIGHTDECK_HELP=' + json.dumps(CONTENT, ensure_ascii=False, separators=(',', ':')) + ';\n'
    for folder in (ROOT / 'mobile', ROOT / 'android/app/src/main/assets/www'):
        (folder / 'help-content.js').write_text(source, encoding='utf-8', newline='\n')
        for name in ('help-ui.js', 'help-ui.css'):
            (folder / name).write_bytes((ROOT / 'assets' / name).read_bytes())


if __name__ == '__main__':
    export()
