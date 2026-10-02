# Repository audit — 2026-10-01

- Existing Python 3.13/PySide6 desktop app, no server. `main.py` starts `ui.RFSWindow`.
- `rfs_schema.py` defines flight/message fields. `templates.py` contains eight working English Discord templates; `message_builder.py` now wraps presentation and multi-pilot support without replacing them.
- `storage.Store` atomically persists local JSON: state, saved flights, presets, history and custom designs. `state['flight']` is shared by every flight message; saved flights contain copies of flight and per-type fields. Unknown additive keys survive loading.
- Frozen data is beside the executable (`data/`), source data beside `storage.py`; environment override supports isolated tests. Preserve installed data, never copy development data over it.
- No fuel calculation exists: fuel is user input. No aircraft/livery database, web backend or existing Finder.
- Existing tests cover templates, validation, state, GUI, presentation, pilots and copy/history. 21 tests pass before Finder integration. PyInstaller one-directory Windows build works; the spec excludes conflicting ICU DLLs from PATH.
- Integration: a separate `finder/` package and modeless/dialog view opened from the existing toolbar. An explicit mapping patches known current-flight values only. Finder failure must not prevent message generation.
- Specs arrived as `Downloads/files.zip`; all five read. Root `CODEX_TASK.md` describes an obsolete generic message generator and is not used for Finder.

## Current-work checkpoint
Dark popups/forms, multi-pilot operations, styles/custom designs, flags, copy feedback, history deduplication, procedures, icon and harmless welcome are implemented and tested. Native build generated successfully. Mobile/server/PWA are deferred by the latest request.
