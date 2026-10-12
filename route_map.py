"""Offline flight overview. Great-circle geometry is a reference, never a filed route."""
from functools import lru_cache
from collections import OrderedDict
import json
import math
from map_geometry import mercator_y, inverse_mercator, airport_coordinates, great_circle
from pathlib import Path
import sys

from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QTransform, QImage
from PySide6.QtWidgets import QWidget, QToolButton, QComboBox, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSizePolicy






@lru_cache(maxsize=1)
def country_paths():
    for root in resource_roots():
        source = root / 'assets/world_countries.json'
        if source.is_file():
            rows = json.loads(source.read_text(encoding='utf-8'))['countries']
            result = []
            for row in rows:
                path = QPainterPath()
                path.setFillRule(Qt.FillRule.OddEvenFill)
                for polygon in row['polygons']:
                    for ring in polygon:
                        if not ring:
                            continue
                        path.moveTo(ring[0][0], mercator_y(ring[0][1]))
                        for lon, lat in ring[1:]:
                            path.lineTo(lon, mercator_y(lat))
                        path.closeSubpath()
                result.append((row['code'], row['name'], path, path.boundingRect()))
            return result
    return []


def country_at(latitude, longitude):
    point = QPointF((longitude+180) % 360-180, mercator_y(latitude))
    for code, name, path, bounds in country_paths():
        if code and bounds.contains(point) and path.contains(point):
            return code, name
    return None


def resource_roots():
    roots = [Path(__file__).resolve().parent]
    if getattr(sys, "frozen", False):
        roots.insert(0, Path(sys.executable).resolve().parent)
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))
    return roots


def default_database():
    return next((root / "finder-data" / "aviation.sqlite" for root in resource_roots()
                 if (root / "finder-data" / "aviation.sqlite").is_file()), None)






@lru_cache(maxsize=1)
def land_path():
    path = QPainterPath()
    for root in resource_roots():
        try:
            rings = json.loads((root / "assets" / "world_land.json").read_text(encoding="utf-8"))
            for ring in rings:
                if not ring:
                    continue
                path.moveTo(ring[0][0], mercator_y(ring[0][1]))
                for lon, lat in ring[1:]:
                    path.lineTo(lon, mercator_y(lat))
                path.closeSubpath()
            break
        except (OSError, ValueError, TypeError):
            continue
    return path


