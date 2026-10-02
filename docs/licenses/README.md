# Third-party notices

This local app uses unmodified Python 3.13.3, PySide6/Shiboken/Qt 6.11.2,
tzdata 2026.4 and the PyInstaller bootloader 6.22.3. Runtime libraries remain
separate, replaceable files in `_internal/`; no restriction on debugging modified
LGPL components is imposed by this project.

- Python licence: `Python/LICENSE.txt`, https://www.python.org/downloads/source/
- PySide6/Qt: LGPLv3/GPL alternatives described by the publisher at
  https://pypi.org/project/PySide6/6.11.2/ . Licence texts are in `Qt/`.
  Source: https://code.qt.io/pyside/pyside-setup and
  https://code.qt.io/qt/qtbase (version 6.11.2).
  Qt third-party notices: https://doc.qt.io/qt-6/licenses-used-in-qt.html and
  https://doc.qt.io/qtforpython-6/licenses.html .
- PyInstaller licence/bootloader exception: `PyInstaller/COPYING.txt`.
- Timezone data/licences: `tzdata/`, https://pypi.org/project/tzdata/2026.4/ .
- Aviation database: separate ODbL notice and source manifest in `finder-data/`.

No application-code licence is selected on behalf of the project owner. Before
a public GitHub release, select an application licence and review the relevant
third-party redistribution/source-provision obligations. The local checks and
these notices are not a legal compliance certification.
