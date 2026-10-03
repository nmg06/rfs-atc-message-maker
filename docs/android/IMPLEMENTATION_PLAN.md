# Android implementation plan

## Audit and source of truth

Baseline: GitHub `main` at `8747e0e5b4985eb6ddd540919ca659dca0b32622`.
The separate local Flightdeck delivery is newer, but is not silently substituted
for this repository. Windows files, tests and workflows remain authoritative and unchanged.

`rfs_schema.py` defines eight types: ATC REQUEST, AIRBORNE, ARRIVAL BOARD,
FLIGHT COMPLETED, ATC ACTIVE, ATC OFFLINE, FLIGHT PLAN and DISPATCH FORM.
PUSHBACK, TAXI and ATIS are additional requested Android types: no Windows
reference exists for these three. They must be documented as Android extensions.

`templates.py` renders English messages; `message_builder.py` applies seven designs,
three lengths, eight emoji choices, explicit templates, grouped pilots and operation
modes. `validation.py` and `validate_group` gate copy; edited previews retain these
checks. Discord alignment is added to clipboard text, not displayed in the editor.
`storage.py` uses four local JSON files; history compaction lives in `history_utils.py`.
Country names/flags and labels already exist in Python and must be exported automatically.

`finder/search.py` performs read-only SQLite filtering, scoring, diversification and
pagination with an explicit UTC clock. `time_utils.py` handles IANA zones/DST;
`mapping.py` preserves unknown manual fields and invalidates obsolete fuel calculations.
The import/download pipeline is development-only, not an Android dependency.
The database is ignored by Git and absent from a fresh clone. Its verified local
snapshot must be bundled with provenance, licences and SHA-256. No first-launch download.
Some durations in that supplied snapshot are estimates: Android must not label their
arithmetic bounds as observed percentiles. The repository's search semantics remain unchanged.

`fuel/calculator.py` is pure Python, with 63 exact aircraft variants, 64 arrivals,
static nearest alternates and half-even display rounding. `fuel/data` is also ignored:
prepare it from the tracked JSON reference files. The generated runtime JSON is
also checked in so a fresh Windows clone has its existing required resources.
No new formula or default alternate.

`ui.py`, `appearance.py`, `dialogs.py`, country picker and report dialog depend on Qt.
They provide the behavioral reference, not Android imports. All flight/message
fields, conditional fields, pilot selections, libraries, favourites and designs
must remain accessible in phone-oriented screens.

`mobile/index.html` supplies useful dark cards, touch sizing, tabs and preview actions,
but its generator implements only four types, ignores several presentation choices,
has no Finder, uses a manually entered alternate distance and incomplete validation.
Its localStorage model is not the PC model. Shipping it unchanged is rejected.

## Architecture

Small native Android host (Java, platform Activity), bundled HTML/CSS/JavaScript
interface, Chaquopy CPython 3.11 and the existing pure Python engines. This avoids
both Qt on Android and a second implementation of aviation rules. Python is embedded
inside the APK: the user installs no runtime. No Capacitor/React/npm runtime needed.
Android native services provide clipboard, sharing, document export/import and image
selection. The WebView only displays our new local interface; remote navigation and
requests are blocked. No INTERNET/storage permission, telemetry or external resources.

Versions pinned: AGP 8.7.3, Gradle 8.9, Chaquopy 16.1.0, Android API 35/minimum 24,
arm64-v8a and x86_64. Runtime assets include IANA tzdata. References:
[Chaquopy](https://chaquo.com/chaquopy/doc/current/android.html),
[compatibility](https://chaquo.com/chaquopy/doc/current/versions.html),
[local Android WebView assets](https://developer.android.com/develop/ui/views/layout/webapps/load-local-content).

## Verifiable stages

1. Audit, baseline Windows tests, parity table and deterministic packaging script.
2. Native host and async local bridge; private atomic state and backup/import validation.
3. Mobile flight, all eight Windows messages plus three extensions, editable preview,
   validated native copy, FR/EN, themes, pilots, libraries, designs and preferences.
4. Full Finder criteria, stable pagination, provenance and safe transfer; Fuel Helper
   using the unchanged Python calculator and explicit aircraft selection.
5. Python parity tests, Windows regression suite, JavaScript UI checks and Android
   instrumented tests for launch/restart/clipboard/database without Internet permission.
6. Real debug APK build, checksum/manifest inspection and device/emulator installation
   when available. Record unverified hardware checks honestly.
7. Separate GitHub Actions build/artifact workflow and reviewable GitHub branch/PR.
   No merge, public release or Google Play publication.

## Acceptance evidence

Document actual commands, counts, APK path and device checks in README/PARITY.
An APK build is not proof of installation, persistence or airplane-mode interaction.
Do not mark these checks OK without running them.
