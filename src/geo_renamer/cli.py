#!/usr/bin/env python3
"""
geo-rename — Rename photos and videos using GPS metadata.

Output format:  COUNTRY--STATE_PROVINCE--AREA--NNN.ext
  e.g.          canada--bc--vancouver--042.jpg
                usa--wa--seattle--001.mp4

GPS sources (tried in order for each file):
  1. Sidecar .json file next to the photo (e.g. from Google Photos Takeout)
  2. EXIF data embedded in the image (via Pillow)
  3. exiftool (if installed — best for video files)

State (counters + log) is stored in ~/.geo-photo-renamer/ by default.
Renamed files are placed in ~/Pictures/geo-renamed/ by default.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ── Optional dependency: pillow-heif ──────────────────────────────────────────
try:
    import PIL.Image as _PILImage  # noqa: F401 — checked below

    _pil_ok = True
except ImportError:
    _pil_ok = False

_heic_ok = False
if _pil_ok:
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
        _heic_ok = True
    except ImportError:
        pass

EXIFTOOL = shutil.which("exiftool")

# ── File type filters ──────────────────────────────────────────────────────────
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif",
    ".webp", ".tiff", ".tif", ".bmp", ".dng", ".raw",
}
VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".3gp", ".m4v", ".mkv",
    ".wmv", ".flv", ".webm", ".mts", ".m2ts",
}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# ── Location lookup tables ─────────────────────────────────────────────────────
PROVINCE_ABBR = {
    "British Columbia": "bc", "Alberta": "ab", "Saskatchewan": "sk",
    "Manitoba": "mb", "Ontario": "on", "Quebec": "qc",
    "New Brunswick": "nb", "Nova Scotia": "ns",
    "Prince Edward Island": "pei", "Newfoundland and Labrador": "nl",
    "Newfoundland": "nl", "Northwest Territories": "nt",
    "Yukon": "yt", "Nunavut": "nu",
}
STATE_ABBR = {
    "Alabama": "al", "Alaska": "ak", "Arizona": "az", "Arkansas": "ar",
    "California": "ca", "Colorado": "co", "Connecticut": "ct", "Delaware": "de",
    "Florida": "fl", "Georgia": "ga", "Hawaii": "hi", "Idaho": "id",
    "Illinois": "il", "Indiana": "in", "Iowa": "ia", "Kansas": "ks",
    "Kentucky": "ky", "Louisiana": "la", "Maine": "me", "Maryland": "md",
    "Massachusetts": "ma", "Michigan": "mi", "Minnesota": "mn", "Mississippi": "ms",
    "Missouri": "mo", "Montana": "mt", "Nebraska": "ne", "Nevada": "nv",
    "New Hampshire": "nh", "New Jersey": "nj", "New Mexico": "nm", "New York": "ny",
    "North Carolina": "nc", "North Dakota": "nd", "Ohio": "oh", "Oklahoma": "ok",
    "Oregon": "or", "Pennsylvania": "pa", "Rhode Island": "ri",
    "South Carolina": "sc", "South Dakota": "sd", "Tennessee": "tn",
    "Texas": "tx", "Utah": "ut", "Vermont": "vt", "Virginia": "va",
    "Washington": "wa", "West Virginia": "wv", "Wisconsin": "wi",
    "Wyoming": "wy", "District of Columbia": "dc",
}
COUNTRY_NAMES = {
    "CA": "canada", "US": "usa", "GB": "uk", "AU": "australia",
    "MX": "mexico", "FR": "france", "DE": "germany", "JP": "japan",
    "IT": "italy", "ES": "spain", "PT": "portugal", "NZ": "new-zealand",
    "NL": "netherlands", "BE": "belgium", "CH": "switzerland",
    "AT": "austria", "SE": "sweden", "NO": "norway", "DK": "denmark",
    "TH": "thailand", "PH": "philippines", "ID": "indonesia",
    "SG": "singapore", "MY": "malaysia", "VN": "vietnam",
}

# ── Area aliases ───────────────────────────────────────────────────────────────
# Maps geocoded area slugs to preferred canonical names.
# Keys and values must be lowercase-hyphenated.
AREA_ALIASES: dict[str, str] = {
    "north-vancouver": "vancouver",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"['\u2019]", "", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def progress_bar(current: int, total: int, label: str = "", width: int = 40) -> None:
    pct = current / total if total else 1
    done = int(pct * width)
    bar = "#" * done + "-" * (width - done)
    sys.stdout.write(f"\r  [{bar}] {current}/{total}  {label:<30}")
    sys.stdout.flush()
    if current == total:
        print()


# ── GPS extraction ─────────────────────────────────────────────────────────────

def _dms_to_decimal(dms, ref: str) -> float:
    def to_float(v):
        if hasattr(v, "numerator"):
            return v.numerator / v.denominator
        if isinstance(v, tuple) and len(v) == 2:
            return v[0] / v[1]
        return float(v)

    d, m, s = (to_float(x) for x in dms)
    dec = d + m / 60.0 + s / 3600.0
    return -dec if ref in ("S", "W") else dec


def gps_from_json_sidecar(filepath: Path):
    sidecar = filepath.parent / (filepath.name + ".json")
    if not sidecar.exists():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        for key in ("geoData", "geoDataExif"):
            geo = data.get(key, {})
            lat, lon = geo.get("latitude", 0.0), geo.get("longitude", 0.0)
            if lat != 0.0 or lon != 0.0:
                return (lat, lon)
    except Exception:
        pass
    return None


def gps_from_exif(filepath: Path):
    if not _pil_ok:
        return None
    if filepath.suffix.lower() in VIDEO_EXTS:
        return None
    if filepath.suffix.lower() in (".heic", ".heif") and not _heic_ok:
        return None
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS

        img = Image.open(filepath)

        # Try the public getexif() API first — required for HEIC via pillow-heif
        gps_info = {}
        try:
            exif_obj = img.getexif()
            gps_ifd = exif_obj.get_ifd(0x8825)  # 0x8825 = GPSInfo tag
            if gps_ifd:
                gps_info = {GPSTAGS.get(t, t): v for t, v in gps_ifd.items()}
        except Exception:
            pass

        # Fall back to _getexif() for JPEG compatibility
        if not gps_info:
            exif_raw = img._getexif()
            if exif_raw:
                for tag, val in exif_raw.items():
                    if TAGS.get(tag) == "GPSInfo":
                        gps_info = {GPSTAGS.get(t, t): v for t, v in val.items()}
                        break

        if not gps_info:
            return None
        lat = gps_info.get("GPSLatitude")
        lref = gps_info.get("GPSLatitudeRef", "N")
        lon = gps_info.get("GPSLongitude")
        lnref = gps_info.get("GPSLongitudeRef", "E")
        if not (lat and lon):
            return None
        return (_dms_to_decimal(lat, lref), _dms_to_decimal(lon, lnref))
    except Exception:
        return None


def gps_from_exiftool(filepath: Path):
    if not EXIFTOOL:
        return None
    try:
        result = subprocess.run(
            [EXIFTOOL, "-j", "-n",
             "-GPSLatitude", "-GPSLongitude", "-GPSCoordinates",
             str(filepath)],
            capture_output=True, text=True, timeout=10,
        )
        if not result.stdout.strip():
            return None
        data = json.loads(result.stdout)
        if not data:
            return None
        entry = data[0]

        lat = entry.get("GPSLatitude")
        lon = entry.get("GPSLongitude")
        if lat is not None and lon is not None and (float(lat) != 0.0 or float(lon) != 0.0):
            return (float(lat), float(lon))

        # Fallback: iPhone videos store GPS as a combined GPSCoordinates string
        # (ISO 6709, e.g. "+49.1234+012.5678+100.000/" or "49.1234, 12.5678")
        coords_str = entry.get("GPSCoordinates", "")
        if coords_str:
            parts = re.split(r"[,\s]+", coords_str.strip().rstrip("/"))
            if len(parts) >= 2:
                lat2, lon2 = float(parts[0]), float(parts[1])
                if lat2 != 0.0 or lon2 != 0.0:
                    return (lat2, lon2)
    except Exception:
        pass
    return None


def get_gps(filepath: Path):
    return (
        gps_from_json_sidecar(filepath)
        or gps_from_exif(filepath)
        or gps_from_exiftool(filepath)
    )


# ── Reverse geocoding ──────────────────────────────────────────────────────────

def batch_geocode(coords: list) -> dict:
    try:
        import reverse_geocoder as rg
    except ImportError:
        sys.exit(
            "reverse_geocoder is not installed.\n"
            "Run: pip install reverse_geocoder"
        )
    unique = list(set(coords))
    results = rg.search(unique, verbose=False)
    mapping = {}
    for coord, r in zip(unique, results):
        cc = r.get("cc", "")
        admin1 = r.get("admin1", "")
        city = r.get("name", "")
        country = COUNTRY_NAMES.get(cc, slugify(cc or "unknown"))
        if cc == "CA":
            state = PROVINCE_ABBR.get(admin1, slugify(admin1 or "unknown"))
        elif cc == "US":
            state = STATE_ABBR.get(admin1, slugify(admin1 or "unknown"))
        else:
            state = slugify(admin1 or "unknown")
        area = AREA_ALIASES.get(slugify(city or "unknown"), slugify(city or "unknown"))
        mapping[coord] = (country, state, area)
    return mapping


# ── Config persistence ─────────────────────────────────────────────────────────

_DEFAULT_DATA_DIR = Path.home() / ".geo-photo-renamer"
_CONFIG_FILE = _DEFAULT_DATA_DIR / "config.json"


def load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(config: dict) -> None:
    _DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


# ── Counts persistence ─────────────────────────────────────────────────────────

def load_counts(counts_file: Path) -> dict:
    if counts_file.exists():
        return json.loads(counts_file.read_text(encoding="utf-8"))
    return {}


def save_counts(counts: dict, counts_file: Path) -> None:
    counts_file.write_text(json.dumps(counts, indent=2, sort_keys=True), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    from geo_renamer import __version__

    parser = argparse.ArgumentParser(
        prog="geo-rename",
        description=(
            "Rename photos and videos using GPS metadata.\n\n"
            "Output format: COUNTRY--STATE--AREA--NNN.ext\n"
            "  e.g. canada--bc--vancouver--042.jpg"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "folders",
        nargs="*",
        metavar="FOLDER",
        help="Folder(s) containing photos/videos to rename (uses saved default if omitted)",
    )
    parser.add_argument(
        "--set-default",
        metavar="DIR",
        help="Save DIR as the default source folder and exit",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="DIR",
        default=None,
        help="Where to place renamed files (default: ~/Pictures/geo-renamed)",
    )
    parser.add_argument(
        "--data-dir",
        metavar="DIR",
        default=None,
        help="Where to store rename_counts.json and rename_log.txt "
             "(default: ~/.geo-photo-renamer)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without moving any files",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip the confirmation prompt",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"geo-rename {__version__}",
    )
    args = parser.parse_args()

    config = load_config()

    # ── Handle --set-default ───────────────────────────────────────────────────
    if args.set_default:
        folder = Path(args.set_default).expanduser().resolve()
        if not folder.is_dir():
            sys.exit(f"ERROR: folder not found — {folder}")
        config["default_folder"] = str(folder)
        save_config(config)
        print(f"Default folder set to: {folder}")
        print("Run  geo-rename  with no arguments to use it.")
        sys.exit(0)

    # ── Resolve folders — fall back to saved default ───────────────────────────
    if not args.folders:
        default = config.get("default_folder")
        if default:
            print(f"  Using saved default folder: {default}")
            args.folders = [default]
        else:
            print("No folder specified and no default folder is set.\n")
            print("  Usage:  geo-rename FOLDER [FOLDER ...]")
            print("  Or set a default folder once with:")
            print("    geo-rename --set-default ~/path/to/photos\n")
            print("  Then just run:  geo-rename")
            sys.exit(1)

    # ── Resolve paths ──────────────────────────────────────────────────────────
    source_dirs: list[Path] = [Path(f).expanduser().resolve() for f in args.folders]

    output_dir = Path(args.output).expanduser().resolve() if args.output else Path.home() / "Pictures" / "geo-renamed"

    data_dir = (
        Path(args.data_dir).expanduser().resolve()
        if args.data_dir
        else Path.home() / ".geo-photo-renamer"
    )
    counts_file = data_dir / "rename_counts.json"
    log_file = data_dir / "rename_log.txt"

    # ── Banner ─────────────────────────────────────────────────────────────────
    sep = "-" * 60
    print(f"\n{sep}")
    print("  geo-rename" + ("  [DRY RUN]" if args.dry_run else ""))
    print(sep)
    for sd in source_dirs:
        print(f"  Source  : {sd}")
    print(f"  Output  : {output_dir}")
    print(f"  Data    : {data_dir}")
    if EXIFTOOL:
        print(f"  exiftool: {EXIFTOOL}  (video GPS enabled)")
    else:
        print("  exiftool: not found  (install via  brew install exiftool  for video GPS)")
    if _heic_ok:
        print("  HEIC    : pillow-heif OK")
    else:
        print("  HEIC    : pillow-heif not installed (JSON sidecars still work)")
    print(f"{sep}\n")

    # ── Validate source folders ────────────────────────────────────────────────
    valid_dirs: list[Path] = []
    for sd in source_dirs:
        if not sd.is_dir():
            print(f"WARNING: folder not found — {sd}")
        else:
            valid_dirs.append(sd)

    if not valid_dirs:
        print("No valid source folders. Exiting.")
        sys.exit(1)

    # ── 1. Collect media files ─────────────────────────────────────────────────
    print("Scanning for media files ...")
    all_files: list[Path] = []
    for sd in valid_dirs:
        for root, dirs, files in os.walk(sd):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                p = Path(root) / name
                if p.suffix.lower() in MEDIA_EXTS and not name.startswith("."):
                    all_files.append(p)

    print(f"  Found {len(all_files)} media files\n")
    if not all_files:
        print("Nothing to do.")
        sys.exit(0)

    # ── 2. Extract GPS ─────────────────────────────────────────────────────────
    print("Extracting GPS coordinates ...")
    file_coords: dict[Path, tuple] = {}
    no_gps_files: list[Path] = []

    for i, f in enumerate(all_files, 1):
        progress_bar(i, len(all_files), f.name[:30])
        coords = get_gps(f)
        if coords:
            file_coords[f] = coords
        else:
            no_gps_files.append(f)

    print(f"\n  GPS found   : {len(file_coords)}")
    print(f"  No GPS data : {len(no_gps_files)}  (will be skipped)\n")

    if not file_coords:
        print("No files with GPS data — nothing to rename.")
        sys.exit(0)

    # ── 3. Reverse geocode ─────────────────────────────────────────────────────
    print("Reverse geocoding ...")
    coord_to_loc = batch_geocode(list(file_coords.values()))
    print("  Done.\n")

    # ── 4. Load existing counts ────────────────────────────────────────────────
    data_dir.mkdir(parents=True, exist_ok=True)
    counts = load_counts(counts_file)

    # ── 5. Build rename plan ───────────────────────────────────────────────────
    sorted_files = sorted(file_coords.items(), key=lambda x: (str(x[0].parent), x[0].name))

    rename_ops: list[tuple[Path, Path]] = []
    for src, coords in sorted_files:
        loc = coord_to_loc.get(coords)
        if not loc:
            continue
        country, state, area = loc
        area_key = f"{country}--{state}--{area}"
        ext_lower = src.suffix.lower()

        area_counts = counts.setdefault(area_key, {})
        new_count = area_counts.get(ext_lower, 0) + 1
        area_counts[ext_lower] = new_count

        new_name = f"{area_key}--{new_count:03d}{src.suffix}"
        dst = output_dir / new_name

        if dst.exists():
            n = 1
            while (output_dir / f"{area_key}--{new_count:03d}-dup{n:02d}{src.suffix}").exists():
                n += 1
            dst = output_dir / f"{area_key}--{new_count:03d}-dup{n:02d}{src.suffix}"

        rename_ops.append((src, dst))

    # ── 6. Preview ─────────────────────────────────────────────────────────────
    print(f"{sep}")
    print(f"  Rename preview  ({len(rename_ops)} files)")
    print(sep)
    for src, dst in rename_ops[:15]:
        print(f"  {src.name:<45}  ->  {dst.name}")
    if len(rename_ops) > 15:
        print(f"  ... and {len(rename_ops) - 15} more")
    print()

    if args.dry_run:
        print("Dry run — no files were moved.")
        sys.exit(0)

    # ── 7. Confirm ─────────────────────────────────────────────────────────────
    if not args.yes:
        try:
            answer = input(
                f"Proceed? Move {len(rename_ops)} files to {output_dir}/  [y/N]  "
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)
        if answer not in ("y", "yes"):
            print("Aborted — no files were moved.")
            sys.exit(0)

    # ── 8. Execute ─────────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    print()
    success = errors = 0
    for i, (src, dst) in enumerate(rename_ops, 1):
        progress_bar(i, len(rename_ops), dst.name[:30])
        try:
            shutil.move(str(src), str(dst))
            success += 1
        except Exception as e:
            print(f"\n  ERROR: {src.name} — {e}")
            errors += 1

    # ── 9. Save counts ─────────────────────────────────────────────────────────
    save_counts(counts, counts_file)

    # ── 10. Write log ──────────────────────────────────────────────────────────
    with open(log_file, "a", encoding="utf-8") as log:
        log.write(f"\n{'=' * 70}\n")
        log.write(f"Date   : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Source : {[str(d) for d in valid_dirs]}\n")
        log.write(f"Output : {output_dir}\n")
        log.write(f"Moved  : {success}  |  Skipped: {len(no_gps_files)}  |  Errors: {errors}\n")
        log.write("-" * 70 + "\n")
        for src, dst in rename_ops:
            log.write(f"  {src.name:<60}  ->  {dst.name}\n")
        if no_gps_files:
            log.write("\nSkipped (no GPS):\n")
            for f in no_gps_files:
                log.write(f"  {f.name}\n")

    # ── 11. Summary ────────────────────────────────────────────────────────────
    area_tally: dict[str, int] = defaultdict(int)
    for _, dst in rename_ops:
        parts = dst.stem.split("--")
        if len(parts) >= 3:
            area_tally["--".join(parts[:3])] += 1

    print(f"\n{sep}")
    print(f"  Moved   : {success}")
    print(f"  Skipped : {len(no_gps_files)}  (no GPS)")
    if errors:
        print(f"  Errors  : {errors}")
    print(sep)
    if area_tally:
        print("  By area:")
        for area, cnt in sorted(area_tally.items()):
            print(f"    {area:<45}  {cnt:>4} files")
    print(sep)
    print(f"  Counts  ->  {counts_file}")
    print(f"  Log     ->  {log_file}")
    print()

    if no_gps_files:
        print("  Skipped files (no GPS):")
        for f in no_gps_files[:8]:
            print(f"    {f.name}")
        if len(no_gps_files) > 8:
            print(f"    ... and {len(no_gps_files) - 8} more (see rename_log.txt)")
        print()


def _ensure_exiftool() -> None:
    """Install exiftool via Homebrew on macOS if not already present."""
    if shutil.which("exiftool"):
        print("exiftool: already installed")
        return
    import platform
    if platform.system() == "Darwin":
        brew = shutil.which("brew")
        if not brew:
            print("Warning: Homebrew not found — cannot auto-install exiftool.")
            print("  Install manually: brew install exiftool")
            return
        print("Installing exiftool via Homebrew...")
        subprocess.run([brew, "install", "exiftool"], check=False)
    else:
        print("Warning: exiftool not found — video GPS extraction will be unavailable.")
        print("  Install with: sudo apt install libimage-exiftool-perl   # Debian/Ubuntu")
        print("             or: sudo dnf install perl-Image-ExifTool      # Fedora/RHEL")


def update() -> None:
    from geo_renamer import __version__

    repo = "https://github.com/airrickdunfield/geo-photo-renamer.git"
    package = f"git+{repo}"

    print(f"geo-update: current version {__version__}")
    print(f"Fetching latest from {repo} ...")

    pipx = shutil.which("pipx")
    if not pipx:
        sys.exit("pipx not found — cannot update. Install pipx and re-run the install script.")

    result = subprocess.run(
        [pipx, "install", "--force", package],
        text=True,
    )

    if result.returncode == 0:
        _ensure_exiftool()

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
