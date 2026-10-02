"""Regression tests for the user's v4 feedback; never read installed state."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import zipfile

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QSpinBox, QVBoxLayout, QWidget
import storage
from ui import RFSWindow
from finder.duration import parse_minutes
from finder.search import Criteria, search
from finder.ui import FinderDialog
from finder.rfs_catalogue import TYPE_BY_ID, records, observation_name
from country_search import resolve_country
from country_picker import CountryPicker
from fuel.ui import FuelDialog
from message_builder import compose, BUILTIN_DESIGNS, EMOJI_STYLES
from validation import emoji_count
from templates import format_touchdown
from i18n import set_language
from report_dialog import ReportDialog
from test_rfs import sample_flight, sample_data
from test_finder import fixture, NOW


class V4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(storage, **{k:self.root/(k+'.json') for k in
            ('STATE_FILE','HISTORY_FILE','PRESETS_FILE','DESIGNS_FILE')})
        self.paths.start()
        set_language('fr')

    def tearDown(self):
        for widget in self.app.topLevelWidgets():
            if isinstance(widget, FinderDialog) and widget.worker:
                widget.worker.wait(5000)
            widget.close()
        self.app.processEvents()
        self.paths.stop()
        self.temp.cleanup()
        set_language('fr')

    def test_clear_manual_saved_and_finder_flights_preserves_library(self):
        window = RFSWindow()
        window.store.state.update(pilot_name='Primary', pilot_library=[{'name':'Friend','callsign':'FRI2'}],
            saved_flights=[{'id':'saved','label':'Keep','flight':sample_flight()}])
        preserved = deepcopy({k:window.store.state[k] for k in ('pilot_name','pilot_library','saved_flights','presentation','theme')})
        for source in ('manual','saved','finder'):
            flight = sample_flight()
            if source == 'finder':
                flight.update(selected_flight={'pattern_id':3}, fuel_calculation={'total':123}, fuel_aircraft_id='id')
            window.store.state.update(flight=flight, per_type=sample_data(), current_flight_id='saved' if source=='saved' else '', preview_edits={'AIRBORNE':'old'})
            window.clear_current_message()
            self.assertEqual('', window.store.state['flight']['callsign'])
            self.assertNotIn('selected_flight',window.store.state['flight'])
            self.assertNotIn('fuel_calculation',window.store.state['flight'])
            self.assertEqual('',window.store.state['current_flight_id'])
            self.assertEqual({},window.store.state['preview_edits'])
            self.assertEqual('',window.store.state['per_type']['ATC REQUEST']['pushback'])
            for key,value in preserved.items():
                self.assertEqual(value,window.store.state[key],key)
            self.assertIn('Effacé',window.clear_button.text())

    def test_failed_copy_focus_marks_and_then_clears(self):
        window = RFSWindow()
        window.show()
        self.app.processEvents()
        QApplication.clipboard().setText('unchanged')
        window.copy_message()
        self.assertEqual('unchanged',QApplication.clipboard().text())
        self.assertFalse(window.can_copy)
        self.assertTrue(window.flight_widgets['airline'].property('invalid'))
        self.assertIn('⚠',window.flight_form.labelForField(window.flight_widgets['airline']).text())
        self.assertIn('color:',window.issues.styleSheet())
        window.flight_widgets['airline'].setCurrentText('Air France')
        window.render_preview()
        self.assertFalse(window.flight_widgets['airline'].property('invalid'))
        window.store.state.update(flight=sample_flight(),per_type=sample_data())
        window._rebuild_forms()
        window.copy_message()
        self.assertTrue(window.can_copy,window.issues.text())
        self.assertNotEqual('unchanged',QApplication.clipboard().text())

    def test_duration_units_and_legacy_bare_minutes(self):
        for text,expected in [('10h',600),('7 heures',420),('9h30',570),('03:00',180),('60 min',60),('10',10),('1,5h',90),('',None)]:
            self.assertEqual(expected,parse_minutes(text),text)
        for text in ('-1','nan','3:99','9h75','25h','10abc','0'):
            with self.assertRaises(ValueError,msg=text): parse_minutes(text)

    def test_strict_bounds_and_pagination_no_loss_or_duplicates(self):
        path=self.root/'aviation.sqlite';fixture(path)
        with sqlite3.connect(path) as db:
            row=list(db.execute('SELECT * FROM flight_patterns WHERE pattern_id=1').fetchone())
            for i in range(6,86):
                row[0]=i;row[2]=f'AFR{i}'
                db.execute('INSERT INTO flight_patterns VALUES ('+','.join('?' for _ in row)+')',row)
        db.close()
        full=search(path,Criteria(diversify=False,limit=100),NOW)
        paged=[]
        for offset in (0,30,60):
            page=search(path,Criteria(diversify=False,offset=offset),NOW)
            paged.extend(r['pattern_id'] for r in page['results'])
        self.assertEqual([r['pattern_id'] for r in full['results']],paged)
        self.assertEqual(len(set(paged)),len(paged))
        self.assertGreater(search(path,Criteria(),NOW)['diversity_dropped'],0)
        self.assertTrue(all(r['duration_min']>=420 for r in search(path,Criteria(min_minutes=420),NOW)['results']))
        self.assertTrue(all(r['duration_min']<=180 for r in search(path,Criteria(max_minutes=180),NOW)['results']))

    def test_enter_search_not_file_picker_and_results_invalidate(self):
        path=self.root/'aviation.sqlite';fixture(path)
        dialog=FinderDialog(None,path,'fr');dialog.show()
        dialog.fields['airline'].setText('AIC')
        with patch('finder.ui.QFileDialog.getOpenFileName') as picker:
            QTest.keyClick(dialog.fields['airline'],Qt.Key.Key_Return)
            for _ in range(500):
                QTest.qWait(10)
                if dialog.worker and dialog.worker.isFinished():break
            self.app.processEvents()
            picker.assert_not_called()
        self.assertTrue(dialog.results,dialog.status.text())
        dialog.fields['max_minutes'].setText('3h')
        self.assertEqual([],dialog.results)
        self.assertEqual(0,dialog.table.rowCount())
        self.assertFalse(dialog.use_button.isEnabled())
        self.assertEqual(180,dialog.criteria().max_minutes)
        dialog.fields['aircraft'].setText('Airbus A220-300')
        dialog.query = dialog.criteria()
        response = search(path, dialog.query, NOW)
        response['results'] = []
        dialog.search_revision = dialog.revision
        dialog.present(response)
        self.assertIn('Airbus A220-300', dialog.status.text())
        self.assertNotIn('rfs_aircraft_id', dialog.status.text())

    def test_catalogue_mapping_does_not_select_ambiguous_fuel_variant(self):
        self.assertEqual({r['id'] for r in records()},set(TYPE_BY_ID))
        self.assertEqual(TYPE_BY_ID['boeing_737_800'],TYPE_BY_ID['boeing_737_800bcf'])
        self.assertEqual('Boeing 737-800',observation_name('B738'))
        self.assertIsNone(TYPE_BY_ID['lockheed_c_5b_galaxy'])
        dialog=FuelDialog({'aircraft':'B738'})
        self.assertIsNone(dialog.aircraft.currentData())
        for i in range(1,dialog.aircraft.count()):
            self.assertNotIn('[',dialog.aircraft.itemText(i))
            self.assertIn(dialog.aircraft.itemData(i),TYPE_BY_ID)

    def test_countries_flags_and_accents(self):
        for query,code in [('FR','FR'),('France','FR'),('Romania','RO'),('România','RO'),('R Moldavie','MD'),('Moldova','MD')]:
            self.assertEqual(code,resolve_country(query))
        picker=CountryPicker()
        for text in ('FR','France'):
            picker.setEditText(text);picker.commit_country()
            self.assertIn('(FR)',picker.currentText())
            self.assertEqual('🇫🇷',picker.value())

    def test_wheel_never_changes_closed_combo_or_spinbox_but_scrolls(self):
        window=RFSWindow();window.show();self.app.processEvents()
        combo=window.flight_widgets['airline'];combo.addItems(['A','B','C']);combo.setCurrentIndex(0)
        bar=window.form_scroll.verticalScrollBar();bar.setValue(0)
        wheel=QWheelEvent(QPointF(8,8),QPointF(combo.mapToGlobal(QPoint(8,8))),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        QApplication.sendEvent(combo,wheel)
        self.assertEqual(0,combo.currentIndex());self.assertGreater(bar.value(),0)
        spin=QSpinBox(window);spin.setValue(8)
        QApplication.sendEvent(spin,wheel);self.assertEqual(8,spin.value())
        QTest.keyClick(combo,Qt.Key.Key_Down);self.assertEqual(1,combo.currentIndex())

    def test_language_switch_preserves_model_and_discord(self):
        window=RFSWindow();window.store.state.update(flight=sample_flight(),per_type=sample_data())
        window._rebuild_forms();window.render_preview()
        before=window.preview.toPlainText();flight=deepcopy(window.store.state['flight'])
        window.language_combo.setCurrentIndex(window.language_combo.findData('en'))
        self.assertEqual('Copy message',window.copy_button.text())
        self.assertIn('Current flight',window.flight_group.title())
        self.assertEqual('Medium',window.length_combo.itemText(1))
        self.assertEqual('Moyen',window.length_combo.currentText())
        self.assertEqual(before,window.preview.toPlainText())
        self.assertEqual(flight,window.store.state['flight'])
        self.assertEqual('en',storage.Store().state['language'])
        fuel=FuelDialog(sample_flight(),window)
        self.assertEqual('Calculate fuel',fuel.calculate_button.text())

    def test_old_language_migration_and_joke_independence(self):
        storage.save_json(storage.STATE_FILE,{'finder_language':'ro','intro_seen':False})
        store=storage.Store();self.assertEqual('fr',store.state['language']);self.assertTrue(store.state['joke_seen'])
        storage.save_json(storage.STATE_FILE,{'finder_language':'en','intro_seen':False})
        self.assertEqual('en',storage.Store().state['language'])
        window=RFSWindow();window.store.state.update(joke_seen=False,intro_seen=False)
        welcome=MagicMock();welcome.remember.isChecked.return_value=False
        with patch('ui.JokeDialog') as joke,patch('ui.WelcomeDialog',return_value=welcome) as intro,patch('ui.QMessageBox.information'),patch('ui.QInputDialog.getItem',return_value=('English',True)):
            window.show_welcome();window.show_welcome()
            self.assertEqual(1,joke.call_count);self.assertEqual(2,intro.call_count)
        restored=storage.Store();self.assertTrue(restored.state['joke_seen']);self.assertFalse(restored.state['intro_seen'])

    def test_touchdown_units(self):
        for value,expected in [('-250','-250 ft/min'),('-250 ft/min','-250 ft/min'),('','')]:
            self.assertEqual(expected,format_touchdown(value))

    def test_all_styles_lengths_emojis_groups_custom_limit(self):
        flight=sample_flight();flight['pilots']=[{'name':'Friend','callsign':'FRI2'}]
        for kind,data in sample_data().items():
            for design in BUILTIN_DESIGNS:
                for length in ('Court','Moyen','Détaillé'):
                    for emoji in EMOJI_STYLES:
                        text=compose(kind,flight,data,'Primary',{'design':design,'length':length,'emoji_style':emoji}, {'template':'✈️🌙📡📦🧳🌊😀{{message}}'})
                        if kind != 'DISPATCH FORM':
                            self.assertLessEqual(emoji_count(text),6,(kind,design,length,emoji))
        texts=[compose('ATC REQUEST',flight,sample_data()['ATC REQUEST'],'Primary',{'emoji_style':style,'design':'Minimal'}) for style in EMOJI_STYLES]
        self.assertEqual(len(texts),len(set(texts)))
        plain = compose('ATC REQUEST',sample_flight(),sample_data()['ATC REQUEST'],'Primary',{'emoji_style':'Aviation'})
        self.assertNotIn('✈️ ✈', plain)

    def test_report_exports_only_explicit_text_and_consented_attachments(self):
        dialog=ReportDialog();dialog.title.setText('Example');dialog.observed.setPlainText('Visible issue')
        image=self.root/'private-name.png';image.write_bytes(b'test fixture')
        dialog.attachments=[image]
        path=self.root/'report.zip';dialog.write_report(path)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(['report.json'],archive.namelist())
            self.assertNotIn(str(self.root),archive.read('report.json').decode())
        dialog.consent.setChecked(True);dialog.write_report(path)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(['report.json','image-1.png'],archive.namelist())
            self.assertEqual(b'test fixture',archive.read('image-1.png'))
