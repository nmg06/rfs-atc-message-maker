"""Présentation, vols à plusieurs et modèles personnels, entièrement locaux."""
from __future__ import annotations

import re
from copy import deepcopy
from i18n import tr

from rfs_schema import FLIGHT_TYPES, FLIGHT_FIELDS, MESSAGE_FIELDS
from templates import render, format_runway
from validation import Issue, validate

DEFAULT_PRESENTATION = {"design": "Classique", "length": "Moyen", "emoji_style": "Aviation",
                        "discord_aligned": True, "custom_id": ""}
PILOT_FIELDS = ("name", "callsign", "aircraft", "airline", "livery", "departure_runway",
                "arrival_runway", "departure_gate", "arrival_gate")
OPERATION_LABELS = {"Indépendant": "", "En groupe": "Group", "Parallèle": "Parallel",
                    "Décalé": "Staggered"}
BUILTIN_DESIGNS = ("Classique", "Carte", "Tableau ATC", "Bulletin", "Minimal", "Bandeau", "Carnet")
EMOJI_STYLES = ("Aviation", "Alternatif", "Voyage", "Contrôle", "Cargo", "Nuit", "Océan", "Sans emojis")


def additional_pilots(flight: dict, kind: str | None = None) -> list[dict]:
    return [p for p in flight.get("pilots", []) if isinstance(p, dict)
            and (kind is None or kind in p.get("message_types", FLIGHT_TYPES))]


def pilot_flight(flight: dict, pilot: dict) -> dict:
    result = deepcopy(flight)
    result["pilots"] = []
    for key in PILOT_FIELDS:
        if key != "name" and str(pilot.get(key, "")).strip():
            result[key] = str(pilot[key]).strip()
    # An additional pilot must always supply their own callsign.
    result["callsign"] = str(pilot.get("callsign", "")).strip()
    result["radio_callsign"] = ""
    result["flight_number"] = ""
    return result


def validate_group(kind: str, flight: dict, data: dict, pilot_name: str) -> list[Issue]:
    data = procedure_data(kind, data)
    issues = validate(kind, flight, data, pilot_name)
    if kind not in FLIGHT_TYPES:
        return issues
    pilots = additional_pilots(flight, kind)
    if pilots and not str(flight.get("callsign", "")).strip():
        issues.append(Issue("callsign", tr("Le callsign du pilote principal est requis pour un vol à plusieurs.")))
    for index, pilot in enumerate(pilots, 2):
        name = str(pilot.get("name", "")).strip()
        if not name:
            issues.append(Issue("pilots", tr("Pilote {index} : pseudo requis.", index=index)))
        extra_data = dict(data)
        if kind == "AIRBORNE":
            extra_data["runway_used"] = ""
        for issue in validate(kind, pilot_flight(flight, pilot), extra_data, name):
            issues.append(Issue("pilots", tr("Pilote {index} : {text}", index=index, text=issue.text)))
    phases = ("departure", "arrival") if kind in ("FLIGHT PLAN", "DISPATCH FORM") else (
        ("departure",) if kind in ("ATC REQUEST", "AIRBORNE") else ("arrival",))
    for phase in phases:
        if flight.get(f"{phase}_mode") != "Parallèle":
            continue
        label = tr("départ") if phase == "departure" else tr("arrivée")
        if not pilots:
            issues.append(Issue("pilots", tr("Opération parallèle au {phase} : ajoutez au moins un autre pilote.", phase=label)))
        runways = [format_runway(str(flight.get(f"{phase}_runway", ""))).upper()]
        for index, pilot in enumerate(pilots, 2):
            runway = format_runway(str(pilot.get(f"{phase}_runway", ""))).upper()
            if not runway:
                issues.append(Issue("pilots", tr("Pilote {index} : indiquez sa piste de {phase} pour l'opération parallèle.", index=index, phase=label)))
            elif runway in runways:
                issues.append(Issue("pilots", tr("Pilote {index} : une opération parallèle exige une piste distincte au {phase}.", index=index, phase=label)))
            runways.append(runway)
    return issues


