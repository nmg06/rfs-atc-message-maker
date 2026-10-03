"""Small, shared colour catalogue: ten identities, each with dark/light surfaces."""
THEMES = (
    ('avionique', 'Avionique', '#70e4cd', '#096a60', '#0b1220', '#171e29'),
    ('ocean', 'Océan', '#7bc9ff', '#075d9c', '#0d1929', '#14263b'),
    ('aurora', 'Aurore', '#bdabff', '#6340ae', '#191627', '#27223a'),
    ('sunset', 'Crépuscule', '#ffb393', '#a74220', '#25171c', '#35242a'),
    ('forest', 'Forêt', '#a4e5a0', '#286525', '#142019', '#203025'),
    ('amber', 'Ambre', '#f4ce7e', '#795409', '#211e16', '#302b20'),
    ('rose', 'Rose', '#ffa8ce', '#9e2960', '#251822', '#352431'),
    ('glacier', 'Glacier', '#8de5ef', '#076777', '#112027', '#1b3039'),
    ('lavender', 'Lavande', '#d4bdff', '#7446ad', '#201a2b', '#2e273d'),
    ('graphite', 'Graphite', '#c3d3e7', '#3f576d', '#171c23', '#252d38'),
)


def theme_colors(identity='avionique', dark=True):
    row = next((r for r in THEMES if r[0] == identity), THEMES[0])
    return dict(id=row[0], name=row[1], accent=row[2] if dark else row[3],
        bg=row[4] if dark else '#f1f5f9' if row[0]=='avionique' else '#f3f5f8', card=row[5] if dark else '#ffffff',
        field=row[4] if dark else '#f5f7fa', text='#edf4fa' if dark else '#142731',
        muted='#b0bdd0' if dark else '#516172', border='#495768' if dark else '#cbd5df',
        accent_text='#10151d' if dark else '#ffffff')
