"""Historical ETL mechanics use synthetic fixtures; never shipped as evidence."""
import contextlib
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from finder.importer import REQUIRED, build
from scripts.rebuild_historical_finder import entries_from_manifest, unpack_references, verify


class ManifestTests(unittest.TestCase):
    def test_frozen_references_match_manifest_and_keep_altered_cache(self):
        entries = entries_from_manifest()
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            unpack_references(cache, entries)
            for entry in entries:
                if not entry['file'].endswith('.parquet'):
                    verify(cache / entry['file'], entry)
            altered = cache / 'airlines.csv'
            altered.write_bytes(b'local alteration')
            with self.assertRaisesRegex(ValueError, 'manifest'):
                unpack_references(cache, entries)
            self.assertEqual(b'local alteration', altered.read_bytes())

    def test_pinned_quarters_and_no_runtime_download(self):
        entries = entries_from_manifest()
        quarters = {e["file"] for e in entries if e["file"].endswith(".parquet")}
        self.assertEqual({"2026_Q1_detailed_github.parquet", "2026_Q2_detailed_github.parquet"}, quarters)
        self.assertTrue(all(e["retrieved_at"] for e in entries))

    def test_manifest_rejects_traversal_duplicate_and_untrusted_flight_source(self):
        from scripts.rebuild_historical_finder import download_source
        good = {"file": "2026_Q1_detailed_github.parquet", "bytes": 1,
                "sha256": "a" * 64, "url": "https://github.com/MrAirspace/aircraft-flight-schedules/releases/download/aircraft_flight_schedules_2026_quarter1/2026_Q1_detailed_github.parquet"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            for url in ('file:///private-file', 'http://github.com/file.parquet', 'https://example.invalid/data.parquet'):
                with self.assertRaisesRegex(ValueError,'Unapproved flight source URL'):
                    download_source(Path(folder),dict(good,url=url))
            for entries in ([dict(good, file="../escape")], [good, good], [dict(good, bytes=True)],
                            [dict(good, url="https://example.invalid/dataset.parquet")]):
                path.write_text(json.dumps(entries), encoding="utf-8")
                with self.assertRaises(ValueError):
                    entries_from_manifest(path)

    def test_cached_source_is_verified_and_not_rewritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source"
            path.write_bytes(b"approved")
            entry = {"file": "source", "bytes": 8, "sha256": hashlib.sha256(b"approved").hexdigest()}
            verify(path, entry)
            path.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "manifest"):
                verify(path, entry)
            self.assertEqual(b"modified", path.read_bytes())