def procedure_data(kind, data):
    adjusted = dict(data)
    if kind == "ARRIVAL BOARD" and not data.get("go_around"):
        statuses = {"Go-around": "Go-around in progress", "Missed approach": "Missed approach",
                    "Holding": "Holding", "Diversion": "Diverting"}
        if data.get("procedure") in statuses:
            adjusted["status"] = statuses[data["procedure"]]
    return adjusted


def strip_emojis(text: str) -> str:
    return re.sub(r"[\U0001F1E6-\U0001FAFF\u2600-\u27BF\u231a\u231b\u23f0-\u23f3\ufe0e\ufe0f\u200d]", "", text)


def _unframe(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].startswith("╭") and lines[2].startswith("╰"):
        return "\n".join(lines[3:]).strip()
    return "\n".join(line for line in lines if not line.startswith(("╭", "╰"))).strip()


def _header(title: str, design: str) -> str:
    if design == "Bandeau":
        return f"══════ {title} ══════"
    if design == "Carnet":
        return f"[ {title} ]"
    if design == "Minimal":
        return title
    width = max(27, len(title) + 2)
    if design == "Carte":
        return f"┏{'━' * width}┓\n┃{title.center(width)}┃\n┗{'━' * width}┛"
    return f"╭{'─' * width}╮\n│{title.center(width)}│\n╰{'─' * width}╯"


def _shorten(text: str, flight: dict, kind: str) -> str:
    lines = []
    for line in text.splitlines():
        value = line.strip()
        if not value or value == "↘" or value.startswith(("🛫 ", "🛬 ")):
            if "DEPARTURES:" in value or "INBOUNDS:" in value:
                lines.append(value)
            continue
        clean = strip_emojis(value).strip()
        if clean.upper().startswith(("RADIO", "REQUESTING GROUND", "SERVER", "PAX", "CARGO", "FUEL", "LIVERY", "PASSENGERS",
                                     "CRUISE", "ROUTE", "DISTANCE", "ESTIMATED FLIGHT TIME", "ETE", "STAR", "ALTITUDE")):
            continue
        lines.append(value)
    if flight:
        phase = "arrival" if kind in ("ARRIVAL BOARD", "FLIGHT COMPLETED") else "departure"
        airport = str(flight.get(phase + "_icao", ""))
        if airport and not any(airport in line for line in lines):
            lines.insert(min(2, len(lines)), f"ICAO : {airport}")
    return "\n".join(lines)


def _one(kind: str, flight: dict, data: dict, name: str, length: str) -> str:
    adjusted = procedure_data(kind, data)
    if length == "Détaillé" and kind == "FLIGHT COMPLETED":
        adjusted["detailed"] = True
    text = _unframe(render(kind, flight, adjusted, name))
    if kind in ("ATC ACTIVE", "ATC OFFLINE"):
        text = "\n".join(text.splitlines()[1:]).strip()
    if kind == "FLIGHT PLAN":
        text = text.removeprefix("✈️ Flight Plan ✈️").strip()
        if flight.get("callsign"):
            text = "Callsign : " + str(flight["callsign"]) + "\n" + text
    if length == "Court":
        text = _shorten(text, flight if kind in FLIGHT_TYPES else {}, kind)
    elif length == "Détaillé" and kind in ("ATC REQUEST", "AIRBORNE", "ARRIVAL BOARD"):
        extra = []
        for key, label, suffix in (("passengers", "PASSENGERS", ""), ("cargo", "CARGO", " kg"),
                                   ("fuel", "FUEL", " kg")):
            value = str(flight.get(key, "")).strip()
            if value and label not in text:
                extra.append(f"{label} : {value}{suffix}")
        if extra:
            text += "\n\n" + "\n".join(extra)
    procedure = str(data.get("procedure", "")).strip()
    if procedure and procedure != "Standard" and not data.get("go_around"):
        text += f"\nPROCEDURE : {procedure}"
    note = str(data.get("procedure_note", "")).strip()
    if note:
        text += f"\n{note}"
    return text


def _mentions_outside(text: str) -> tuple[str, list[str]]:
    body, mentions = [], []
    for line in text.splitlines():
        if "@" in line:
            if line not in mentions:
                mentions.append(line)
        else:
            body.append(line)
    return "\n".join(body).strip(), mentions


