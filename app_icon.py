from functools import lru_cache
"""Icône vectorielle dessinée localement : avion et radar."""
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap


def icon_image(size=256):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 256, size / 256)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#111c32"))
    painter.drawRoundedRect(QRectF(5, 5, 246, 246), 52, 52)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#244261"), 4))
    for radius in (52, 89):
        painter.drawEllipse(QPointF(128, 128), radius, radius)
    painter.setPen(QPen(QColor("#2dd4bf"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawArc(QRectF(39, 39, 178, 178), 15 * 16, 65 * 16)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#f3f7ff"))
    plane = QPainterPath()
    plane.moveTo(128, 47)
    for x, y in ((141, 99), (201, 143), (201, 160), (141, 139), (138, 182),
                 (157, 197), (157, 210), (128, 199), (99, 210), (99, 197),
                 (118, 182), (115, 139), (55, 160), (55, 143), (115, 99)):
        plane.lineTo(x, y)
    plane.closeSubpath()
    painter.drawPath(plane)
    painter.end()
    return image


def make_icon():
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(icon_image(size)))
    return icon


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    assets = Path(__file__).parent / "assets"
    assets.mkdir(exist_ok=True)
    assert icon_image().save(str(assets / "app.png"))
    assert icon_image().save(str(assets / "app.ico")), "Écriture ICO indisponible"
