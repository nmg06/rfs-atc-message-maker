"""Application-wide wheel routing; keyboard editing and open popups stay native."""
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QAbstractSpinBox, QAbstractScrollArea, QAbstractItemView


class WheelGuard(QObject):
    def eventFilter(self, watched, event):
        event_type = event.type()
        if event_type == QEvent.Type.Show and isinstance(watched, QAbstractScrollArea):
            smooth_scroll(watched)
        if event_type != QEvent.Type.Wheel:
            return False
        control = watched
        while control is not None and not isinstance(control, (QComboBox, QAbstractSpinBox)):
            control = control.parentWidget() if hasattr(control, 'parentWidget') else None
        if control is None:
            return False
        if isinstance(control, QComboBox):
            view = control.view()
            if view and view.isVisible():
                return False
        # Forward or scroll the enclosing scroll area.
        parent = control.parentWidget() if hasattr(control, 'parentWidget') else None
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                pixels = event.pixelDelta()
                if not pixels.isNull():
                    bar = parent.verticalScrollBar() if pixels.y() else parent.horizontalScrollBar()
                    bar.setValue(bar.value() - (pixels.y() or pixels.x()))
                    event.accept()
                    return True
                QApplication.sendEvent(parent.viewport(), event)
                return True
            parent = parent.parentWidget() if hasattr(parent, 'parentWidget') else None
        event.ignore()
        return True


def install_wheel_guard():
    app = QApplication.instance()
    if not hasattr(app, '_rfs_wheel_guard'):
        app._rfs_wheel_guard = WheelGuard(app)
        app.installEventFilter(app._rfs_wheel_guard)


def smooth_scroll(widget):
    if isinstance(widget, QAbstractItemView):
        widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    widget.verticalScrollBar().setSingleStep(18)