class RouteMap(QWidget):
    """Offline vector map, with explicitly enabled asynchronous online layers."""
    countries_selected = Signal(str, str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("routeMap")
        self.setMinimumHeight(230)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("Route map")
        self._dark = True
        self._language = "en"
        self._database = default_database()
        self._codes = ("", "")
        self._airports = (None, None)
        self._route = []
        self._center = QPointF(0, -15)
        self._zoom = 1.0
        self._drag = None
        self._first_show = True
        self._press = None
        self._tiles = OrderedDict()
        self._background = None
        self._background_key = None
        self._tile_revision = 0
        self._wind = None
        self._wind_key = None
        self._online_note = ''
        self._country_codes = ['', '']
        self._country_mode = 0
        self.country_pickers = []
        from map_online import OnlineLayers, LEVELS
        self.online = OnlineLayers(self)
        self.online.tile_ready.connect(self._tile_ready)
        self.online.wind_ready.connect(self._wind_ready)
        self.online.status.connect(self._online_status)
        self.tools = QWidget(self)
        tools_layout = QHBoxLayout(self.tools)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        self.layer = QComboBox(self.tools)
        self.layer.addItem('Carte hors ligne', 'offline')
        self.layer.addItem('Satellite 2025 · Internet', 'satellite')
        self.layer.currentIndexChanged.connect(self._layer_changed)
        self.layer.setToolTip('EOxCloudless 2025 · https://maps.eox.at/ · Copernicus · CC BY-NC-SA 4.0 (non-commercial)')
        tools_layout.addWidget(self.layer)
        self.wind_level = QComboBox(self.tools)
        self.wind_level.addItem('Vents désactivés', None)
        for level, altitude in LEVELS:
            self.wind_level.addItem(f'{level} hPa · {altitude}', level)
        self.wind_level.currentIndexChanged.connect(self._wind_changed)
        self.wind_level.setToolTip('Open-Meteo · Internet · altitudes approximatives AMSL · météo réelle prévue, peut différer de RFS')
        tools_layout.addWidget(self.wind_level)
        self.refresh = QToolButton(self.tools)
        self.refresh.setText('↻')
        self.refresh.setToolTip('Actualiser les vents / Refresh winds')
        self.refresh.clicked.connect(lambda: self._request_wind(True))
        tools_layout.addWidget(self.refresh)
        self.wind_timer = QTimer(self)
        self.wind_timer.setSingleShot(True)
        self.wind_timer.timeout.connect(self._request_wind)
        self.auto_refresh = QTimer(self)
        self.auto_refresh.setInterval(900000)
        self.auto_refresh.timeout.connect(lambda: self._request_wind(True))
        self._buttons = []
        for label, action in (("+", lambda: self.zoom(1.3)), ("−", lambda: self.zoom(1 / 1.3)),
                              ("↔", self.fit_route)):
            button = QToolButton(self)
            button.setText(label)
            button.setFixedSize(28, 28)
            button.clicked.connect(action)
            self._buttons.append(button)
        self.set_dark(True)
        self.set_language("en")

    def set_database_path(self, path):
        path = Path(path) if path else default_database()
        if path != self._database:
            self._database = path
            codes = self._codes
            self._codes = ("", "")
            self.set_flight(dict(departure_icao=codes[0], arrival_icao=codes[1]))

    def set_flight(self, flight):
        codes = tuple(str(flight.get(key) or "").strip().upper()
                      for key in ("departure_icao", "arrival_icao"))
        if codes == self._codes:
            return
        self._codes = codes
        self._airports = tuple(airport_coordinates(str(self._database), code)
                               if self._database else None for code in codes)
        self._route = great_circle(*self._airports) if all(self._airports) else []
        self.fit_route()

    def set_language(self, language):
        self._language = language
        fr = language == "fr"
        self.layer.setItemText(0, 'Carte hors ligne' if fr else 'Offline map')
        self.layer.setItemText(1, 'Satellite 2025 · Internet')
        self.wind_level.setItemText(0, 'Vents désactivés' if fr else 'Winds off')
        if hasattr(self, 'click_mode'):
            for index, label in enumerate(('Clic : déplacer', 'Clic : départ', 'Clic : arrivée') if fr else ('Click: pan', 'Click: origin', 'Click: destination')):
                self.click_mode.setItemText(index, label)
            for index, picker in enumerate(self.country_pickers):
                picker.setItemText(0, ('Pays de départ' if index == 0 else 'Pays d’arrivée') if fr else ('Origin country' if index == 0 else 'Destination country'))
            self.find_countries_button.setText('Trouver ces vols' if fr else 'Find these flights')
        self.setAccessibleName("Carte du trajet" if fr else "Route map")
        for button, name in zip(self._buttons, ("Zoom +", "Zoom −", "Cadrer le trajet" if fr else "Fit route")):
            button.setToolTip(name)
            button.setAccessibleName(name)
        self.setToolTip(("Glisser : déplacer · Molette : zoom · Double-clic : cadrer" if fr else
                        "Drag to pan · Scroll to zoom · Double-click to fit") + "\nMade with Natural Earth · Public domain")
        self.update()

    def set_dark(self, dark):
        self._dark = bool(dark)
        if hasattr(self, 'attribution'):
            color = '#83A8B6' if dark else '#426674'
            self.attribution.setText(self._attribution_template.replace('<a ', f'<a style="color:{color}" '))
        for button in self._buttons:
            button.setStyleSheet("QToolButton {background:%s;color:%s;border:1px solid %s;border-radius:7px;font-size:17px;padding:0;min-height:0;min-width:0;}"
                                 "QToolButton:hover {border-color:#29BDAE;}" %
                                 (("#152C3B", "#E6F1F4", "#2D4756") if dark else
                                  ("#FFFFFF", "#143341", "#B7CAD2")))
        self.update()

    def create_country_controls(self, parent=None):
        from country_search import country_rows
        panel = QWidget(parent)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        layout = QHBoxLayout()
        outer.addLayout(layout)
        layout.setContentsMargins(8, 4, 8, 6)
        self.click_mode = QComboBox(panel)
        self.click_mode.addItems(['Clic : déplacer', 'Clic : départ', 'Clic : arrivée'])
        self.click_mode.currentIndexChanged.connect(lambda index: setattr(self, '_country_mode', index))
        layout.addWidget(self.click_mode)
        for index in range(2):
            picker = QComboBox(panel)
            picker.setEditable(True)
            picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            picker.addItem('Pays de départ' if index == 0 else 'Pays d’arrivée', '')
            for code, french, english in sorted(country_rows(), key=lambda row: row[1]):
                picker.addItem(f'{french} / {english} ({code})', code)
            picker.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            picker.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            picker.currentIndexChanged.connect(lambda _, i=index, p=picker: self.set_country(i, p.currentData() or ''))
            self.country_pickers.append(picker)
            layout.addWidget(picker, 1)
        find = QPushButton('Trouver ces vols', panel)
        find.clicked.connect(lambda: self.countries_selected.emit(*self._country_codes))
        layout.addWidget(find)
        self.find_countries_button = find
        attribution = QLabel('<a href="https://www.naturalearthdata.com/">Natural Earth</a> · '
                             '<a href="https://maps.eox.at/">EOX::Maps / Copernicus 2025</a> · '
                             '<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a> · '
                             '<a href="https://open-meteo.com/">Open-Meteo</a>', panel)
        attribution.setOpenExternalLinks(True)
        attribution.setWordWrap(True)
        self.attribution = attribution
        self._attribution_template = attribution.text()
        attribution.setText(self._attribution_template.replace('<a ', '<a style="color:#83A8B6" '))
        outer.addWidget(attribution)
        self.set_language(self._language)
        return panel

    def set_country(self, index, code):
        if index not in (0, 1):
            return
        self._country_codes[index] = code
        if len(self.country_pickers) == 2:
            picker = self.country_pickers[index]
            target = picker.findData(code)
            if target >= 0 and target != picker.currentIndex():
                picker.setCurrentIndex(target)
        self.update()

    def _layer_changed(self):
        self._online_note = ('© EOxCloudless 2025 · Copernicus · CC BY-NC-SA 4.0' if self.layer.currentData() == 'satellite' else '')
        self.update()

    def _online_status(self, message):
        self._online_note = ('Satellite indisponible · carte locale conservée' if self._language == 'fr' else message)
        self.update()

    def _tile_ready(self, key, data):
        image = QImage.fromData(data)
        if image.isNull() or image.width() != 256 or image.height() != 256:
            self._online_status('Satellite unavailable; offline map retained')
            return
        self._tiles[key] = image
        self._tiles.move_to_end(key)
        while len(self._tiles) > 128:
            self._tiles.popitem(last=False)
        self._tile_revision += 1
        self.update()

    def _draw_satellite(self, painter):
        scale = self._scale()
        z = max(0, min(15, int(math.log2(max(1, 360*scale/256)))))
        n = 2**z
        unit = 360/n
        left = self._center.x()-self.width()/2/scale
        right = self._center.x()+self.width()/2/scale
        top = self._center.y()-self.height()/2/scale
        bottom = self._center.y()+self.height()/2/scale
        for x in range(math.floor((left+180)/unit), math.floor((right+180)/unit)+1):
            for y in range(max(0, math.floor((top+180)/unit)), min(n-1, math.floor((bottom+180)/unit))+1):
                key = (z, x % n, y)
                rect = QRectF(self.width()/2+(-180+x*unit-self._center.x())*scale,
                              self.height()/2+(-180+y*unit-self._center.y())*scale, unit*scale+0.2, unit*scale+0.2)
                image = self._tiles.get(key)
                if image is not None:
                    self._tiles.move_to_end(key)
                    painter.drawImage(rect, image)
                    continue
                # Reuse already loaded coarser imagery while detailed tiles load.
                for parent_z in range(z-1, -1, -1):
                    factor = 2**(z-parent_z)
                    parent_key = (parent_z, (x % n)//factor, y//factor)
                    if parent_key in self._tiles:
                        crop = QRectF((x % factor)*256/factor, (y % factor)*256/factor, 256/factor, 256/factor)
                        painter.drawImage(rect, self._tiles[parent_key], crop)
                        break
                # Request a coarse base first, so panning/zooming can retain
                # satellite imagery while more detailed images arrive.
                for parent_z in dict.fromkeys((0, max(0, z-2), max(0, z-1))):
                    factor = 2**(z-parent_z)
                    parent_key = (parent_z, (x % n)//factor, y//factor)
                    if parent_key not in self._tiles:
                        self.online.request_tile(parent_key)
                self.online.request_tile(key)

    def _wind_changed(self):
        self._wind = None
        self._wind_key = None
        if self.wind_level.currentData():
            self.auto_refresh.start()
            self._schedule_wind()
        else:
            self.wind_timer.stop()
            self.auto_refresh.stop()
        self.update()

    def _schedule_wind(self):
        if self.wind_level.currentData():
            self.wind_timer.start(600)

    def _wind_points(self):
        scale = self._scale()
        points = []
        for row in range(3):
            for column in range(4):
                lon = self._center.x()+((column+0.5)/4-0.5)*self.width()/scale
                y = self._center.y()+((row+0.5)/3-0.5)*max(40, self.height()-90)/scale
                points.append((round(max(-85, min(85, inverse_mercator(y))), 3), round((lon+180)%360-180, 3)))
        for lat, lon in self._route[::24]:
            points.append((round(max(-85, min(85, lat)), 3), round((lon+180)%360-180, 3)))
        return list(dict.fromkeys(points))

    def _request_wind(self, refresh=False):
        level = self.wind_level.currentData()
        if not level:
            return
        points = self._wind_points()
        # Set key before request: a cache hit can emit synchronously.
        self._wind_key = (level, tuple(points))
        self.online.request_wind(points, level, refresh)

    def _wind_ready(self, key, value, error):
        if key != self._wind_key or not self.wind_level.currentData():
            return
        if value:
            self._wind = value
            self._online_note = ''
        else:
            self._online_note = 'Vents indisponibles · réessayer / Winds unavailable · retry'
        self.update()

    def _draw_wind(self, painter):
        if not self._wind or not self.wind_level.currentData():
            return
        from map_online import wind_components
        painter.setPen(QPen(QColor('#FEBE59'), 2))
        painter.setFont(QFont('Segoe UI', 8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for sample in self._wind['samples']:
            lon = sample['longitude'] + 360*round((self._center.x()-sample['longitude'])/360)
            point = self._point(sample['latitude'], lon)
            if not QRectF(0, 42, self.width(), self.height()-95).contains(point):
                continue
            east, north = wind_components(sample['speed'], sample['direction'])
            magnitude = max(1, math.hypot(east, north))
            delta = QPointF(east/magnitude, -north/magnitude)*min(25, 9+sample['speed']/6)
            start, end = point-delta/2, point+delta/2
            painter.drawLine(start, end)
            normal = QPointF(-delta.y(), delta.x())/max(1, delta.manhattanLength())*6
            rear = end-delta/max(1, delta.manhattanLength())*9
            painter.drawLine(end, rear+normal)
            painter.drawLine(end, rear-normal)
            painter.drawText(end+QPointF(3, -4), f"{sample['speed']:.0f} kt")

    def _wind_note(self):
        if not self._wind:
            return self._online_note or 'Chargement des vents… / Loading winds…'
        if self._online_note:
            return self._online_note+' · dernier cache '+self._wind['samples'][0]['time'][:16]+' UTC'
        samples = self._wind.get('samples') or []
        if not samples:
            return self._online_note or ('Chargement des vents…' if self._language == 'fr' else 'Loading winds…')
        height = sum(row['height_m'] for row in samples)/len(samples)
        fr = self._language == 'fr'
        note = f"Open-Meteo · {height:.0f} m AMSL"
        if self._route and len(self._route) >= 2:
            from map_online import bearing, tailwind
            components = []
            for index in range(0, len(self._route)-1, 24):
                lat, lon = self._route[index]
                sample = min(samples, key=lambda s: abs(s['latitude']-lat)+abs((s['longitude']-lon+180)%360-180)*math.cos(math.radians(lat)))
                components.append(tailwind(sample['speed'], sample['direction'], bearing(self._route[index], self._route[index+1])))
            average = sum(components)/len(components) if components else 0
            direction = ('arrière' if average >= 0 else 'face') if fr else ('tailwind' if average >= 0 else 'headwind')
            note += f" · {direction} ≈ {abs(average):.0f} kt"
        note += f" · {samples[0]['time'][:16]} UTC · " + ('prévision, peut différer de RFS' if fr else 'forecast, may differ from RFS')
        return note

    def _scale(self):
        return max(0.1, min(self.width() / 360, max(1, self.height() - 100) / 180)) * self._zoom

    def _point(self, lat, lon):
        scale = self._scale()
        return QPointF(self.width() / 2 + (lon - self._center.x()) * scale,
                       self.height() / 2 + (mercator_y(lat) - self._center.y()) * scale)

    def fit_route(self):
        points = self._route or [point for point in self._airports if point]
        if points:
            lats, lons = zip(*points)
            ys = [mercator_y(lat) for lat in lats]
            self._center = QPointF((max(lons) + min(lons)) / 2, (max(ys) + min(ys)) / 2)
            span_x, span_y = max(4, max(lons) - min(lons)), max(4, max(ys) - min(ys))
            self._zoom = 1
            self._zoom = max(1, min(128, min(max(40, self.width() - 130) / span_x,
                                           max(40, self.height() - 100) / span_y) / self._scale()))
        else:
            self._center, self._zoom = QPointF(0, -15), 1.0
        self.update()
        self._schedule_wind()

    def zoom(self, factor):
        self._zoom = max(1.0, min(32768.0, self._zoom * factor))
        self.update()
        self._schedule_wind()

    def resizeEvent(self, event):
        self.tools.setGeometry(12, 10, max(100, self.width()-68), 32)
        for index, button in enumerate(self._buttons):
            button.move(self.width() - 40, 12 + index * 33)
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.fit_route()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = self._dark
        ocean, land, coast, grid, text, muted, accent = (
            ("#0B1D29", "#193443", "#2B4A59", "#17313F", "#E5F4F4", "#83A8B6", "#50E0CA") if dark else
            ("#EAF3F6", "#D2E2E7", "#AEC5CE", "#DCE8ED", "#173A48", "#557582", "#007E76"))
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 12, 12)
        painter.setClipPath(clip)
        key = (self.width(), self.height(), self._center.x(), self._center.y(), self._zoom,
               dark, self.layer.currentData(), self._tile_revision, tuple(self._country_codes))
        if key != self._background_key:
            self._background = QImage(self.size(), QImage.Format.Format_RGB32)
            base = QPainter(self._background)
            base.setRenderHint(QPainter.RenderHint.Antialiasing)
            base.fillRect(self.rect(), QColor(ocean))
            base.setPen(QPen(QColor(grid), 1))
            for lon in range(-720, 721, 30):
                base.drawLine(self._point(-85, lon), self._point(85, lon))
            for lat in range(-60, 61, 30):
                base.drawLine(self._point(lat, -900), self._point(lat, 900))
            scale = self._scale()
            transforms = [QTransform(scale, 0, 0, scale, self.width()/2+(shift-self._center.x())*scale,
                                     self.height()/2-self._center.y()*scale)
                          for shift in (-720, -360, 0, 360, 720)]
            base.setPen(QPen(QColor(coast), 0.7))
            base.setBrush(QColor(land))
            if self.layer.currentData() != 'satellite':
                for transform in transforms:
                    base.drawPath(transform.map(land_path()))
            if self.layer.currentData() == 'satellite':
                self._draw_satellite(base)
            base.setBrush(Qt.BrushStyle.NoBrush)
            viewport = QRectF(self.rect())
            for code, name, path, bounds in country_paths():
                for transform in transforms:
                    if transform.mapRect(bounds).intersects(viewport):
                        chosen = code in self._country_codes
                        base.setPen(QPen(QColor(accent if chosen else ('#EBECDA' if self.layer.currentData() == 'satellite' else coast)), 1.6 if chosen else 0.8))
                        base.drawPath(transform.map(path))
            base.end()
            self._background_key = key
        painter.drawImage(0, 0, self._background)
        if self._route:
            route = QPainterPath()
            route.moveTo(self._point(*self._route[0]))
            for point in self._route[1:]:
                route.lineTo(self._point(*point))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            glow = QColor(accent)
            glow.setAlpha(35)
            painter.setPen(QPen(glow, 8))
            painter.drawPath(route)
            painter.setPen(QPen(QColor(accent), 2))
            painter.drawPath(route)
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        for index, airport in enumerate(self._airports):
            if not airport:
                continue
            point = self._point(*(self._route[0 if index == 0 else -1] if self._route else airport))
            painter.setPen(QPen(QColor(accent), 2))
            painter.setBrush(QColor(ocean))
            painter.drawEllipse(point, 5, 5)
            painter.setBrush(QColor(accent))
            painter.drawEllipse(point, 1.5, 1.5)
            label_width = painter.fontMetrics().horizontalAdvance(self._codes[index]) + 16
            x = max(8, min(self.width() - label_width - 8, point.x() + 10))
            y = max(44, min(self.height() - 80, point.y() - 27 if index == 0 else point.y() + 8))
            label = QRectF(x, y, label_width, 24)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ocean))
            painter.drawRoundedRect(label, 5, 5)
            painter.setPen(QColor(text))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, self._codes[index])
        fr = self._language == "fr"
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.setPen(QColor(muted))
        self._draw_wind(painter)
        painter.fillRect(QRectF(0, self.height() - 51, self.width(), 51), QColor(ocean))
        painter.setFont(QFont("Segoe UI", 8))
        note = ("Arc direct indicatif · Pas le plan de vol réel" if fr else "Great-circle reference · Not the actual flight plan")
        if not self._route:
            note = ("Choisissez deux aéroports pour tracer le trajet" if fr else "Choose two airports to display the route")
            if any(code and not airport for code, airport in zip(self._codes, self._airports)):
                note = ("Coordonnées d’aéroport manquantes dans la base locale" if fr else "Airport coordinates unavailable in the local database")
        painter.drawText(QRectF(14, self.height() - 49, self.width() - 28, 24),
                         Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(note, Qt.TextElideMode.ElideRight, self.width() - 28))
        online_note = self._wind_note() if self.wind_level.currentData() else self._online_note
        if not online_note:
            online_note = 'Natural Earth · frontières indicatives' if fr else 'Natural Earth · indicative borders'
        painter.drawText(QRectF(14, self.height()-26, self.width()-28, 22),
                         painter.fontMetrics().elidedText(online_note, Qt.TextElideMode.ElideRight, self.width()-28))
        painter.end()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            position = event.position()
            before = (position-QPointF(self.width()/2, self.height()/2))/self._scale()+self._center
            self.zoom(1.2 if delta > 0 else 1 / 1.2)
            self._center = before-(position-QPointF(self.width()/2, self.height()/2))/self._scale()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.position()
            self._press = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            delta = event.position() - self._drag
            self._center -= delta / self._scale()
            self._center.setX(max(-540, min(540, self._center.x())))
            self._center.setY(max(-180, min(180, self._center.y())))
            self._drag = event.position()
            self.update()
            self._schedule_wind()
        elif self._wind and self.wind_level.currentData() and self._wind.get('samples'):
            position = event.position()
            sample = min(self._wind['samples'], key=lambda s: (self._point(s['latitude'], s['longitude'])-position).manhattanLength())
            self.setToolTip(self._wind_note()+f"\n{sample['speed']:.0f} kt depuis {sample['direction']:.0f}° · {sample['height_m']:.0f} m AMSL")

    def mouseReleaseEvent(self, event):
        if self._press is not None and (event.position()-self._press).manhattanLength() < 5 and self._country_mode:
            point = (event.position()-QPointF(self.width()/2, self.height()/2))/self._scale()+self._center
            country = country_at(inverse_mercator(point.y()), point.x())
            if country:
                self.set_country(self._country_mode-1, country[0])
                self.setToolTip(country[1])
        self._drag = None
        self._press = None
        self.unsetCursor()

    def mouseDoubleClickEvent(self, event):
        self.fit_route()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom(1.3)
        elif key == Qt.Key.Key_Minus:
            self.zoom(1 / 1.3)
        elif key in (Qt.Key.Key_0, Qt.Key.Key_Home):
            self.fit_route()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            dx = (key == Qt.Key.Key_Right) - (key == Qt.Key.Key_Left)
            dy = (key == Qt.Key.Key_Down) - (key == Qt.Key.Key_Up)
            self._center += QPointF(dx * 30 / self._scale(), dy * 30 / self._scale())
            self.update()
            self._schedule_wind()
        else:
            super().keyPressEvent(event)
