from pathlib import Path


def wine_path_to_logos_subpath(wine_path):
    """Return subpath, beginning one level beneath 'Logos' folder.
    """
    # Escape all backslashes.
    p_esc = wine_path.encode('unicode-escape').decode()
    # Remove root drive letter.
    p_noroot = '/'.join(p_esc.split('\\\\')[1:])
    # Convert to Path obj.
    p = Path(p_noroot)
    idx = p.parts.index('Logos')
    rel_p = p.parts[idx+1:]  # get everything after 'Logos'
    return Path('/'.join(rel_p))


def b_to_mb(size_bytes):
    return round(size_bytes / 1_000_000, 1)
