"""Export only the public website, never repository data or build credentials."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = ('index.html', 'assets/site.css', 'assets/site.js',
    'assets/flightdeck-mark.svg', 'mobile/index.html', 'mobile/help-ui.js',
    'mobile/help-ui.css', 'mobile/help-content.js', 'mobile/help-adapter.js',
    'mobile/fuel.js', 'mobile/fuel-reference.js', 'mobile/workspace.css',
    'mobile/workspace.js')


def prepare(output=None):
    output = Path(output) if output else ROOT / 'build/site'
    if not output.resolve().is_relative_to((ROOT / 'build').resolve()):
        raise ValueError('Website output must remain inside the project build directory')
    # Use a new output so unrelated files can never become public or be deleted.
    output.mkdir(parents=True, exist_ok=False)
    for name in PUBLIC_FILES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    (output / '.nojekyll').write_text('', encoding='utf-8')
    return output


if __name__ == '__main__':
    print(prepare())