class HistoricalWindowTests(unittest.TestCase):
    def test_invalid_limits_fail_before_build_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "not-created.sqlite"
            for options in ({"window_days": 0}, {"window_days": True}, {"window_days": 1.5},
                            {"memory_mb": 1}, {"threads": 0}):
                with self.assertRaises(ValueError):
                    build(Path(folder), path, **options)
                self.assertFalse(path.exists())

    def test_extended_window_keeps_current_and_adds_only_ground_to_ground_duration(self):
        try:
            import duckdb
            import timezonefinder
        except ImportError:
            self.skipTest("Install requirements-etl.txt for full historical ETL tests")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def write_csv(name, fields, rows):
                with (root / name).open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(fields)
                    writer.writerows(rows)
            write_csv("airports.csv", ["id", "icao_code", "ident", "type", "name", "iata_code", "municipality", "iso_country", "iso_region", "continent", "latitude_deg", "longitude_deg"],
                      [(1, "LFPG", "LFPG", "large_airport", "Paris", "CDG", "Paris", "FR", "FR-IDF", "EU", 49, 2),
                       (2, "EGLL", "EGLL", "large_airport", "London", "LHR", "London", "GB", "GB-ENG", "EU", 51, -.4)])
            write_csv("runways.csv", ["id", "airport_ref", "le_ident", "he_ident", "length_ft", "width_ft", "surface", "lighted", "closed"], [])
            write_csv("airlines.csv", ["ICAO", "IATA", "Name"], [("AFR", "AF", "Air France")])
            write_csv("models-A.csv", ["ICAO", "Manufacturer", "Model", "IsActive"], [("A20N", "Airbus", "A320neo", 1)])
            quarters = {}
            for quarter, month in ((1, 1), (2, 6)):
                rows = []
                for suffix, ground in (("100", True), ("200", False)):
                    for day in (1, 2, 3):
                        row = {name: "-" for name in REQUIRED}
                        row.update(ICAO_Hex=f"fixture-{suffix}-{quarter}", AC_Type="A20N", AC_Type_Description="Airbus A320neo",
                                   Airline="AFR", Callsign="AFR" + suffix, Track_Origin_FL_Ft="ground",
                                   Track_Destination_FL_Ft="ground" if ground else "5000",
                                   Track_Origin_DateTime_UTC=f"2026-{month:02}-{day:02} 10:00:00",
                                   Track_Destination_DateTime_UTC=f"2026-{month:02}-{day:02} 11:30:00",
                                   Track_Origin_ApplicableAirports="['LFPG']", Track_Destination_ApplicableAirports="['EGLL']",
                                   Route_Validation_Based_on_Callsign="LFPG-EGLL")
                        rows.append(row)
                if quarter == 1:
                    # A source-quarter overlap is rejected, even with complete endpoints.
                    overlap = rows[0].copy()
                    overlap.update(Callsign="AFR999", ICAO_Hex="overlap",
                                   Track_Origin_DateTime_UTC="2026-06-01 10:00:00",
                                   Track_Destination_DateTime_UTC="2026-06-01 11:30:00")
                    rows.extend([overlap] * 3)
                file = root / f"2026_Q{quarter}_fixture.parquet"
                csv_path = f"quarter-{quarter}.csv"
                write_csv(csv_path, REQUIRED, [[r[k] for k in REQUIRED] for r in rows])
                connection = duckdb.connect()
                connection.execute("CREATE TABLE fixture AS SELECT * FROM read_csv(?, all_varchar=true)", [str(root / csv_path)])
                connection.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(file)])
                connection.close()
                quarters[quarter] = file
            for days in (90, 181):
                output = root / f"window-{days}.sqlite"
                with contextlib.redirect_stdout(io.StringIO()):
                    build(root, output, window_days=days, memory_mb=256, threads=1)
                with contextlib.closing(sqlite3.connect(output)) as database:
                    patterns = {r[0]: r[1:] for r in database.execute("SELECT callsign,n_obs,n_complete,duration_min,first_seen,last_seen FROM flight_patterns")}
                    self.assertNotIn("AFR999", patterns)
                    complete = patterns["AFR100"]
                    self.assertEqual(90.0, complete[2])
                    self.assertEqual(3 if days == 90 else 6, complete[1])
                    self.assertEqual(0, patterns["AFR200"][1])
                    self.assertIsNone(patterns["AFR200"][2])
                    self.assertEqual("2026-06-01" if days == 90 else "2026-01-01", complete[3][:10])
                    self.assertEqual("2026-06-03", complete[4][:10])
                    info = dict(database.execute("SELECT key,value FROM build_info"))
                    self.assertEqual(str(days), info["window_days"])
                    self.assertEqual("ok", database.execute("PRAGMA integrity_check").fetchone()[0])


