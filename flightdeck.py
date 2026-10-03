"""Flight-centred desktop shell. Existing message and storage logic stays in ui.py."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QMenu, QSizePolicy,
)
from i18n import language


def tx(fr, en):
    return fr if language() == 'fr' else en


def card(title, value='—'):
    panel = QFrame(objectName='metricCard')
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(6)
    layout.addWidget(QLabel(title, objectName='eyebrow'))
    label = QLabel(value, objectName='metricValue')
    label.setWordWrap(True)
    layout.addWidget(label)
    return panel, label


def install_shell(w, old):
    """Move the proven editor controls into a new, separate workspace."""
    root = QWidget(objectName='appRoot')
    shell = QHBoxLayout(root)
    shell.setContentsMargins(0, 0, 0, 0)
    shell.setSpacing(0)
    rail = QFrame(objectName='navRail')
    rail.setFixedWidth(178)
    nav = QVBoxLayout(rail)
    nav.setContentsMargins(16, 27, 16, 20)
    nav.setSpacing(9)
    logo = QLabel('RFS', objectName='brandMark')
    nav.addWidget(logo)
    nav.addWidget(QLabel('F L I G H T D E C K', objectName='brandCaption'))
    nav.addSpacing(32)
    nav.addWidget(QLabel(tx('ESPACE DE VOL', 'FLIGHT WORKSPACE'), objectName='navCaption'))
    w.deck_nav = []
    for index, title in enumerate((tx('Vue du vol', 'Flight overview'), tx('Messages', 'Messages'))):
        button = QPushButton(title)
        button.setObjectName('navItem')
        button.setCheckable(True)
        button.clicked.connect(lambda checked=False, page=index: show_page(w, page))
        nav.addWidget(button)
        w.deck_nav.append(button)
    nav.addSpacing(22)
    nav.addWidget(QLabel(tx('OUTILS', 'TOOLS'), objectName='navCaption'))
    for button, text in ((w.finder_button, tx('Rechercher un vol', 'Find a flight')),
                         (w.fuel_button, tx('Carburant', 'Fuel planner'))):
        button.setText(text)
        button.setObjectName('navItem')
        nav.addWidget(button)
    library = QPushButton(tx('Bibliothèque', 'Library'), objectName='navItem')
    library.setMenu(QMenu(library))
    for fr, en, callback in (
        ('Sauver un favori', 'Save favourite', w.save_preset),
        ('Charger un favori', 'Load favourite', w.load_preset),
        ('Historique des messages', 'Message history', w.open_history),
    ):
        library.menu().addAction(tx(fr, en), callback)
    nav.addWidget(library)
    nav.addStretch()
    nav.addWidget(QLabel(tx('PILOTE RFS', 'RFS PILOT'), objectName='navCaption'))
    w.pilot_name.setMinimumWidth(0)
    nav.addWidget(w.pilot_name)
    help_button = QPushButton(tx('Aide et suggestions', 'Help and feedback'), objectName='navItem')
    # A QMenu must retain popup window flags; create a proper menu here.
    w.help_menu = QMenu(help_button)
    w.help_menu.addAction(tx('Formulaire en ligne — problème ou suggestion', 'Online form — issue or suggestion'), w.open_feedback_form)
    w.help_menu.addAction(tx('Rapport local et pièces jointes…', 'Local report and attachments…'), w.open_report)
    help_button.setMenu(w.help_menu)
    nav.addWidget(help_button)
    local = QLabel(tx('LOCAL  /  SANS COMPTE', 'LOCAL  /  NO ACCOUNT'), objectName='navCaption')
    nav.addWidget(local)
    shell.addWidget(rail)
    content = QWidget()
    outer = QVBoxLayout(content)
    outer.setContentsMargins(26, 22, 26, 22)
    outer.setSpacing(16)
    top = QHBoxLayout()
    heading = QVBoxLayout()
    heading.setSpacing(3)
    heading.addWidget(QLabel(tx('VOTRE PROCHAINE DESTINATION', 'YOUR NEXT DESTINATION'), objectName='eyebrow'))
    w.deck_title = QLabel(objectName='deckTitle')
    heading.addWidget(w.deck_title)
    top.addLayout(heading, 1)
    w.language_combo.setMinimumWidth(102)
    top.addWidget(w.language_combo)
    top.addWidget(w.theme_button)
    w.visual_theme_combo.setMaximumWidth(120)
    top.addWidget(w.visual_theme_combo)
    outer.addLayout(top)
    commands = QHBoxLayout()
    commands.addWidget(QLabel(tx('MESSAGE', 'MESSAGE'), objectName='eyebrow'))
    w.message_type.setMinimumWidth(190)
    commands.addWidget(w.message_type)
    commands.addStretch()
    commands.addWidget(w.pilots_button)
    outer.addLayout(commands)

    w.deck_pages = QStackedWidget()
    outer.addWidget(w.deck_pages, 1)
    home = QWidget()
    home_layout = QVBoxLayout(home)
    home_layout.setContentsMargins(0, 0, 0, 0)
    home_layout.setSpacing(14)
    route_bar = QHBoxLayout()
    w.deck_route = QLabel(objectName='routeHeadline')
    w.deck_route.setWordWrap(True)
    route_bar.addWidget(w.deck_route, 1)
    edit = QPushButton(tx('Modifier le vol', 'Edit flight'))
    edit.clicked.connect(lambda: show_page(w, 1))
    route_bar.addWidget(edit)
    home_layout.addLayout(route_bar)
    map_frame = QFrame(objectName='mapCard')
    map_layout = QVBoxLayout(map_frame)
    map_layout.setContentsMargins(1, 1, 1, 1)
    from route_map import RouteMap
    w.route_map = RouteMap(map_frame)
    w.route_map.setMinimumHeight(235)
    map_layout.addWidget(w.route_map, 1)
    map_layout.addWidget(w.route_map.create_country_controls(map_frame))
    w.route_map.countries_selected.connect(lambda origin, destination: w.open_finder({'origin_country': origin, 'destination_country': destination}))
    home_layout.addWidget(map_frame, 1)
    stats = QHBoxLayout()
    stats.setSpacing(12)
    w.deck_metrics = {}
    for key, title in (('aircraft', tx('APPAREIL / CALLSIGN', 'AIRCRAFT / CALLSIGN')),
                       ('duration', tx('DURÉE RENSEIGNÉE', 'ENTERED DURATION')),
                       ('fuel', tx('CARBURANT RENSEIGNÉ', 'ENTERED FUEL'))):
        panel, label = card(title)
        stats.addWidget(panel, 1)
        w.deck_metrics[key] = label
    home_layout.addLayout(stats)
    ready = QFrame(objectName='dispatchStrip')
    ready_layout = QHBoxLayout(ready)
    ready_layout.setContentsMargins(18, 14, 18, 14)
    readiness = QVBoxLayout()
    readiness.addWidget(QLabel(tx('VOTRE MESSAGE, AU BON MOMENT', 'YOUR MESSAGE, AT THE RIGHT TIME'), objectName='eyebrow'))
    w.deck_readiness = QLabel()
    w.deck_readiness.setWordWrap(True)
    readiness.addWidget(w.deck_readiness)
    ready_layout.addLayout(readiness, 1)
    continue_button = QPushButton(tx('Préparer le message', 'Prepare message'), objectName='primary')
    continue_button.clicked.connect(lambda: show_page(w, 1))
    ready_layout.addWidget(continue_button)
    home_layout.addWidget(ready)
    phase_row = QHBoxLayout()
    w.phase_buttons = []
    for kind, fr, en in (
        ('ATC REQUEST', '01  Au départ', '01  Departure'),
        ('AIRBORNE', '02  En vol', '02  Airborne'),
        ('ARRIVAL BOARD', '03  En approche', '03  Approach'),
        ('FLIGHT COMPLETED', '04  Arrivé', '04  Arrived'),
    ):
        button = QPushButton(tx(fr, en), objectName='phaseStep')
        button.setCheckable(True)
        def choose(checked=False, value=kind):
            w.message_type.setCurrentText(value)
            show_page(w, 1)
        button.clicked.connect(choose)
        phase_row.addWidget(button, 1)
        w.phase_buttons.append((kind, button))
    home_layout.addLayout(phase_row)
    w.deck_pages.addWidget(home)

    editor = QWidget()
    editor_layout = QVBoxLayout(editor)
    editor_layout.setContentsMargins(0, 0, 0, 0)
    editor_layout.setSpacing(12)
    style_row = QHBoxLayout()
    style_row.addWidget(w.presentation_toggle)
    style_row.addWidget(w.presentation_summary, 1)
    editor_layout.addLayout(style_row)
    editor_layout.addWidget(w.presentation_panel)
    editor_layout.addWidget(w.main_split, 1)
    sections = QHBoxLayout()
    for fr, en, group in (('Informations du vol', 'Flight details', w.flight_group),
                           ('Champs du message', 'Message fields', w.detail_group)):
        jump = QPushButton(tx(fr, en), objectName='sectionJump')
        jump.clicked.connect(lambda checked=False, target=group: w.form_scroll.verticalScrollBar().setValue(target.y()))
        sections.addWidget(jump)
    left_layout = w.main_split.widget(0).layout()
    left_layout.insertLayout(left_layout.indexOf(w.form_scroll), sections)
    w.deck_pages.addWidget(editor)
    shell.addWidget(content, 1)
    w.setCentralWidget(root)
    old.deleteLater()
    show_page(w, getattr(w, '_deck_page', 0))


def show_page(w, page):
    w._deck_page = page
    w.deck_pages.setCurrentIndex(page)
    w.deck_title.setText(tx('Votre vol. Votre horizon.', 'Your flight. Your horizon.') if page == 0 else tx('Prêt pour la fréquence.', 'Ready for the frequency.'))
    for i, button in enumerate(w.deck_nav):
        button.setChecked(i == page)


def refresh(w):
    if not hasattr(w, 'route_map'):
        return
    flight = w.store.state['flight']
    dep, arr = flight.get('departure_icao', ''), flight.get('arrival_icao', '')
    w.deck_route.setText(f'{dep or "— — — —"}   →   {arr or "— — — —"}')
    w.deck_metrics['aircraft'].setText(' · '.join(x for x in (flight.get('aircraft'), flight.get('callsign')) if x) or tx('À choisir', 'Choose aircraft'))
    w.deck_metrics['duration'].setText(str(flight.get('estimated_flight_time') or '—'))
    fuel = str(flight.get('fuel') or '')
    w.deck_metrics['fuel'].setText(f'{fuel} kg' if fuel else '—')
    if flight_db := w.store.state.get('finder_database'):
        w.route_map.set_database_path(flight_db)
    else:
        w.route_map.set_database_path(None)
    w.route_map.set_flight(flight)
    w.route_map.set_language(language())
    for kind, button in w.phase_buttons:
        button.setChecked(kind == w.message_type.currentText())
    problems = getattr(w, 'validation_problems', [])
    if problems:
        w.deck_readiness.setText(tx(f'{len(problems)} point(s) à compléter avant la copie.', f'{len(problems)} item(s) to complete before copying.'))
    else:
        w.deck_readiness.setText(tx('Message prêt. Relisez-le, puis copiez-le vers Discord.', 'Message ready. Review it, then copy it to Discord.'))


_styles = {}
def deck_style(dark):
    if dark in _styles:
        return _styles[dark]
    bg, surface, field, text, muted, border = (
        ('#10151D', '#171E29', '#111821', '#EDF4FA', '#A4B1C2', '#303C4B') if dark else
        ('#EFF3F4', '#FFFFFF', '#F5F8F9', '#142731', '#516772', '#CDDBDF')
    )
    accent, selected = ('#70E4CD', '#183E3C') if dark else ('#096A60', '#DEF3EE')
    style = f'''
    QWidget {{ font-family:"Segoe UI"; font-size:13px; color:{text}; }}
    QMainWindow, QDialog, QWidget#appRoot {{ background:{bg}; }}
    QFrame#navRail {{ background:#101B24; border:0; border-right:1px solid #29404A; }}
    QLabel#brandMark {{ color:#77E6D0; font-size:40px; font-weight:800; }}
    QLabel#brandCaption {{ color:#E7F2F4; font-size:10px; }}
    QLabel#navCaption {{ color:#93A8B6; font-size:10px; padding:4px 0; }}
    QPushButton#navItem {{ text-align:left; background:transparent; color:#C1CED8; border:1px solid transparent; border-radius:8px; padding:10px 8px; font-size:12px; }}
    QPushButton#navItem:hover {{ background:#1C303B; color:#FFFFFF; }}
    QPushButton#navItem:checked {{ background:#23433F; color:#8DEED8; border-color:#345C53; }}
    QPushButton#navItem:focus {{ border-color:#70E4CD; }}
    QLabel#deckTitle {{ font-size:27px; font-weight:600; color:{text}; }}
    QLabel#eyebrow {{ color:{muted}; font-size:10px; font-weight:600; }}
    QLabel#routeHeadline {{ font-family:"Consolas"; font-size:25px; font-weight:700; color:{text}; }}
    QFrame#mapCard {{ background:{field}; border:1px solid {border}; border-radius:14px; }}
    QFrame#metricCard, QFrame#dispatchStrip, QFrame#card, QFrame#settingsPanel {{ background:{surface}; border:1px solid {border}; border-radius:12px; }}
    QLabel#metricValue {{ color:{text}; font-size:17px; font-weight:600; }}
    QLabel#routeSummary {{ background:{field}; border-color:{border}; color:{text}; }}
    QGroupBox {{ background:{surface}; border-color:{border}; color:{muted}; }}
    QGroupBox::title {{ background:{surface}; color:{muted}; }}
    QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit {{ background:{field}; color:{text}; border:1px solid {border}; border-radius:7px; selection-background-color:#285D56; selection-color:#FFFFFF; }}
    QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus, QPlainTextEdit:focus {{ border-color:{accent}; }}
    QComboBox QLineEdit {{ border:none; background:transparent; }}
    QLineEdit[invalid="true"], QComboBox[invalid="true"] {{ border-color:#D87A78; }}
    QPushButton, QToolButton {{ background:{surface}; border:1px solid {border}; color:{text}; border-radius:7px; }}
    QPushButton:hover, QToolButton:hover {{ background:{selected}; border-color:{accent}; }}
    QPushButton#primary, QPushButton#copy {{ background:#70E4CD; border-color:#70E4CD; color:#082D28; font-weight:700; }}
    QPushButton#primary:hover, QPushButton#copy:hover {{ background:#99EFDE; border-color:#99EFDE; }}
    QPushButton#primary:disabled, QPushButton#copy:disabled {{ background:{surface}; color:{muted}; border-color:{border}; }}
    QPushButton#phaseStep {{ background:transparent; color:{muted}; font-size:12px; padding:8px 4px; border:0; border-top:2px solid {border}; border-radius:0; }}
    QPushButton#phaseStep:checked {{ color:{accent}; border-top-color:{accent}; }}
    QPushButton#phaseStep:hover {{ background:{selected}; }}
    QPushButton#sectionJump {{ background:transparent; color:{accent}; border:0; border-bottom:1px solid {border}; border-radius:0; font-size:11px; padding:6px 2px; }}
    QLabel#muted {{ color:{muted}; }}
    QPlainTextEdit#discordPreview {{ background:{field}; border-color:{border}; color:{text}; }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background:{border}; }}
    QScrollBar::handle:hover {{ background:{muted}; }}
    QToolButton#presentationToggle {{ color:{muted}; }}
    '''
    _styles[dark] = style
    return style
