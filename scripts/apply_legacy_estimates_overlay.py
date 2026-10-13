"""Apply conservative legacy duration estimates overlay to candidate rebuild.

Preserves exact legacy duration estimates from 0.4.2 without inventing formulas,
without adding fake percentiles, while respecting all newly observed durations
(n_complete >= 3) and maintaining full ESTIMATED_DISTANCE_HEURISTIC provenance.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finder.provenance import duration_provenance


def apply_overlay(base_path: Path, legacy_path: Path, output_path: Path, report_path: Path | None = None) -> dict:
    base_path = Path(base_path).resolve()
    legacy_path = Path(legacy_path).resolve()
    output_path = Path(output_path).resolve()

    if not base_path.is_file():
        raise FileNotFoundError(f"Base candidate database not found: {base_path}")
    if not legacy_path.is_file():
        raise FileNotFoundError(f"Legacy database not found: {legacy_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_suffix(".overlay.tmp")
    if temp_output.exists():
        temp_output.unlink()

    print(f"Copying base database {base_path.name} to {temp_output.name}…", flush=True)
    shutil.copy2(base_path, temp_output)

    legacy_con = sqlite3.connect(legacy_path.as_uri() + "?mode=ro", uri=True)
    legacy_con.row_factory = sqlite3.Row
    out_con = sqlite3.connect(temp_output)
    out_con.row_factory = sqlite3.Row

    try:
        # 1. Integrity check base copy
        int_check = out_con.execute("PRAGMA integrity_check").fetchone()[0]
        fk_check = out_con.execute("PRAGMA foreign_key_check").fetchall()
        if int_check != "ok" or fk_check:
            raise ValueError(f"Base database copy failed checks: int={int_check}, fk={fk_check}")

        # 2. Extract legacy estimates
        # All legacy rows with duration_min IS NOT NULL and n_complete < 3
        legacy_rows = legacy_con.execute("""
            SELECT p.airline, p.callsign, o.icao AS origin, d.icao AS destination,
                   p.aircraft, p.duration_min, p.distance_nm, p.n_complete
            FROM flight_patterns p
            JOIN airports o ON o.id=p.origin_id
            JOIN airports d ON d.id=p.destination_id
            WHERE p.duration_min IS NOT NULL AND p.n_complete < 3
        """).fetchall()

        print(f"Found {len(legacy_rows)} legacy estimated profiles in {legacy_path.name}.", flush=True)

        # Build airport mapping for output
        airports = dict(out_con.execute("SELECT icao, id FROM airports").fetchall())

        # Build lookup of output patterns where duration is NULL
        # exact_key: (airline, callsign, origin, destination, aircraft) -> list of pattern_ids
        # route_key: (airline, callsign, origin, destination) -> list of pattern_ids
        # observed_routes: set of (airline, callsign, origin, destination) having an observed duration
        null_exact_patterns: dict[tuple, list[int]] = {}
        null_route_patterns: dict[tuple, list[int]] = {}
        observed_exact_keys: set[tuple] = set()
        observed_route_keys: set[tuple] = set()

        for row in out_con.execute("""
            SELECT p.pattern_id, p.airline, p.callsign, o.icao AS origin, d.icao AS destination,
                   p.aircraft, p.duration_min, p.n_complete, p.distance_nm
            FROM flight_patterns p
            JOIN airports o ON o.id=p.origin_id
            JOIN airports d ON d.id=p.destination_id
        """):
            ek = (row["airline"], row["callsign"], row["origin"], row["destination"], row["aircraft"])
            rk = (row["airline"], row["callsign"], row["origin"], row["destination"])
            if row["duration_min"] is not None and row["n_complete"] >= 3:
                observed_exact_keys.add(ek)
                observed_route_keys.add(rk)
            elif row["duration_min"] is None:
                null_exact_patterns.setdefault(ek, []).append(row["pattern_id"])
                null_route_patterns.setdefault(rk, []).append(row["pattern_id"])

        exact_matches_restored = 0
        exact_pattern_ids_restored = set()
        promoted_to_observed_exact = 0

        route_matches_restored = 0
        route_pattern_ids_restored = set()
        promoted_to_observed_route = 0

        unmatched = 0

        # Pass 1: exact matches
        remaining_legacy = []
        for lr in legacy_rows:
            ek = (lr["airline"], lr["callsign"], lr["origin"], lr["destination"], lr["aircraft"])
            if ek in observed_exact_keys:
                promoted_to_observed_exact += 1
                continue
            candidates = null_exact_patterns.get(ek, [])
            if candidates:
                for pid in candidates:
                    out_con.execute("""
                        UPDATE flight_patterns
                        SET duration_min = ?, duration_p10 = NULL, duration_p90 = NULL
                        WHERE pattern_id = ? AND duration_min IS NULL
                    """, (lr["duration_min"], pid))
                    exact_pattern_ids_restored.add(pid)
                exact_matches_restored += 1
            else:
                remaining_legacy.append(lr)

        print(f"Pass 1: Restored {exact_matches_restored} legacy exact keys ({len(exact_pattern_ids_restored)} profile rows). Promoted to observed: {promoted_to_observed_exact}.", flush=True)

        # Pass 2: route matches for modal-shifted aircraft
        for lr in remaining_legacy:
            rk = (lr["airline"], lr["callsign"], lr["origin"], lr["destination"])
            if rk in observed_route_keys:
                promoted_to_observed_route += 1
                continue
            candidates = null_route_patterns.get(rk, [])
            # Filter candidates that are still null (not updated in pass 1)
            still_null = [pid for pid in candidates if pid not in exact_pattern_ids_restored]
            if still_null:
                for pid in still_null:
                    out_con.execute("""
                        UPDATE flight_patterns
                        SET duration_min = ?, duration_p10 = NULL, duration_p90 = NULL
                        WHERE pattern_id = ? AND duration_min IS NULL
                    """, (lr["duration_min"], pid))
                    route_pattern_ids_restored.add(pid)
                route_matches_restored += 1
            else:
                unmatched += 1

        print(f"Pass 2: Restored {route_matches_restored} route matches ({len(route_pattern_ids_restored)} profile rows). Promoted to observed: {promoted_to_observed_route}. Unmatched: {unmatched}.", flush=True)

        total_profiles_updated = len(exact_pattern_ids_restored | route_pattern_ids_restored)

        # 3. Validation
        # Verify that all updated rows have duration_provenance == 'ESTIMATED_DISTANCE_HEURISTIC'
        invalid_provenance = 0
        for pid in (exact_pattern_ids_restored | route_pattern_ids_restored):
            row = dict(out_con.execute("SELECT * FROM flight_patterns WHERE pattern_id = ?", (pid,)).fetchone())
            prov = duration_provenance(row)
            if prov != "ESTIMATED_DISTANCE_HEURISTIC":
                invalid_provenance += 1

        if invalid_provenance > 0:
            raise ValueError(f"Corrupted provenance in {invalid_provenance} updated profiles!")

        # Verify no observed durations were overwritten
        touched_observed = out_con.execute("""
            SELECT count(*) FROM flight_patterns
            WHERE n_complete >= 3 AND (duration_min IS NULL OR duration_p10 IS NULL OR duration_p90 IS NULL)
        """).fetchone()[0]
        if touched_observed > 0:
            raise ValueError("Observed complete tracks durations were improperly modified!")

        # Update build_info
        now_iso = datetime.now(timezone.utc).isoformat()
        total_searchable = out_con.execute("SELECT count(*) FROM flight_patterns WHERE duration_min IS NOT NULL").fetchone()[0]
        observed_searchable = out_con.execute("SELECT count(*) FROM flight_patterns WHERE duration_min IS NOT NULL AND n_complete >= 3").fetchone()[0]

        meta = {
            "legacy_overlay_applied": now_iso,
            "legacy_overlay_source": legacy_path.name,
            "legacy_overlay_exact_profiles_restored": len(exact_pattern_ids_restored),
            "legacy_overlay_modal_shifted_profiles_restored": len(route_pattern_ids_restored),
            "legacy_overlay_total_profiles_restored": total_profiles_updated,
            "legacy_overlay_promoted_to_observed": promoted_to_observed_exact + promoted_to_observed_route,
            "total_searchable_patterns": total_searchable,
            "observed_searchable_patterns": observed_searchable,
        }

        for k, v in meta.items():
            out_con.execute("INSERT OR REPLACE INTO build_info VALUES (?, ?)", (k, str(v)))

        out_con.commit()

        # Run VACUUM and final PRAGMA checks
        print("Running VACUUM and integrity checks…", flush=True)
        out_con.execute("VACUUM")
        int_check = out_con.execute("PRAGMA integrity_check").fetchone()[0]
        fk_check = out_con.execute("PRAGMA foreign_key_check").fetchall()
        if int_check != "ok" or fk_check:
            raise ValueError(f"Final database failed integrity checks: int={int_check}, fk={fk_check}")

        out_con.close()
        legacy_con.close()

        if output_path.exists():
            output_path.unlink()
        temp_output.replace(output_path)
        print(f"Overlay successfully written to {output_path} ({output_path.stat().st_size:,} bytes).", flush=True)

        audit_result = {
            "output_bytes": output_path.stat().st_size,
            "total_legacy_estimates_in_source": len(legacy_rows),
            "exact_legacy_keys_restored": exact_matches_restored,
            "exact_profiles_updated": len(exact_pattern_ids_restored),
            "modal_shifted_legacy_routes_restored": route_matches_restored,
            "modal_shifted_profiles_updated": len(route_pattern_ids_restored),
            "total_profiles_restored": total_profiles_updated,
            "promoted_to_observed_exact": promoted_to_observed_exact,
            "promoted_to_observed_route": promoted_to_observed_route,
            "total_promoted_to_observed": promoted_to_observed_exact + promoted_to_observed_route,
            "unmatched_legacy_routes": unmatched,
            "total_searchable_patterns": total_searchable,
            "observed_searchable_patterns": observed_searchable,
            "integrity": int_check,
            "foreign_key_errors": len(fk_check),
        }

        if report_path:
            report_path = Path(report_path)
            report_path.write_text(json.dumps(audit_result, indent=2), encoding="utf-8")

        return audit_result

    finally:
        out_con.close()
        legacy_con.close()
        if temp_output.exists():
            temp_output.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="Base Q1-Q2 reconstructed sqlite")
    parser.add_argument("--legacy", type=Path, required=True, help="Legacy Q2-before sqlite")
    parser.add_argument("--output", type=Path, required=True, help="Output destination sqlite")
    parser.add_argument("--report", type=Path, help="JSON audit report")
    args = parser.parse_args()
    res = apply_overlay(args.base, args.legacy, args.output, args.report)
    print(json.dumps(res, indent=2))
