"""Local update preferences and a non-blocking desktop release check."""
from __future__ import annotations

from datetime import datetime
from threading import Thread, Lock

from PySide6.QtCore import QObject, Signal, Slot, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app_version import VERSION
from i18n import language
import storage
import updates

_WORKERS = set()
_PREFERENCE_LOCK = Lock()


def tx(fr, en):
    return fr if language() == 'fr' else en


def preferences_path():
    # This preference belongs to the device, outside the four exported files.
    return storage.DATA_DIR / 'rfs_updates.json'


def read_preferences():
    return updates.normalise_preferences(storage.load_json(preferences_path(), {}))


def write_preferences(preferences):
    with _PREFERENCE_LOCK:
        storage.save_json(preferences_path(), updates.normalise_preferences(preferences))


def result_text(result):
    status = result.get('status')
    if status == 'available':
        return tx('Nouvelle version disponible : ', 'New version available: ') + str(result.get('version', ''))
    if status == 'up_to_date':
        return tx('Aucune version compatible plus récente n’est publiée.', 'No newer compatible version has been published.')
    if status == 'no_release':
        return tx('Aucune version publique compatible n’est publiée pour cet appareil. Les versions de test ne sont pas annoncées ici.', 'No compatible public release has been published for this device. Test builds are not announced here.')
    if status == 'unavailable':
        if result.get('reason') == 'invalid_cache':
            return tx('La dernière vérification enregistrée est illisible. Appuyez sur Vérifier maintenant pour réessayer.', 'The saved check result could not be read. Press Check now to try again.')
        if result.get('reason') == 'preferences_unavailable':
            return tx('La vérification n’a pas démarré car son réglage local n’a pas pu être sauvegardé.', 'The check did not start because its local preference could not be saved.')
        return tx('Vérification indisponible. Vérifiez votre connexion ou réessayez plus tard. Cela ne signifie pas que vous êtes à jour.', 'The check is unavailable. Check your connection or try again later. This does not mean you are up to date.')
    return tx('Aucune vérification effectuée sur cet appareil.', 'No check has been made on this device.')


class ReleaseWorker(QObject):
    result = Signal(object)
    finished = Signal()

    def __init__(self, parent, preferences):
        super().__init__(parent)
        self.preferences = preferences

    def run(self):
        try:
            # OneDrive/storage writes can be slow: both writes happen off the GUI.
            write_preferences(self.preferences)
        except OSError:
            result = {'status': 'unavailable', 'reason': 'preferences_unavailable'}
        else:
            result = updates.check_for_update('windows')
            self.preferences['last_result'] = result
            try:
                write_preferences(self.preferences)
            except OSError:
                storage.LOGGER.exception('Update result could not be saved')
        try:
            self.result.emit(result)
            self.finished.emit()
        except RuntimeError:
            # QApplication may already have destroyed the signal receiver.
            # The daemon exits safely; quitting never waits for the network.
            pass


class PreferenceWorker(QObject):
    result = Signal(object)
    finished = Signal()

    def __init__(self, parent, preferences, previous_enabled):
        super().__init__(parent)
        self.preferences = preferences
        self.previous_enabled = previous_enabled

    def run(self):
        result = {'ok': True, 'previous_enabled': self.previous_enabled}
        try:
            write_preferences(self.preferences)
        except OSError:
            result['ok'] = False
        try:
            self.result.emit(result)
            self.finished.emit()
        except RuntimeError:
            pass


def start_preferences_worker(receiver, preferences, previous_enabled):
    worker = PreferenceWorker(QApplication.instance(), preferences, previous_enabled)
    _WORKERS.add(worker)
    worker.result.connect(receiver)
    def release():
        _WORKERS.discard(worker)
        worker.deleteLater()
    worker.finished.connect(release)
    Thread(target=worker.run, name='Flightdeck-update-preference', daemon=True).start()
    return worker


def start_worker(receiver, preferences):
    worker = ReleaseWorker(QApplication.instance(), preferences)
    _WORKERS.add(worker)
    worker.result.connect(receiver)
    def release():
        _WORKERS.discard(worker)
        worker.deleteLater()
    worker.finished.connect(release)
    Thread(target=worker.run, name='Flightdeck-release-check', daemon=True).start()
    return worker


class UpdateDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(tx('Mises à jour', 'Updates'))
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        title = QLabel('RFS Flightdeck ' + VERSION)
        layout.addWidget(title)
        explanation = QLabel(tx('La vérification consulte les versions publiques sur GitHub. Aucun vol ni réglage n’est envoyé. Internet sert uniquement à vérifier et télécharger ; l’application fonctionne toujours hors ligne.', 'The check reads public releases on GitHub. No flight or settings are sent. Internet is only used to check and download; the application keeps working offline.'))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.automatic = QCheckBox(tx('Vérifier automatiquement à l’ouverture, au maximum une fois par jour', 'Check automatically at startup, at most once a day'))
        self.automatic.setChecked(window.update_preferences['enabled'])
        self.automatic.toggled.connect(self.toggle_automatic)
        layout.addWidget(self.automatic)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.checked = QLabel()
        layout.addWidget(self.checked)
        row = QHBoxLayout()
        self.check = QPushButton(tx('Vérifier maintenant', 'Check now'))
        self.check.clicked.connect(lambda: window.check_updates(manual=True))
        row.addWidget(self.check)
        self.download = QPushButton(tx('Télécharger la version', 'Download release'))
        self.download.clicked.connect(lambda: self.open_link(download=True))
        row.addWidget(self.download)
        self.notes = QPushButton(tx('Voir les nouveautés', 'View release notes'))
        self.notes.clicked.connect(self.open_link)
        row.addWidget(self.notes)
        layout.addLayout(row)
        close = QPushButton(tx('Fermer', 'Close'))
        close.clicked.connect(self.close)
        layout.addWidget(close)
        self.refresh()

    @Slot(bool)
    def toggle_automatic(self, enabled):
        self.window.set_update_auto(enabled)
        self.refresh()

    def refresh(self):
        busy = self.window._update_running
        self.automatic.setEnabled(not self.window._update_preferences_running)
        prefs = self.window.update_preferences
        self.check.setEnabled(not busy)
        self.status.setText(tx('Enregistrement du réglage…', 'Saving preference…') if self.window._update_preferences_running else tx('Vérification en cours…', 'Checking…') if busy else result_text(prefs['last_result']))
        last = prefs['last_attempt']
        self.checked.setText((tx('Dernière tentative : ', 'Last attempt: ') + datetime.fromtimestamp(last).strftime('%Y-%m-%d %H:%M')) if last else '')
        result = prefs['last_result']
        available = updates.is_newer_release(result)
        self.download.setEnabled(available and updates.trusted_release_url(result.get('download_url'), download=True))
        self.notes.setEnabled(available and updates.trusted_release_url(result.get('release_url')))

    @Slot()
    def open_link(self, download=False):
        result = self.window.update_preferences['last_result']
        link = result.get('download_url' if download else 'release_url')
        if updates.is_newer_release(result) and updates.trusted_release_url(link, download=download):
            QDesktopServices.openUrl(QUrl(link))
