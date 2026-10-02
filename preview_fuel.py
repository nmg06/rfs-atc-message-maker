"""Capture the supplied fuel example in the real application widgets."""
import os
import logging
from pathlib import Path
import tempfile

temporary=tempfile.TemporaryDirectory(prefix='RFSFuelQA-')
os.environ['RFS_MESSAGE_MAKER_DATA_DIR']=temporary.name
from PySide6.QtWidgets import QApplication
from ui import RFSWindow
from fuel.ui import FuelDialog

app=QApplication([])
window=RFSWindow()
dialog=FuelDialog({'aircraft':'Airbus A220-300','arrival_icao':'EGLL','estimated_flight_time':'5h'},window)
dialog.calculate()
dialog.show()
app.processEvents()
out=Path(__file__).parent.parent/'fuel-screenshots'
out.mkdir(exist_ok=True)
dialog.grab().save(str(out/'a220-5h-egll.png'))
print(dialog.result['display'])
dialog.close()
window.close()
logging.shutdown()
temporary.cleanup()
