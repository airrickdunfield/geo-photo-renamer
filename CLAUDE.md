# geo-photo-renamer — Instructions for Claude

This is an installable CLI tool that renames photos and videos by location using GPS metadata.

**Install command:**
```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/geo-photo-renamer/main/install.sh | bash
```

**Usage:**
```bash
geo-rename ~/path/to/photos
geo-rename --dry-run ~/path/to/photos
geo-rename --yes ~/path/to/photos
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

---

## Naming convention

```
COUNTRY--STATE_PROVINCE--AREA--NNN.ext

Examples:
  canada--bc--vancouver--042.jpg
  usa--wa--seattle--007.mp4
```

Counters are **per area + per extension** and persist across runs via `~/.geo-photo-renamer/rename_counts.json`.

---

## Area aliases

To merge geocoder variations (e.g. `north-vancouver` → `vancouver`), edit `AREA_ALIASES` near the top of `src/geo_renamer/cli.py`.

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
| GPS shows wrong city | Geocoder snaps to nearest populated place; add an entry to `AREA_ALIASES` |
| Video files skipped | Install exiftool: `brew install exiftool` |
| `geo-rename` not on PATH | `export PATH="$PATH:$(python3 -m site --user-base)/bin"` |