def custom_context(kind: str, flight: dict, data: dict, pilot: str, message: str) -> dict:
    values = {key: "" for key in FLIGHT_FIELDS}
    for fields in MESSAGE_FIELDS.values():
        values.update({key: "" for key in fields})
    values.update({key: str(value) for key, value in {**flight, **data}.items() if not isinstance(value, (dict, list))})
    values.update(message=message, message_type=kind, pilot=pilot,
                  pilots=" / ".join([pilot] + [str(p.get("name", "")) for p in additional_pilots(flight)]))
    return values


def apply_custom(template: str, values: dict) -> str:
    """Only explicit {{tokens}} are substituted; no Python expressions are evaluated."""
    def replace(match):
        key = match.group(1)
        if key not in values:
            raise ValueError(tr("Variable inconnue : {key}", key=key))
        return values[key]
    return re.sub(r"\{\{\s*([a-z_]+)\s*\}\}", replace, template).strip()


def _group_identity(body, kind, flight, data, pilot, extra):
    """One shared message, compact paired pilot/callsign/aircraft/runway lines."""
    people = [(pilot, flight)] + [(p.get('name',''), pilot_flight(flight,p)) for p in extra]
    names = ' / '.join(name for name,_ in people)
    callsigns = ' / '.join(str(f.get('callsign','')) for _,f in people)
    aircraft = ' / '.join(f"{name}: {f.get('aircraft','')}" for name,f in people)
    lines = [f"PILOTS : {names}", f"CALLSIGNS : {callsigns}", f"AIRCRAFT : {aircraft}"]
    phases = ('departure','arrival') if kind in ('FLIGHT PLAN','DISPATCH FORM') else (
        ('departure',) if kind in ('ATC REQUEST','AIRBORNE') else ('arrival',))
    for phase in phases:
        parts = []
        for index,(name,f) in enumerate(people):
            runway = str(f.get(phase+'_runway',''))
            if index == 0 and kind == 'AIRBORNE':
                runway = data.get('runway_used') or runway
            if runway:
                parts.append(f"{name}: {format_runway(runway, with_prefix=True)}")
        if parts:
            lines.append(f"{phase.upper()} : " + ' / '.join(parts))
    kept=[]
    for line in body.splitlines():
        stripped=strip_emojis(line).strip().upper()
        if (stripped.startswith(('CALLSIGN','AIRCRAFT','PILOT','RUNWAY','DEPARTURE RUNWAY','ARRIVAL RUNWAY'))
            or line.strip().startswith('✈') or stripped.startswith('NAME:')):
            continue
        kept.append(line)
    return '\n'.join(lines) + '\n\n' + '\n'.join(kept).strip()


def _layout(body, design):
    if design == 'Bandeau':
        return '\n'.join('┃ ' + line if line.strip() else '┃' for line in body.splitlines())
    if design == 'Carnet':
        return '\n'.join(f'{i:02}  {line}' for i, line in enumerate((l for l in body.splitlines() if l.strip()), 1))
    if design == 'Carte':
        blocks = [b.strip() for b in body.split('\n\n') if b.strip()]
        return '\n─────────────── · ───────────────\n'.join(blocks)
    if design == 'Tableau ATC':
        rows=[]
        for line in body.splitlines():
            if ':' in line and not line.strip().startswith('@'):
                key,value=line.split(':',1)
                rows.append(f"{key.strip():<13} │ {value.strip()}")
            elif line.strip():
                rows.append(line.strip())
        return '\n'.join(rows)
    if design == 'Bulletin':
        rows=[]
        for line in body.splitlines():
            if ':' in line:
                key,value=line.split(':',1)
                rows.append(f"› {key.strip().title()} — {value.strip()}")
            else:
                rows.append(line)
        return '\n'.join(rows)
    if design == 'Minimal':
        return '\n'.join(line.strip() for line in body.splitlines() if line.strip())
    return body


def preview_text(text):
    if text.startswith(('```text\n','```\n')):
        lines=text.splitlines()[1:]
        if '```' in lines:
            lines.remove('```')
        return '\n'.join(lines).strip()
    return text


def clipboard_text(text, aligned=True):
    text=preview_text(text)
    if not aligned:
        return text
    body,mentions=_mentions_outside(text)
    body=body.replace('```', "'''")
    return '```\n'+body+'\n```'+ ('\n\n'+'\n'.join(mentions) if mentions else '')


