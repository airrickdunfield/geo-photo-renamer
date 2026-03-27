# geo-photo-renamer — Instructions for Claude

This is an installable CLI tool that renames photos and videos by location using GPS metadata.

**Install command:**
```bash
curl -fsSL https://raw.githubusercontent.com/airrickdunfield/geo-photo-renamer/main/install.sh | bash
```

**Usage:**
```bash
geo-rename ~/path/to/photos
geo-rename --dry-run ~/path/to/photos
geo-rename --yes ~/path/to/photos
geo-rename                              # uses saved default folder
geo-rename --set-default ~/path/to/photos  # save default folder and exit
geo-rename --output ~/dest --data-dir ~/.mydata ~/path/to/photos
```

**Update commands:**
```bash
geo-update          # update to latest version
geo-rename-update   # alias for geo-update
```

---

## File layout

```
geo-photo-renamer/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── install.sh
└── src/
    └── geo_renamer/
        ├── __init__.py   ← version string
        └── cli.py        ← all logic and CLI entry point
```

---

## Output

- **Renamed files** → `~/Pictures/geo-renamed/` (default, overridable with `--output`)
- **Counts** → `~/.geo-photo-renamer/rename_counts.json`
- **Log** → `~/.geo-photo-renamer/rename_log.txt`
- **Config** → `~/.geo-photo-renamer/config.json` (stores saved default folder)

The `--data-dir` flag overrides the `~/.geo-photo-renamer/` directory for counts and log.

---

## Naming convention

```
COUNTRY--STATE_PROVINCE--AREA--NNN.ext

Examples:
  canada--bc--vancouver--042.jpg
  usa--wa--seattle--007.mp4
```

Counters are **per area + per extension** and persist across runs via `~/.geo-photo-renamer/rename_counts.json`.

If a destination file already exists, a `-dupNN` suffix is appended (e.g. `canada--bc--vancouver--042-dup01.jpg`).

---

## GPS source priority

For each file, GPS is extracted by trying these sources in order (first hit wins):

1. **JSON sidecar** — `<filename>.json` next to the photo (Google Photos Takeout format)
2. **EXIF data** — embedded in the image via Pillow (images only; requires `pillow-heif` for HEIC)
3. **exiftool** — best for video files; also handles iPhone `GPSCoordinates` strings

---

## Location overrides

Two mechanisms for controlling how coordinates map to names:

### Area aliases (`AREA_ALIASES`)

Maps geocoder output slugs to preferred names. Edit near the top of `src/geo_renamer/cli.py`.

```python
AREA_ALIASES: dict[str, str] = {
    "north-vancouver": "vancouver",
}
```

### Coordinate overrides (`COORD_OVERRIDES`)

Bounding-box overrides checked **before** the geocoder. Useful for islands or areas where the geocoder snaps to the wrong place. Listed most-specific first (first match wins). Edit near the top of `src/geo_renamer/cli.py`.

```python
COORD_OVERRIDES: list[tuple] = [
    # (lat_min, lat_max, lon_min, lon_max, country, state, area)
    (48.82, 48.87, -123.32, -123.22, "canada", "bc", "mayne-island"),
]
```

---

## Manually editing rename_counts.json

```json
{
  "canada--bc--vancouver": {
    ".jpg": 199,
    ".heic": 129,
    ".mp4": 10
  }
}
```

The next run starts each counter at `stored value + 1`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `reverse_geocoder` not found | `pip install reverse_geocoder` |
| GPS shows wrong city | Geocoder snaps to nearest populated place; add an entry to `AREA_ALIASES` or `COORD_OVERRIDES` |
| Video files skipped | Install exiftool: `brew install exiftool` |
| HEIC GPS not read | `pip install pillow-heif` (JSON sidecars still work without it) |
| `geo-rename` not on PATH | `export PATH="$PATH:$(python3 -m site --user-base)/bin"` |
| `geo-update` fails | Requires pipx; re-run the install script |
