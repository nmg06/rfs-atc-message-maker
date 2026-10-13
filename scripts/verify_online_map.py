"""Explicit developer probe: fetch real providers and verify rendered overlays.

Never called by startup or offline tests. python scripts/verify_online_map.py
"""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from map_online import download, parse_wind, tile_url, wind_url
from route_map import RouteMap

app = QApplication([])
if os.name == 'nt':
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts/segoeui.ttf'))
    app.setFont(QFont('Segoe UI', 9))
widget = RouteMap()
widget.resize(900, 380)
widget.set_flight({'departure_icao':'LFPG','arrival_icao':'LROP'})
widget.create_country_controls()
widget.layer.setCurrentIndex(1)
widget.wind_level.setCurrentIndex(widget.wind_level.findData(250))
widget.show()
for _ in range(450):
    QTest.qWait(100)
    if widget._tiles and widget._wind:
        break
assert widget._tiles, 'EOX actual image tiles missing'
assert widget._wind, 'Open-Meteo actual wind samples missing'
assert not widget._background.isNull(), 'Map rendering failed'
output = Path(os.environ.get('RFS_MAP_PROBE_DIR', '.'))
output.mkdir(parents=True, exist_ok=True)
widget.grab().save(str(output/'map-online.png'))
result = {'tiles_loaded':len(widget._tiles),'wind_samples':len(widget._wind['samples']),
          'forecast':widget._wind['samples'][0]['time'], 'level':widget._wind['level'],
          'wind_note':widget._wind_note()}
(output/'map-online-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
widget.wind_level.setCurrentIndex(0)
widget.layer.setCurrentIndex(0)
widget.grab().save(str(output/'map-offline.png'))
widget.close()
QTest.qWait(100)