def compose(kind: str, flight: dict, data: dict, pilot: str, presentation: dict | None = None,
            custom_design: dict | None = None) -> str:
    options = {**DEFAULT_PRESENTATION, **(presentation or {})}
    if custom_design and custom_design.get("base_design"):
        options["design"] = custom_design.get("base_design", options["design"])
    length, design = options["length"], options["design"]
    body = _one(kind, flight, data, pilot, length)
    extra = additional_pilots(flight, kind) if kind in FLIGHT_TYPES else []
    if extra:
        body = _group_identity(body, kind, flight, data, pilot, extra)
    body = _layout(body, design)
    operation = []
    if kind in FLIGHT_TYPES:
        phases = ("departure", "arrival") if kind in ("FLIGHT PLAN", "DISPATCH FORM") else (
            ("departure",) if kind in ("ATC REQUEST", "AIRBORNE") else ("arrival",))
        for phase in phases:
            mode = OPERATION_LABELS.get(flight.get(f"{phase}_mode", "Indépendant"), "")
            if mode:
                operation.append(f"OPERATION : {mode} {phase}")
    title = "ATC • ARRIVED" if kind == "FLIGHT COMPLETED" else kind
    text = "\n\n".join(part for part in (_header(title, design), "\n".join(operation), body) if part)
    if options["emoji_style"] == "Alternatif":
        for old, new in (("✈", "🛩"), ("📡", "📻"), ("🎧", "🎙"), ("🙏", "🤝")):
            text = text.replace(old, new)
    elif options['emoji_style'] in ('Voyage','Contrôle'):
        icons = ('🧳','📍','🏁','💬') if options['emoji_style']=='Voyage' else ('📡','↗','↘','✅')
        for old,new in zip(('✈','🛫','🛬','🙏'),icons):
            text=text.replace(old,new)
    elif options["emoji_style"] == "Sans emojis":
        text = strip_emojis(text)
    icons = {'Aviation':'✈️', 'Alternatif':'🛩️', 'Voyage':'🧳', 'Contrôle':'📡', 'Cargo':'📦', 'Nuit':'🌙', 'Océan':'🌊'}
    if options['emoji_style'] in icons:
        decoration = next((m for m in EMOJI_TOKEN.finditer(text)
                           if not 0x1F1E6 <= ord(m[0][0]) <= 0x1F1FF), None)
        if decoration:
            text = text[:decoration.start()] + icons[options['emoji_style']] + text[decoration.end():]
        else:
            text = text.replace('\n\n', '\n\n' + icons[options['emoji_style']] + ' ', 1)
    if custom_design and custom_design.get('guided'):
        text = '\n\n'.join(v for v in (custom_design.get('heading', '').strip(), text, custom_design.get('footer', '').strip()) if v)
    elif custom_design:
        text = apply_custom(custom_design.get("template", "{{message}}"), custom_context(kind, flight, data, pilot, text))
    if options["emoji_style"] == "Sans emojis":
        text = strip_emojis(text)
    elif kind != "DISPATCH FORM":
        text = limit_emojis(text, 6)
    # Deduplicate the shared role ping and keep all real mentions outside code blocks.
    text, mentions = _mentions_outside(text)
    if options["discord_aligned"]:
        text = text.replace("```", "'''")
        text = f"```\n{text}\n```"
    if mentions:
        text += "\n\n" + "\n".join(mentions)
    return text


EMOJI_TOKEN = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}|[\U0001F300-\U0001FAFF\u2600-\u27BF\u231a\u231b\u23f0-\u23f3](?:[\ufe0e\ufe0f]|\u200d.)*')


def limit_emojis(text, limit=6):
    tokens = list(EMOJI_TOKEN.finditer(text))
    # Flags carry route context; reserve their places before decoration.
    flags = [i for i, m in enumerate(tokens) if 0x1F1E6 <= ord(m[0][0]) <= 0x1F1FF]
    selected = set((flags + [i for i in range(len(tokens)) if i not in flags])[:limit])
    parts, last = [], 0
    for i, match in enumerate(tokens):
        parts += [text[last:match.start()], match[0] if i in selected else '']
        last = match.end()
    return ''.join(parts) + text[last:]
