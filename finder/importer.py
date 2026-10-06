"""Build a compact, attributed SQLite DB from inspected public source files.

python -m finder.importer --input ../finder-inputs --output finder-data/aviation.sqlite
Build-time only dependencies: DuckDB, timezonefinder. No pandas.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3

from .database import SCHEMA

REQUIRED = ("ICAO_Hex", "AC_Type", "AC_Type_Description", "Airline", "Callsign",
            "Track_Origin_FL_Ft", "Track_Origin_DateTime_UTC", "Track_Origin_ApplicableAirports",
            "Track_Destination_FL_Ft", "Track_Destination_DateTime_UTC", "Track_Destination_ApplicableAirports",
            "Route_Validation_Based_on_Callsign")
SOURCES = [
    ("ourairports", "OurAirports", "https://ourairports.com/data/", "LicenseRef-Public-Domain",
     "Airport and available runway data: OurAirports (public domain)."),
    ("mrairspace", "MrAirspace / adsb.lol", "https://github.com/MrAirspace/aircraft-flight-schedules", "ODbL-1.0",
     "Flight observations: MrAirspace/aircraft-flight-schedules, derived from adsb.lol ADS-B data, ODbL 1.0."),
    ("vrs", "Virtual Radar Server", "https://github.com/vradarserver/standing-data", "CC0-1.0",
     "Airline and aircraft references, callsign route validation: Virtual Radar Server standing data (CC0)."),
    ("timezone", "timezone-boundary-builder", "https://github.com/evansiroky/timezone-boundary-builder", "ODbL-1.0",
     "Time zone boundaries: timezone-boundary-builder, © OpenStreetMap contributors, ODbL 1.0."),
]


def inspect_schema(connection, parquet: Path):
    schema = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()
    columns = {row[0]: row[1] for row in schema}
    missing = set(REQUIRED) - columns.keys()
    unexpected = {key: columns[key] for key in REQUIRED if key in columns and columns[key] != "VARCHAR"}
    if missing or unexpected:
        raise ValueError(f"Unsupported Parquet schema; missing={sorted(missing)}, types={unexpected}")
    return columns


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        yield from csv.DictReader(file)


def nullable(value, convert=str):
    return convert(value) if value not in (None, "", "-", "nan") else None


def family_for(icao):
    # Explicit, narrow ICAO family mapping; unknown families remain blank.
    families = {"A320": ("A318", "A319", "A320", "A321", "A19N", "A20N", "A21N"),
                "A330": ("A332", "A333", "A338", "A339"), "A350": ("A359", "A35K"),
                "B737": ("B736", "B737", "B738", "B739", "B37M", "B38M", "B39M", "B3XM"),
                "B777": ("B772", "B773", "B77L", "B77W"), "B787": ("B788", "B789", "B78X")}
    return next((name for name, codes in families.items() if icao in codes), None)


def distance_nm(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((phi2-phi1)/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 3440.065 * 2 * math.asin(min(1, math.sqrt(a)))


def build(input_dir: Path, output: Path, *, window_days: int = 90,
          parquet_files: list[Path] | None = None, source_manifest: Path | None = None,
          memory_mb: int = 1024, threads: int = 2):
    if isinstance(window_days, bool) or not isinstance(window_days, int) or not 1 <= window_days <= 3660:
        raise ValueError("window_days must be an integer between 1 and 3660")
    if isinstance(memory_mb, bool) or not isinstance(memory_mb, int) or not 64 <= memory_mb <= 8192:
        raise ValueError("memory_mb must be an integer between 64 and 8192")
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 16:
        raise ValueError("threads must be an integer between 1 and 16")
    import duckdb
    from timezonefinder import TimezoneFinder
    import importlib.metadata

    parquets = sorted(Path(p).resolve() for p in (parquet_files if parquet_files is not None else input_dir.glob("*.parquet")))
    if not parquets:
        raise ValueError("No real Parquet input found")
    if len(parquets) != len(set(parquets)):
        raise ValueError("Duplicate Parquet input")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".building")
    if temporary.exists():
        raise ValueError(f"Previous incomplete build exists: {temporary}; preserve or move it before retrying")
    work = duckdb.connect()
    work.execute(f"SET memory_limit='{memory_mb}MB'")
    work.execute(f"SET threads={threads}")
    work.execute("SET preserve_insertion_order=false")
    work.execute("SET TimeZone='UTC'")
    schema = {p.name: inspect_schema(work, p) for p in parquets}
    report = {"schema": schema, "versions": {name: importlib.metadata.version(name) for name in
               ("duckdb", "timezonefinder", "timezonefinder-data", "tzdata")}, "sources": []}
    manifest = source_manifest if source_manifest is not None else input_dir / "manifest.json"
    if manifest.is_file():
        report["sources"] = json.loads(manifest.read_text(encoding="utf-8"))
    db = sqlite3.connect(temporary)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO sources VALUES (?,?,?,?,?)", SOURCES)
    airports = {}
    print("Importing OurAirports references…", flush=True)
    for row in csv_rows(input_dir / "airports.csv"):
        icao = row.get("icao_code") or row["ident"]
        if not re.fullmatch(r"[A-Z]{4}", icao) or row["type"] == "closed":
            continue
        values = (int(row["id"]), icao, nullable(row["iata_code"]), row["name"], nullable(row["municipality"]),
                  nullable(row["iso_country"]), nullable(row["iso_region"]), nullable(row["continent"]),
                  float(row["latitude_deg"]), float(row["longitude_deg"]), None, row["type"])
        if icao not in airports:
            airports[icao] = values
            db.execute("INSERT INTO airports VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", values)
    ids = {row[0] for row in airports.values()}
    for row in csv_rows(input_dir / "runways.csv"):
        if int(row["airport_ref"]) in ids:
            db.execute("INSERT INTO runways VALUES (?,?,?,?,?,?,?,?,?)", (int(row["id"]), int(row["airport_ref"]),
                row["le_ident"], row["he_ident"], nullable(row["length_ft"], int), nullable(row["width_ft"], int),
                row["surface"], int(row["lighted"] or 0), int(row["closed"] or 0)))
    airlines = {}
    for row in csv_rows(input_dir / "airlines.csv"):
        code = row["ICAO"].strip()
        if re.fullmatch(r"[A-Z]{3}", code):
            airlines.setdefault(code, (code, nullable(row["IATA"]), row["Name"], None, None))
    db.executemany("INSERT INTO airlines VALUES (?,?,?,?,?)", airlines.values())
    models = {}
    for file in sorted(input_dir.glob("models-*.csv")):
        for row in csv_rows(file):
            code = row["ICAO"]
            if row["IsActive"] == "1":
                models.setdefault(code, (code, (row["Manufacturer"] + " " + row["Model"]).strip(),
                                         row["Manufacturer"], family_for(code)))
    # Native CSV ingestion avoids slow per-row Python->DuckDB binding on Windows.
    reference_csv = output.with_name(output.name + '.airport-reference.csv')
    with reference_csv.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('icao','id','latitude','longitude','tz'))
        writer.writerows((r[1],r[0],r[8],r[9],None) for r in airports.values())
    work.execute("CREATE TABLE airport_ref AS SELECT icao,cast(id AS BIGINT) id,cast(latitude AS DOUBLE) latitude,cast(longitude AS DOUBLE) longitude,cast(tz AS VARCHAR) tz FROM read_csv(?,all_varchar=true)", [str(reference_csv)])
    work.execute("CREATE TABLE airline_ref AS SELECT ICAO FROM read_csv(?,all_varchar=true) WHERE regexp_full_match(ICAO,'[A-Z]{3}')", [str(input_dir/'airlines.csv')])
    work.execute("CREATE TABLE clean(hex VARCHAR, airline VARCHAR, callsign VARCHAR, aircraft VARCHAR, description VARCHAR, origin VARCHAR, destination VARCHAR, dep TIMESTAMP, arr TIMESTAMP, complete BOOLEAN, duration DOUBLE)")
    source_count = 0
    valid_count = 0
    for parquet in parquets:
        print(f"Normalizing {parquet.name} with conservative endpoint resolution…", flush=True)
        quarter = re.search(r"(20\d{2})_Q([1-4])", parquet.name)
        if not quarter:
            raise ValueError("Parquet filename must identify its real year and quarter")
        year, q = map(int, quarter.groups())
        start = datetime(year, 3*q-2, 1)
        end = datetime(year+1, 1, 1) if q == 4 else datetime(year, 3*q+1, 1)
        source_count += work.execute("SELECT count(*) FROM read_parquet(?)", [str(parquet)]).fetchone()[0]
        projection = ",".join('"'+name+'"' for name in REQUIRED)
        # All interpolation is developer-owned column names. Paths/dates use bound parameters.
        work.execute(f"""INSERT INTO clean
        WITH raw AS (SELECT {projection} FROM read_parquet(?)),
        parsed AS (SELECT ICAO_Hex AS hex, Airline AS airline, Callsign AS callsign,
          AC_Type AS aircraft, AC_Type_Description AS description,
          TRY_CAST(Track_Origin_DateTime_UTC AS TIMESTAMP) AS dep,
          TRY_CAST(Track_Destination_DateTime_UTC AS TIMESTAMP) AS arr,
          lower(trim(Track_Origin_FL_Ft))='ground' AS dep_ground,
          lower(trim(Track_Destination_FL_Ft))='ground' AS arr_ground,
          regexp_extract_all(Track_Origin_ApplicableAirports, '''([A-Z0-9]{{4}})''', 1) AS oc,
          regexp_extract_all(Track_Destination_ApplicableAirports, '''([A-Z0-9]{{4}})''', 1) AS dc,
          CASE WHEN regexp_full_match(Route_Validation_Based_on_Callsign,'[A-Z0-9]{{4}}-[A-Z0-9]{{4}}') THEN split_part(Route_Validation_Based_on_Callsign,'-',1) END AS vo,
          CASE WHEN regexp_full_match(Route_Validation_Based_on_Callsign,'[A-Z0-9]{{4}}-[A-Z0-9]{{4}}') THEN split_part(Route_Validation_Based_on_Callsign,'-',2) END AS vd
          FROM raw),
        resolved AS (SELECT *,
          CASE WHEN len(oc)=1 AND dep_ground THEN oc[1] WHEN vo IS NOT NULL AND (len(oc)=0 OR list_contains(oc,vo)) THEN vo END AS origin,
          CASE WHEN len(dc)=1 AND arr_ground THEN dc[1] WHEN vd IS NOT NULL AND (len(dc)=0 OR list_contains(dc,vd)) THEN vd END AS destination
          FROM parsed)
        SELECT hex,airline,callsign,aircraft,description,origin,destination,dep,arr,
          coalesce(dep_ground AND arr_ground,false),epoch(arr-dep)/60
        FROM resolved WHERE dep>=? AND dep<? AND epoch(arr-dep)/60 BETWEEN 15 AND 1200
          AND origin IN (SELECT icao FROM airport_ref) AND destination IN (SELECT icao FROM airport_ref)
          AND origin != destination AND airline IN (SELECT icao FROM airline_ref)
          AND regexp_full_match(aircraft,'[A-Z0-9]{{2,4}}') AND regexp_full_match(callsign,'[A-Z0-9]{{3,12}}')
          AND hex IS NOT NULL AND hex NOT IN ('','-','nan')""", [str(parquet), start, end])  # nosec B608 - projection uses only REQUIRED constants; values are bound
    valid_count = work.execute("SELECT count(*) FROM clean").fetchone()[0]
    latest = work.execute("SELECT max(dep) FROM clean").fetchone()[0]
    if latest is None:
        raise ValueError("No usable observations; source schema or coverage needs investigation")
    work.execute("CREATE TABLE observations AS SELECT * EXCLUDE(rn) FROM (SELECT *, row_number() OVER (PARTITION BY hex,round(epoch(dep)/60),origin,destination ORDER BY complete DESC,arr,aircraft,callsign) rn FROM clean WHERE dep >= ? - (? * INTERVAL 1 DAY)) WHERE rn=1", [latest, window_days])
    work.execute("DROP TABLE clean")
    count = work.execute("SELECT count(*) FROM observations").fetchone()[0]
    print(f"{count:,} accepted observations. Resolving airport timezones…", flush=True)
    finder = TimezoneFinder(in_memory=True)
    used = work.execute("SELECT origin FROM observations UNION SELECT destination FROM observations").fetchall()
    zones = []
    for (code,) in used:
        row = airports[code]
        tz = finder.timezone_at(lat=row[8], lng=row[9])
        zones.append((code,tz))
        db.execute("UPDATE airports SET tz_iana=? WHERE icao=?", (tz, code))
    with reference_csv.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('icao','tz'))
        writer.writerows(zones)
    work.execute("UPDATE airport_ref SET tz=z.tz FROM read_csv(?,all_varchar=true) z WHERE airport_ref.icao=z.icao", [str(reference_csv)])
    for code, description in work.execute("SELECT aircraft,min(description) FROM observations GROUP BY aircraft ORDER BY aircraft").fetchall():
        models.setdefault(code, (code, nullable(description), None, family_for(code)))
    db.executemany("INSERT INTO aircraft_types VALUES (?,?,?,?)", models.values())
    print("Aggregating observed route/callsign patterns…", flush=True)
    work.execute("""CREATE TABLE timed AS SELECT x.*,o.id origin_id,d.id destination_id,
       o.latitude olat,o.longitude olon,d.latitude dlat,d.longitude dlon,
       CASE WHEN o.tz IS NOT NULL THEN timezone(o.tz,timezone('UTC',dep)) END local_dep
       FROM observations x JOIN airport_ref o ON x.origin=o.icao JOIN airport_ref d ON x.destination=d.icao""")
    work.execute("DROP TABLE observations")
    # Circular bins: start immediately after the largest gap, split gaps >90 minutes.
    work.execute("""CREATE TABLE minutes AS SELECT DISTINCT airline,callsign,origin,destination,
        hour(local_dep)*60+minute(local_dep) m FROM timed WHERE local_dep IS NOT NULL""")
    work.execute("""CREATE TABLE minute_gaps AS SELECT *,
        m-coalesce(lag(m) OVER w, max(m) OVER (PARTITION BY airline,callsign,origin,destination)-1440) gap
        FROM minutes WINDOW w AS (PARTITION BY airline,callsign,origin,destination ORDER BY m)""")
    work.execute("""CREATE TABLE anchors AS SELECT airline,callsign,origin,destination,
        arg_max(m,gap*1441+1440-m) anchor FROM minute_gaps GROUP BY ALL""")
    work.execute("""CREATE TABLE rotated AS SELECT m.*, (m.m-a.anchor+1440)%1440 rotated FROM minutes m JOIN anchors a USING(airline,callsign,origin,destination)""")
    work.execute("""CREATE TABLE clusters AS SELECT *, sum(new_cluster) OVER (PARTITION BY airline,callsign,origin,destination ORDER BY rotated) cluster_id FROM (
        SELECT *,CASE WHEN rotated-lag(rotated) OVER (PARTITION BY airline,callsign,origin,destination ORDER BY rotated)>90 THEN 1 ELSE 0 END new_cluster FROM rotated)""")
    work.execute("""CREATE TABLE grouped AS SELECT t.*,coalesce(c.cluster_id,0) cluster_id,c.rotated,a.anchor
        FROM timed t LEFT JOIN clusters c ON t.airline=c.airline AND t.callsign=c.callsign AND t.origin=c.origin AND t.destination=c.destination AND hour(t.local_dep)*60+minute(t.local_dep)=c.m
        LEFT JOIN anchors a ON t.airline=a.airline AND t.callsign=a.callsign AND t.origin=a.origin AND t.destination=a.destination
        ORDER BY t.airline,t.callsign,t.dep""")
    # Drop intermediate copies and aggregate one airline at a time to limit
    # DuckDB intermediates. Final profile/recent lists and timezone references
    # remain in Python memory, outside DuckDB's configured memory limit.
    for table in ('timed','minutes','minute_gaps','anchors','rotated','clusters'):
        work.execute('DROP TABLE ' + table)
    airline_codes = [r[0] for r in work.execute('SELECT DISTINCT airline FROM grouped ORDER BY airline').fetchall()]
    rows = []
    for code in airline_codes:
        rows.extend(work.execute("""SELECT airline,callsign,origin_id,destination_id,mode(aircraft ORDER BY aircraft),
        to_json(list(DISTINCT aircraft ORDER BY aircraft)),count(*),count(*) FILTER(WHERE complete),count(DISTINCT cast(dep AS DATE)),
        median(duration) FILTER(WHERE complete),quantile_cont(duration,.1) FILTER(WHERE complete),quantile_cont(duration,.9) FILTER(WHERE complete),
        first(olat),first(olon),first(dlat),first(dlon),
        (cast(median(rotated) AS INTEGER)+first(anchor))%1440, max(rotated)-min(rotated),
        bit_or(1 << (isodow(local_dep)-1)),min(dep),max(dep),max(dep),arg_max(arr,dep),cluster_id,origin,destination
        FROM grouped WHERE airline=? GROUP BY airline,callsign,origin_id,destination_id,cluster_id,origin,destination HAVING count(*)>=3
        ORDER BY airline,callsign,origin,destination,cluster_id""", [code]).fetchall())
    keys = {}
    for index, row in enumerate(rows, 1):
        row = list(row)
        distance = distance_nm(*row[12:16])
        if row[7] < 3:
            row[9:12] = [None, None, None]
        values = [index] + row[:12] + [distance] + row[16:19] + [v.replace(tzinfo=timezone.utc).isoformat() for v in row[19:23]] + ["mrairspace"]
        db.execute("INSERT INTO flight_patterns VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
        keys[(row[0], row[1], row[24], row[25], int(row[23]))] = index
    recent = work.execute("""SELECT airline,callsign,origin,destination,cluster_id,dep,arr,aircraft,complete FROM grouped
        QUALIFY row_number() OVER(PARTITION BY airline,callsign,origin,destination,cluster_id ORDER BY dep DESC,arr DESC,aircraft) <=5""").fetchall()
    for row in recent:
        index = keys.get(tuple(row[:5]))
        if index:
            db.execute("INSERT INTO recent_observations VALUES (?,?,?,?,?)", (index, row[5].replace(tzinfo=timezone.utc).isoformat(), row[6].replace(tzinfo=timezone.utc).isoformat(), row[7], int(row[8])))
    report.update(raw_rows=source_count, accepted_before_dedup_window=valid_count, retained_observations=count,
                  window_days=window_days, input_quarters=[p.name for p in parquets],
                  etl_memory_mb=memory_mb, etl_threads=threads,
                  rejected_before_dedup=source_count-valid_count, patterns=len(rows), airports=len(airports),
                  searchable_patterns=db.execute("SELECT count(*) FROM flight_patterns WHERE n_complete>=3").fetchone()[0],
                  last_observation=latest.replace(tzinfo=timezone.utc).isoformat(),
                  built_at=datetime.now(timezone.utc).isoformat())
    for key, value in report.items():
        db.execute("INSERT INTO build_info VALUES (?,?)", (key, value if isinstance(value,str) else json.dumps(value)))
    db.commit()
    report["integrity_check"] = db.execute("PRAGMA integrity_check").fetchone()[0]
    report["foreign_key_check"] = db.execute("PRAGMA foreign_key_check").fetchall()
    if report["integrity_check"] != "ok" or report["foreign_key_check"]:
        raise ValueError("Built database failed integrity checks")
    db.close()
    work.close()
    temporary.replace(output)
    output.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources','schema')}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window-days", type=int, default=90,
                        help="Historical retention relative to the latest source departure (default: 90)")
    parser.add_argument("--parquet", type=Path, action="append", dest="parquet_files",
                        help="Explicit source quarter; repeat to combine verified historical quarters")
    parser.add_argument("--manifest", type=Path, dest="source_manifest",
                        help="Provenance manifest copied into the report; historical rebuild verifies hashes")
    parser.add_argument("--memory-mb", type=int, default=1024,
                        help="DuckDB memory limit for build only (default: 1024)")
    parser.add_argument("--threads", type=int, default=2,
                        help="DuckDB threads for build only (default: 2)")
    args = parser.parse_args()
    build(args.input, args.output, window_days=args.window_days,
          parquet_files=args.parquet_files, source_manifest=args.source_manifest,
          memory_mb=args.memory_mb, threads=args.threads)
