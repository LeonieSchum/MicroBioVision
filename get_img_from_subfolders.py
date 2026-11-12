"""Move one image per subfolder into the main folder.

Rule per subfolder:
  - exactly one image            -> move it
  - several images               -> move the one whose name ends with "_overlay"
  - several images, no/ambiguous overlay -> skip and warn

How to use in VS Code: set FOLDER and DRY_RUN below, then press "Run Python File".
"""
import shutil
from pathlib import Path

# ----------------------------- SETTINGS -----------------------------
FOLDER = r"C:\Users\leoschum\Nextcloud\02_Lab\02_EVOS\260825_BOS1"   # <- main folder that contains the subfolders
DRY_RUN = False                       # True = only print what would happen; set to False to really move
# --------------------------------------------------------------------

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}


def pick_image(images):
    """Return (chosen_file, problem_message)."""
    if len(images) == 1:
        return images[0], None
    overlays = [f for f in images if f.stem.lower().endswith("_overlay")]
    if len(overlays) == 1:
        return overlays[0], None
    if not overlays:
        return None, f"{len(images)} images, none ends with '_overlay'"
    return None, f"{len(overlays)} files end with '_overlay'"


def main(folder=FOLDER, dry_run=DRY_RUN):
    root = Path(folder).resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a folder: {root}")

    moved = skipped = 0
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        images = sorted(
            f for f in sub.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS
        )
        if not images:
            continue

        chosen, problem = pick_image(images)
        if chosen is None:
            print(f"SKIP  {sub.name}: {problem}")
            skipped += 1
            continue

        target = root / chosen.name
        if target.exists():  # name clash -> prefix with subfolder name
            target = root / f"{sub.name}_{chosen.name}"
            if target.exists():
                print(f"SKIP  {sub.name}: {target.name} already exists")
                skipped += 1
                continue

        print(f"{'WOULD MOVE' if dry_run else 'MOVE'}  {chosen.relative_to(root)} -> {target.name}")
        if not dry_run:
            shutil.move(str(chosen), str(target))
        moved += 1

    print(f"\nDone: {moved} moved, {skipped} skipped" + (" (dry run)" if dry_run else ""))


if __name__ == "__main__":
    main()