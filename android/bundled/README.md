# Offline flight catalogue — 13 October 2026

Historical ADS-B profiles are not current scheduled flights. Airline/callsign/route
keys grew from 167,381 to 344,667 (2.059 times).
All 203,627 existing profile rows and 21,061 recent observed-route rows are preserved.
199,145 historical keys have a searchable duration. Other added keys
have unknown duration: never use partial timestamp spans as airborne flight times.

| Added quarter | New distinct keys |
|---|---:|
| 2025_Q4 | 50638 |
| 2025_Q3 | 30365 |
| 2025_Q2 | 19253 |
| 2025_Q1 | 31074 |
| 2024_Q4 | 29075 |
| 2024_Q3 | 16881 |

The separate DGCA Air India summer 2026 programme contains 1,573 seasonal variants,
785 distinct flight-number/route pairs, 770 flight numbers, and 1,988 published
movements from 37 pages. Validity ends on 24 October 2026. Local times, intermediate
stops and generic aircraft families are retained. 399 variants have a duration
from unambiguous paired domestic published times (scheduled block time, not an
observed airborne median). No foreign or overnight duration has been guessed.

Sources:
https://github.com/MrAirspace/aircraft-flight-schedules (ODbL 1.0, adsb.lol)
https://ourairports.com/data/ (public domain)
https://github.com/vradarserver/standing-data (CC0)
https://github.com/evansiroky/timezone-boundary-builder (ODbL 1.0)
https://public-prd-dgca.s3.ap-south-1.amazonaws.com/InventoryList/airOperation/certification/scheduled/domestic/AirIndiaLtd_SS_2026.pdf
https://public-prd-dgca.s3.ap-south-1.amazonaws.com/InventoryList/airOperation/certification/scheduled/domestic/AirIndiaflightSchedule-INT.pdf

DGCA facts: attribution to Directorate General of Civil Aviation, Government of
India. Public approved schedules do not prove actual operation. No licence grant
for the original PDFs is asserted; only normalised timetable facts are included.
Full build evidence, preserved-row checks and input hashes: aviation.report.json.
No account, network call or downloaded data is needed to search the bundled base.
