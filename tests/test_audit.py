from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
import storage
from ui import RFSWindow
from validation import emoji_count
from message_builder import strip_emojis, limit_emojis, compose
from finder.search import search, Criteria
from test_finder import fixture, NOW
from test_rfs import sample_flight, sample_data

class EmojiRegression(unittest.TestCase):
    def test_non_emoji_symbols_and_accents(self):
        self.assertEqual(0, emoji_count('⌁⌀⛁➜⮕éà•'))
        self.assertEqual('⌁⌀⛁➜⮕éà•', strip_emojis('⌁⌀⛁➜⮕éà•'))
    def test_skin_tones_and_zwj(self):
        for text in ('👍🏽', '👩🏽‍✈️', '👨‍👩‍👧‍👦', '🇫🇷', '1️⃣', '1⃣'):
            with self.subTest(text=text): self.assertEqual(1, emoji_count(text))
    def test_text_variation_is_preserved(self):
        self.assertEqual(0, emoji_count('✈︎'))
        self.assertEqual('✈︎', strip_emojis('✈︎'))
    def test_limit_preserves_complete_clusters_and_flags(self):
        limited = limit_emojis('🇫🇷🇬🇧'+'👍🏽'*10)
        self.assertEqual('🇫🇷🇬🇧'+'👍🏽'*4, limited)
        self.assertEqual(6, emoji_count(limited))
        self.assertEqual('', strip_emojis('1️⃣👩🏽‍✈️🇫🇷'))

class FinderRegression(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'fixture.sqlite'
        fixture(self.path)
        with sqlite3.connect(self.path) as db:
            original=list(db.execute('SELECT * FROM flight_patterns WHERE pattern_id=1').fetchone())
            for i in range(100,1605):
                row=original.copy()
                row[0]=i; row[2]='AFR'+str(i); row[7]=100; row[8]=100
                row[10]=60+(i-100)/10
                db.execute('INSERT INTO flight_patterns VALUES ('+','.join('?' for _ in row)+')',row)
        db.close()
    def tearDown(self): self.temp.cleanup()
    def test_target_is_not_hidden_by_irrelevant_frequent_profiles(self):
        result=search(self.path,Criteria(target_minutes=600, tolerance_minutes=30, diversify=False),NOW)
        self.assertEqual([4,5], [r['pattern_id'] for r in result['results']])
    def test_pagination_keeps_same_population(self):
        a=search(self.path,Criteria(max_minutes=1200,limit=100,diversify=False),NOW)
        b=search(self.path,Criteria(max_minutes=1200,limit=100,offset=100,diversify=False),NOW)
        self.assertEqual(a['available'], b['available'])
        self.assertEqual(a['candidates'], b['candidates'])
        self.assertFalse({r['pattern_id'] for r in a['results']} & {r['pattern_id'] for r in b['results']})

class StorageRegression(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.paths=patch.multiple(storage,**{k:self.root/(k+'.json') for k in ('STATE_FILE','HISTORY_FILE','PRESETS_FILE','DESIGNS_FILE')})
        self.paths.start()
    def tearDown(self): self.paths.stop(); self.temp.cleanup()
    def test_concurrent_writes_both_complete_with_valid_json(self):
        destination=self.root/'state.json'; storage.save_json(destination,{'old':True})
        barrier=threading.Barrier(2); original=Path.replace; local=threading.local()
        def synchronized(p,target):
            if not getattr(local,'ready',False):
                barrier.wait(timeout=10)
                local.ready=True
            return original(p,target)
        with patch.object(Path,'replace',synchronized):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures=[executor.submit(storage.save_json,destination,{'writer':i}) for i in (1,2)]
                for f in futures: f.result(timeout=15)
        self.assertIn(json.loads(destination.read_text())['writer'], (1,2))
    def test_failed_store_operations_keep_prior_memory_and_disk(self):
        store=storage.Store(); store.save_design('old',{'name':'old','template':'{{message}}'})
        store.save_preset('old',{'flight':{}})
        before=(deepcopy(store.designs),deepcopy(store.presets),deepcopy(store.history))
        with patch('storage.save_json', side_effect=OSError('disk unavailable')):
            for call in (lambda:store.save_design('new',{'name':'new'}),lambda:store.save_preset('new',{}),lambda:store.add_history({'message_type':'ATC REQUEST','message':'test'})):
                with self.assertRaises(OSError): call()
        self.assertEqual(before,(store.designs,store.presets,store.history))
        self.assertEqual(before[0],json.loads(storage.DESIGNS_FILE.read_text()))

class UiRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.paths=patch.multiple(storage,**{k:self.root/(k+'.json') for k in ('STATE_FILE','HISTORY_FILE','PRESETS_FILE','DESIGNS_FILE')})
        self.paths.start(); self.window=RFSWindow()
    def tearDown(self):
        self.window.close(); self.app.processEvents(); self.paths.stop(); self.temp.cleanup()
    def test_save_flight_failure_does_not_announce_success(self):
        with patch('ui.QInputDialog.getText',return_value=('Audit test',True)), patch.object(self.window.store,'save_state',side_effect=OSError('disk unavailable')):
            self.window.save_current_flight()
        self.assertIn('impossible',self.window.status.text().casefold())
        self.assertEqual([],self.window.store.state['saved_flights'])
    def test_close_keeps_unsaved_window_open_on_failure(self):
        self.window.show(); self.app.processEvents()
        with patch.object(self.window.store,'save_state',side_effect=OSError('disk unavailable')):
            self.assertFalse(self.window.close())
            self.assertTrue(self.window.isVisible())
    def test_import_rejects_malformed_optional_design_fields(self):
        path=self.root/'design.json'; path.write_text(json.dumps({'name':'Broken','template':'{{message}}','guided':True,'heading':7}),encoding='utf8')
        with patch('ui.QFileDialog.getOpenFileName',return_value=(str(path),'')):
            self.window.import_design()
        self.assertEqual({},self.window.store.designs)
        self.assertIn('Import impossible',self.window.status.text())
    def test_immediate_copy_and_close_preserve_last_character(self):
        w=self.window
        w.store.state.update(flight=sample_flight(), per_type=sample_data())
        w._rebuild_forms(); w.flight_widgets['callsign'].setText('AUDIT999')
        w.copy_message()
        self.assertIn('AUDIT999',QApplication.clipboard().text())
        w.flight_widgets['callsign'].setText('AUDIT998')
        w.close()
        self.assertEqual('AUDIT998',json.loads(storage.STATE_FILE.read_text())['flight']['callsign'])
    def test_language_switch_preserves_preview_and_model(self):
        w=self.window; w.store.state.update(flight=sample_flight(),per_type=sample_data())
        w._rebuild_forms(); w.preview.setPlainText('Manual audit message')
        before=deepcopy(w.store.state['flight'])
        for code in ('en','fr','en','fr'):
            w.language_combo.setCurrentIndex(w.language_combo.findData(code))
            self.app.processEvents()
            self.assertEqual(before,w.store.state['flight'])
            self.assertEqual('Manual audit message',w.preview.toPlainText())
