"""Isolated offscreen desktop check and screenshots; never opens a daily profile."""
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
output = Path(os.environ['RFS_DESKTOP_PROBE_DIR']).resolve()
output.mkdir(parents=True, exist_ok=True)
os.environ['RFS_MESSAGE_MAKER_DATA_DIR'] = str(output/'isolated-profile')
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from ui import RFSWindow

app = QApplication([])
if os.name == 'nt':
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts/segoeui.ttf'))
    app.setFont(QFont('Segoe UI', 9))
window = RFSWindow()
window.resize(1250, 900)
window.store.state.update(intro_seen=True, language='fr')
window.store.state['flight'].update(departure_icao='LFPG', arrival_icao='LROP', callsign='AFR123',
                                   aircraft='Airbus A220-300', estimated_flight_time='5h')
window._rebuild_forms()
window.render_preview()
window.show()
app.processEvents()
if window.store.state['theme'] != 'Sombre':
    window.toggle_theme()
    app.processEvents()
window.grab().save(str(output/'desktop-dark.png'))
switches = []
for _ in range(4):
    started = time.perf_counter()
    window.toggle_theme()
    app.processEvents()
    switches.append(round((time.perf_counter()-started)*1000, 2))
window.toggle_theme()
app.processEvents()
window.grab().save(str(output/'desktop-light.png'))
window.route_map.set_country(0, 'FR')
window.route_map.set_country(1, 'RO')
route = window.store.state['flight'].copy()
from PySide6.QtTest import QTest
from finder.ui import FinderDialog
original_exec = FinderDialog.exec
selected = {}
def check_finder(dialog):
    selected.update(origin=dialog.fields['origin_country'].text(), destination=dialog.fields['destination_country'].text())
    return 0
FinderDialog.exec = check_finder
window.route_map.find_countries_button.click()
FinderDialog.exec = original_exec
assert selected == {'origin':'FR','destination':'RO'}
assert window.store.state['flight'] == route
result = dict(theme_switch_ms=switches, countries_to_finder=selected,
              country_features=len(__import__('route_map').country_paths()),
              default_offline=not window.route_map.online.pending)
(output/'desktop-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
window.close()