class OverlayTests(unittest.TestCase):
    def test_overlay_restores_legacy_estimates_and_protects_observed(self):
        from scripts.apply_legacy_estimates_overlay import apply_overlay
        from finder.database import SCHEMA
        from finder.provenance import duration_provenance

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy_path = root / "legacy.sqlite"
            base_path = root / "base.sqlite"
            output_path = root / "final.sqlite"

            # Create legacy DB
            db = sqlite3.connect(legacy_path)
            db.executescript(SCHEMA)
            db.execute("INSERT INTO airports (id, icao, name, latitude, longitude) VALUES (1, 'LFPG', 'Paris', 49.0, 2.5), (2, 'EGLL', 'London', 51.5, -0.4)")
            db.execute("INSERT INTO airlines (icao, name) VALUES ('AFR', 'Air France')")
            db.execute("INSERT INTO aircraft_types (icao, model) VALUES ('A20N', 'A320neo'), ('B738', 'B738')")
            db.execute("""INSERT INTO flight_patterns
                (pattern_id, airline, callsign, origin_id, destination_id, aircraft, n_obs, n_complete, duration_min, distance_nm)
                VALUES (1, 'AFR', 'AFR101', 1, 2, 'A20N', 10, 0, 44.0, 188.16)""")
            db.execute("""INSERT INTO flight_patterns
                (pattern_id, airline, callsign, origin_id, destination_id, aircraft, n_obs, n_complete, duration_min, distance_nm)
                VALUES (2, 'AFR', 'AFR102', 1, 2, 'A20N', 10, 0, 44.0, 188.16)""")
            db.commit()
            db.close()

            # Create base candidate DB
            db = sqlite3.connect(base_path)
            db.executescript(SCHEMA)
            db.execute("INSERT INTO airports (id, icao, name, latitude, longitude) VALUES (1, 'LFPG', 'Paris', 49.0, 2.5), (2, 'EGLL', 'London', 51.5, -0.4)")
            db.execute("INSERT INTO airlines (icao, name) VALUES ('AFR', 'Air France')")
            db.execute("INSERT INTO aircraft_types (icao, model) VALUES ('A20N', 'A320neo'), ('B738', 'B738')")
            db.execute("""INSERT INTO flight_patterns
                (pattern_id, airline, callsign, origin_id, destination_id, aircraft, n_obs, n_complete, duration_min, distance_nm)
                VALUES (1, 'AFR', 'AFR101', 1, 2, 'A20N', 15, 0, NULL, 188.16)""")
            db.execute("""INSERT INTO flight_patterns
                (pattern_id, airline, callsign, origin_id, destination_id, aircraft, n_obs, n_complete, duration_min, distance_nm)
                VALUES (2, 'AFR', 'AFR102', 1, 2, 'B738', 20, 0, NULL, 188.16)""")
            db.execute("""INSERT INTO flight_patterns
                (pattern_id, airline, callsign, origin_id, destination_id, aircraft, n_obs, n_complete, duration_min, duration_p10, duration_p90, distance_nm)
                VALUES (3, 'AFR', 'AFR103', 1, 2, 'A20N', 30, 5, 52.0, 48.0, 55.0, 188.16)""")
            db.commit()
            db.close()

            report = apply_overlay(base_path, legacy_path, output_path)
            self.assertEqual(1, report["exact_legacy_keys_restored"])
            self.assertEqual(1, report["modal_shifted_legacy_routes_restored"])
            self.assertEqual(2, report["total_profiles_restored"])
            self.assertEqual("ok", report["integrity"])
            self.assertEqual(0, report["foreign_key_errors"])

            db = sqlite3.connect(output_path)
            db.row_factory = sqlite3.Row
            p1 = dict(db.execute("SELECT * FROM flight_patterns WHERE pattern_id = 1").fetchone())
            self.assertEqual(44.0, p1["duration_min"])
            self.assertIsNone(p1["duration_p10"])
            self.assertIsNone(p1["duration_p90"])
            self.assertEqual("ESTIMATED_DISTANCE_HEURISTIC", duration_provenance(p1))

            p2 = dict(db.execute("SELECT * FROM flight_patterns WHERE pattern_id = 2").fetchone())
            self.assertEqual(44.0, p2["duration_min"])
            self.assertIsNone(p2["duration_p10"])
            self.assertEqual("B738", p2["aircraft"])
            self.assertEqual("ESTIMATED_DISTANCE_HEURISTIC", duration_provenance(p2))

            p3 = dict(db.execute("SELECT * FROM flight_patterns WHERE pattern_id = 3").fetchone())
            self.assertEqual(52.0, p3["duration_min"])
            self.assertEqual(48.0, p3["duration_p10"])
            self.assertEqual(55.0, p3["duration_p90"])
            self.assertEqual("AGGREGATED_COMPLETE_TRACKS", duration_provenance(p3))
            db.close()


if __name__ == "__main__":
    unittest.main()
