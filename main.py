"""Point d'entrée Windows de RFS ATC Message Maker."""
from __future__ import annotations
from i18n import tr, set_language, language
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
from storage import LOGGER
from ui import RFSWindow
from app_icon import make_icon

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName('RFS ATC Message Maker')
    app.setWindowIcon(make_icon())

    def report_exception(exc_type, exc_value, exc_tb) -> None:
        LOGGER.error('Erreur non gérée', exc_info=(exc_type, exc_value, exc_tb))
        if '--smoke-test' in sys.argv:
            app.exit(1)
            return
        QMessageBox.critical(None, tr('Erreur'), tr('Une erreur a été enregistrée dans le journal local. Les données sauvegardées sont conservées.'))
    sys.excepthook = report_exception
    window = RFSWindow()
    window.show()
    if '--smoke-test' in sys.argv:

        def smoke():
            from storage import DATA_DIR
            from finder.ui import FinderDialog
            from finder.time_utils import local_to_utc
            from fuel.calculator import calculate_fuel
            from fuel.ui import FuelDialog
            from finder.search import search, Criteria
            from datetime import datetime, timezone
            app_folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
            database = app_folder / 'finder-data' / 'aviation.sqlite'
            dialog = FinderDialog(window, database)
            instant, warnings = local_to_utc(datetime(2026, 3, 29, 2, 30), 'Europe/Paris')
            window.grab().save(str(DATA_DIR / 'smoke-main.png'))
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(DATA_DIR / 'smoke-finder.png'))
            fuel_dialog = FuelDialog({'aircraft': 'Airbus A220-300', 'arrival_icao': 'EGLL', 'estimated_flight_time': '5h'}, window)
            fuel_dialog.calculate()
            fuel_dialog.show()
            app.processEvents()
            fuel_dialog.grab().save(str(DATA_DIR / 'smoke-fuel.png'))
            found = search(database, Criteria(origin=['LFPG'], max_minutes=120), datetime.now(timezone.utc)) if database.is_file() else None
            (DATA_DIR / 'smoke-result.json').write_text(json.dumps({'window': window.windowTitle(), 'finder': dialog.windowTitle(), 'dst_utc': instant.isoformat(), 'warnings': warnings, 'real_database_matches': found['matches'] if found else None, 'fuel_example_kg': calculate_fuel('airbus_a220_300', 5, 'EGLL')['total_block_fuel_kg_exact']}), encoding='utf-8')
            window.language_combo.setCurrentIndex(window.language_combo.findData('en'))
            app.processEvents()
            window.grab().save(str(DATA_DIR / 'smoke-main-en.png'))
            from report_dialog import ReportDialog
            from dialogs import UnifiedDesignDialog
            report = ReportDialog(window)
            report.show()
            app.processEvents()
            report.grab().save(str(DATA_DIR / 'smoke-report.png'))
            report.close()
            design = UnifiedDesignDialog(parent=window)
            design.show()
            app.processEvents()
            design.grab().save(str(DATA_DIR / 'smoke-design.png'))
            design.close()
            window.toggle_theme()
            app.processEvents()
            window.grab().save(str(DATA_DIR / 'smoke-main-light.png'))
            fuel_dialog.close()
            dialog.close()
            window.close()
            app.quit()
        QTimer.singleShot(100, smoke)
    else:
        QTimer.singleShot(150, window.show_welcome)
    return app.exec()
if __name__ == '__main__':
    raise SystemExit(main())
