# geo-photo-renamer

Rename photos and videos by location using embedded GPS metadata.

**Output format:**
```
canada--bc--vancouver--042.jpg
canada--bc--whistler--001.mp4
usa--wa--seattle--007.heic
```

Renamed files land in `~/Pictures/geo-renamed/`. Counters persist across runs so filenames never collide when you process folders in batches.

> **Note:** This tool was built and tested with [Google Photos Takeout](https://takeout.google.com) exports. It should work with any photos that have embedded GPS EXIF data, but folder structures, sidecar JSON formats, and metadata fields from other sources (iCloud exports, camera SD cards, etc.) may require adjustments.

---

## Install

**One-command install (Mac & Linux):**

```bash
curl -fsSL https://raw.githubusercontent.com/airrickdunfield/geo-photo-renamer/main/install.sh | bash
```

**Or directly with pip:**

```bash
pip install git+https://github.com/airrickdunfield/geo-photo-renamer.git
```

**Requirements:** Python 3.8+

**Optional — improves GPS extraction from video files:**
```bash
brew install exiftool                        # macOS
sudo apt install libimage-exiftool-perl      # Debian/Ubuntu
```

---

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/airrickdunfield/geo-photo-renamer/main/uninstall.sh | bash
```

Or manually:

```bash
pip uninstall geo-photo-renamer
rm -rf ~/.geo-photo-renamer   # optional: removes counters and log
```

Output photos in `~/Pictures/geo-renamed/` are never touched by the uninstaller.

---

## Usage

```bash
geo-rename ~/Downloads/vacation-photos
geo-rename ~/Downloads/trip1 ~/Downloads/trip2   # multiple folders

geo-rename --dry-run ~/Downloads/photos          # preview without moving anything
geo-rename --yes ~/Downloads/photos              # skip confirmation prompt
geo-rename --output ~/Desktop/out ~/Downloads/photos
geo-rename --data-dir /mnt/nas/geo-data ~/Downloads/photos
```

### Setting a default folder

If you always process the same folder, save it once so you can run `geo-rename` with no arguments:

```bash
geo-rename --set-default ~/Downloads/photos
# Saved. From now on, just run:
geo-rename
```

The default is stored in `~/.geo-photo-renamer/config.json`. You can change it any time by running `--set-default` again, or edit the file directly:

```json
{
  "default_folder": "/Users/you/Downloads/photos"
}
```

**All options:**

```
usage: geo-rename [-h] [--output DIR] [--data-dir DIR] [--set-default DIR]
                  [--dry-run] [--yes] [--version] [FOLDER ...]

positional arguments:
  FOLDER              Folder(s) containing photos/videos to rename
                      (uses saved default if omitted)

options:
  --set-default DIR   Save DIR as the default source folder and exit
  --output DIR        Where to place renamed files (default: ~/Pictures/geo-renamed)
  --data-dir DIR      Where to store rename_counts.json and rename_log.txt
                      (default: ~/.geo-photo-renamer)
  --dry-run           Show what would be renamed without moving any files
  --yes, -y           Skip the confirmation prompt
  --version           Show version
```

---

## How GPS is read

For each file, three sources are tried in order:

| Priority | Source | Works for |
|---|---|---|
| 1 | Sidecar `.json` file next to the photo | Images + Videos |
| 2 | EXIF data embedded in the file (via Pillow) | Images (JPG, PNG, HEIC, DNG, …) |
| 3 | `exiftool` (if installed) | Images + Videos |

Files with no GPS from any source are **skipped and left untouched**.

Sidecar `.json` files are the format produced by Google Photos Takeout, but any JSON file with a matching name and `geoData.latitude` / `geoData.longitude` fields will work.

---

## State files

By default, two files are stored in `~/.geo-photo-renamer/`:

| File | Purpose |
|---|---|
| `rename_counts.json` | Tracks the highest counter used per area + extension |
| `rename_log.txt` | Append-only log of every rename ever made |

Override with `--data-dir` if you want to store these elsewhere (e.g. a NAS shared between machines).

---

## How counters work

`rename_counts.json` tracks the highest counter used per area and file extension:

```json
{
  "canada--bc--vancouver": {
    ".jpg": 199,
    ".heic": 129,
    ".mp4": 10
  }
}
```

On the next run, `canada--bc--vancouver .jpg` files start at `200`, not `001`. To reset a counter, edit `rename_counts.json` directly and lower the number.

---

## Area aliases

Some locations may be returned by the geocoder under a slightly different name (e.g. `north-vancouver` instead of `vancouver`). These are controlled by `AREA_ALIASES` in `src/geo_renamer/cli.py`:

```python
AREA_ALIASES: dict[str, str] = {
    "north-vancouver": "vancouver",
}
```

Keys and values must be lowercase-hyphenated (matching the filename format).

---

## Troubleshooting

**`reverse_geocoder` not found**
```bash
pip install reverse_geocoder
```

**GPS shows wrong city** (e.g. `sooke` becomes `victoria`)
The offline geocoder snaps to the nearest named populated place. Add an alias to `AREA_ALIASES` or rename files manually.

**Video files skipped**
Install `exiftool` — videos rarely have GPS in their EXIF, and exiftool is the most reliable extractor for them.

**HEIC files without a sidecar JSON**
```bash
pip install pillow-heif
```

**`geo-rename` not found after install**
```bash
export PATH="$PATH:$(python3 -m site --user-base)/bin"
```
