"""Capture de contrôle de nos widgets, sans toucher aux données utilisateur."""
import os
from pathlib import Path
import sys
import tempfile
import logging

temporary = tempfile.TemporaryDirectory(prefix="RFS-preview-")
os.environ["RFS_MESSAGE_MAKER_DATA_DIR"] = temporary.name
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from ui import RFSWindow

sys.path.insert(0, str(Path(__file__).parent / "tests"))
from test_rfs import sample_flight, sample_data

app = QApplication([])
window = RFSWindow()
window.store.state["flight"] = sample_flight()
window.store.state["per_type"] = sample_data()
window.message_type.setCurrentText("ARRIVAL BOARD")
window._rebuild_forms()
window.render_preview()
window.resize(1290, 920)
window.show()


def capture():
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(destination / "dark-arrival.png"))
    window.message_type.showPopup()
    app.processEvents()
    window.message_type.view().grab().save(str(destination / "dark-menu.png"))
    window.message_type.hidePopup()
    window.message_type.setCurrentText("ATC OFFLINE")
    window.render_preview()
    app.processEvents()
    window.grab().save(str(destination / "dark-atc-offline.png"))
    window.toggle_theme()
    app.processEvents()
    window.grab().save(str(destination / "light-atc-offline.png"))
    window.close()
    app.quit()


QTimer.singleShot(1000, capture)
app.exec()
logging.shutdown()
temporary.cleanup()
