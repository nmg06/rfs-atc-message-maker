"""Developer-only real database checks and own-widget screenshots."""
import json
import logging
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

session_data=tempfile.TemporaryDirectory(prefix='RFSFinderQA-')
os.environ['RFS_MESSAGE_MAKER_DATA_DIR']=session_data.name

from PySide6.QtWidgets import QApplication
from ui import RFSWindow
from finder.ui import FinderDialog
from finder.search import Criteria, search

app=QApplication([])
window=RFSWindow()
db=Path(__file__).parent/'finder-data'/'aviation.sqlite'
out=Path(__file__).parent.parent/'finder-screenshots'
out.mkdir(exist_ok=True)
now=datetime.now(timezone.utc)
cases={
    'air_india_airbus_longhaul': Criteria(airline='Air India',manufacturer='Airbus',min_minutes=570,max_minutes=660,
        arrival_time='07:00',arrival_date='tomorrow',excluded_airports=['EGLL']),
    'paris_two_hours_neo': Criteria(origin=['LFPG'],aircraft='A320neo',target_minutes=120),
    'air_india_a321neo': Criteria(airline='Air India',aircraft='A321neo'),
    'paris_available_two_hours': Criteria(origin=['LFPG'],max_minutes=120),
}
report={}
for name,criteria in cases.items():
    result=search(db,criteria,now)
    report[name]={'count':len(result['results']),'matches':result['matches'],
                  'examples':[{k:r[k] for k in ('callsign','aircraft','origin','destination','duration_min','n_obs','n_complete','last_seen','score')} for r in result['results'][:3]]}
dialog=FinderDialog(window,db,'fr')
dialog.fields['origin'].setText('LFPG')
dialog.fields['max_minutes'].setText('120')
dialog.show()
dialog.present(search(db,cases['paris_available_two_hours'],now))
app.processEvents()
dialog.grab().save(str(out/'finder-dark.png'))
window.toggle_theme()
app.processEvents()
dialog.grab().save(str(out/'finder-light.png'))
dialog.close()
window.close()
logging.shutdown()
session_data.cleanup()
(out/'real-search-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
