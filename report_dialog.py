"""User-reviewed reports with online Google Forms link, rich attachment manager and optional local ZIP export."""
import json
import platform
from pathlib import Path
import zipfile
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPlainTextEdit,
    QLabel, QPushButton, QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QListWidget, QListWidgetItem,
    QScrollArea, QWidget, QDialogButtonBox)
from i18n import tr

# Default Google Forms URL (can be customized or configured)
GOOGLE_FORMS_URL = "https://docs.google.com/forms/d/e/1FAIpQLSf5Btz-JubaPy9n8g2kpYvFSojD6ngSq3ruS0KEAzgxcUpHAw/viewform?usp=header"


def open_feedback_form():
    """Open only on explicit click; never submit local report data."""
    return QDesktopServices.openUrl(QUrl(GOOGLE_FORMS_URL))


class ReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Signaler un problème ou faire une suggestion'))
        self.resize(800, 760)
        self.attachments: list[Path] = []
        shell = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        outer = QVBoxLayout(body)
        scroll.setWidget(body)
        shell.addWidget(scroll, 1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        shell.addWidget(close)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        # Online Google Forms Section
        online_group = QGroupBox(tr('Option 1 — Formulaire en ligne (Google Forms)'))
        online_box = QVBoxLayout(online_group)
        online_box.setSpacing(10)
        online_desc = QLabel(tr('Déclarez un bug, signalez un problème ou proposez une suggestion d’amélioration directement via Google Forms en un clic :'))
        online_desc.setWordWrap(True)
        online_box.addWidget(online_desc)

        online_btn_layout = QHBoxLayout()
        forms_btn = QPushButton(tr('🌐 Ouvrir le formulaire en ligne (Google Forms)'), objectName='primary')
        forms_btn.setStyleSheet('padding: 11px 20px; font-size: 14px; font-weight: 700;')
        forms_btn.clicked.connect(self.open_google_forms)
        online_btn_layout.addWidget(forms_btn)
        online_box.addLayout(online_btn_layout)
        outer.addWidget(online_group)

        # Local export section
        local_group = QGroupBox(tr('Option 2 — Exporter un rapport local (ZIP)'))
        local_box = QVBoxLayout(local_group)
        local_box.setSpacing(10)

        notice = QLabel(tr('Préparez un résumé, gérez vos captures d’écran et exportez une archive ZIP locale sur votre PC pour la partager.'))
        notice.setWordWrap(True)
        local_box.addWidget(notice)

        form = QFormLayout()
        form.setSpacing(10)
        self.title = QLineEdit()
        self.title.setPlaceholderText(tr('Ex: Problème d’alignement ou suggestion'))
        self.steps = QPlainTextEdit()
        self.steps.setMaximumHeight(75)
        self.steps.setPlaceholderText(tr('Ex: 1. Ouvrir le Finder, 2. Chercher Air India...'))
        self.expected = QLineEdit()
        self.observed = QPlainTextEdit()
        self.observed.setMaximumHeight(75)
        for label, widget in [('Résumé', self.title), ('Étapes pour reproduire', self.steps),
                              ('Résultat attendu', self.expected), ('Résultat observé', self.observed)]:
            form.addRow(tr(label), widget)
            widget.textChanged.connect(self.refresh)
        local_box.addLayout(form)

        # Attachments manager
        attach_box = QVBoxLayout()
        self.consent = QCheckBox(tr('J’autorise l’inclusion des captures d’écran sélectionnées'))
        self.consent.toggled.connect(self.refresh)
        attach_box.addWidget(self.consent)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(100)
        self.file_list.itemSelectionChanged.connect(self._selection_changed)
        self.file_list.itemDoubleClicked.connect(self.view_selected_image)
        attach_box.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton(tr('➕ Ajouter une capture…'))
        self.add_btn.clicked.connect(self.add_images)
        self.view_btn = QPushButton(tr('👁️ Voir l’image'))
        self.view_btn.setEnabled(False)
        self.view_btn.clicked.connect(self.view_selected_image)
        self.remove_btn = QPushButton(tr('🗑️ Retirer'))
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self.remove_selected_image)

        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.view_btn)
        btn_row.addWidget(self.remove_btn)
        attach_box.addLayout(btn_row)
        local_box.addLayout(attach_box)

        self.status = QLabel()
        self.status.setWordWrap(True)
        local_box.addWidget(self.status)

        preview_toggle = QPushButton(tr('Voir le contenu du rapport'))
        preview_toggle.setCheckable(True)
        local_box.addWidget(preview_toggle)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(160)
        self.preview.hide()
        preview_toggle.toggled.connect(self.preview.setVisible)
        local_box.addWidget(self.preview)

        export = QPushButton(tr('💾 Exporter le rapport ZIP sur mon PC'))
        export.clicked.connect(self.export)
        local_box.addWidget(export)

        outer.addWidget(local_group)
        self.refresh()

    def open_google_forms(self):
        opened = open_feedback_form()
        self.status.setText(tr('Formulaire ouvert dans votre navigateur Internet.') if opened else
                            tr('Impossible d’ouvrir le navigateur. Réessayez ou exportez un rapport local.'))

    def report(self):
        return {'application': 'RFS ATC Message Maker v5', 'system': platform.system(),
                'platform_release': platform.release(),
                'summary': self.title.text(), 'steps': self.steps.toPlainText(),
                'expected': self.expected.text(), 'observed': self.observed.toPlainText(),
                'attachments': [f'image-{i + 1}{p.suffix.lower()}' for i,p in enumerate(self.attachments)] if self.consent.isChecked() else []}

    def refresh(self, *_):
        if hasattr(self, 'preview'):
            self.preview.setPlainText(json.dumps(self.report(), ensure_ascii=False, indent=2))

    def add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, tr('Choisir des images'), '', 'Images (*.png *.jpg *.jpeg *.webp)')
        if not paths:
            return
        for p in paths:
            path = Path(p)
            if path in self.attachments:
                continue
            if len(self.attachments) >= 5:
                self.status.setText(tr('Maximum : 5 images au total.'))
                break
            try:
                size = path.stat().st_size
            except OSError:
                self.status.setText(tr('Impossible de lire cette image : {v0}', v0=path.name))
                continue
            if size > 10 * 1024 * 1024:
                self.status.setText(tr('Image trop volumineuse (max 10 Mo) : {v0}', v0=path.name))
                continue
            self.attachments.append(path)
        self.consent.setChecked(False)
        self._refresh_file_list()

    def _refresh_file_list(self):
        self.file_list.clear()
        for p in self.attachments:
            try:
                size_kb = round(p.stat().st_size / 1024)
                description = f"{p.name} ({size_kb} KB)"
            except OSError:
                description = tr('Image indisponible : {v0}', v0=p.name)
            item = QListWidgetItem(description)
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.file_list.addItem(item)
        count = len(self.attachments)
        self.status.setText(tr('{v0}/5 capture(s) sélectionnée(s). Double-cliquez pour voir.', v0=count) if count else '')
        self._selection_changed()
        self.refresh()

    def _selection_changed(self):
        has_sel = bool(self.file_list.selectedItems())
        self.view_btn.setEnabled(has_sel)
        self.remove_btn.setEnabled(has_sel)

    def view_selected_image(self):
        item = self.file_list.currentItem()
        if not item:
            return
        p_str = item.data(Qt.ItemDataRole.UserRole)
        if p_str:
            QDesktopServices.openUrl(QUrl.fromLocalFile(p_str))

    def remove_selected_image(self):
        row = self.file_list.currentRow()
        if 0 <= row < len(self.attachments):
            self.attachments.pop(row)
            self._refresh_file_list()

    def write_report(self, path):
        report = self.report()
        destination = Path(path)
        temporary = destination.with_name(destination.name + '.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('report.json', json.dumps(report, ensure_ascii=False, indent=2))
                for name, source in zip(report['attachments'], self.attachments):
                    archive.write(source, name)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def export(self):
        if not self.title.text().strip() or not self.observed.toPlainText().strip():
            self.status.setText(tr('Complétez le résumé et le résultat observé avant l’export.'))
            return
        name, _ = QFileDialog.getSaveFileName(self, tr('Exporter le rapport'), 'rapport-rfs.zip', 'ZIP (*.zip)')
        if name:
            try:
                self.write_report(name)
                self.status.setText(tr('Rapport exporté avec succès sur votre ordinateur.'))
            except OSError:
                self.status.setText(tr('Impossible d’écrire le rapport ou de lire une pièce jointe.'))
