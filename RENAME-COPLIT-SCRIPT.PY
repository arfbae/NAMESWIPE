import os
import re
import tempfile
from pathlib import Path

BLOCKLIST = {
    "a","an","and","artwork","computer","device","digital","for","gpu",
    "graphic","icon","image","in","logo","of","on","photo","picture",
    "render","screenshot","the","to","wallpaper","with"
}

VALID_EXTS = {".jpg",".jpeg",".png",".webp",".heic",".heif",".bmp"}

def extract_date_suffix(filename):
    patterns = [
        r"(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})",
        r"(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if not match:
            continue
        if len(match.group(1)) == 4:
            year, month, day = match.group(1), match.group(2), match.group(3)
        else:
            day, month, year = match.group(1), match.group(2), match.group(3)
        return f"{int(day):02d}-{int(month):02d}-{int(year)}"
    return ""

def clean_base(name):
    base, ext = os.path.splitext(name)
    if ext.lower() not in VALID_EXTS:
        return False, f"bad extension: {name}"
    if not base:
        return False, f"empty basename: {name}"

    prefix = base.split("-")[0].lower()
    if prefix in BLOCKLIST:
        return False, f"junk prefix: {name}"

    parts = [p for p in re.split(r"[-_ ]+", base) if p]
    if len(parts) < 2:
        return False, f"too short: {name}"

    for p in parts[:3]:
        if p.lower() in BLOCKLIST:
            return False, f"generic token at front: {name}"

    if re.match(r"^(gpu|photo|image|picture|screenshot|computer|graphic|artwork)", base, re.I):
        return False, f"starts with generic token: {name}"

    if not re.match(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", base):
        return False, f"bad format: {name}"

    return True, "ok"

samples = [
    "Goldfish-Boombox-3D-Model-26-02-2025.jpg",
    "Illustration-Angry-Money-Block-Running-24-02-2025.jpg",
    "Woman-Sitting-On-Mushroom-3D-Sculpt-05-07-2025.jpg",
    "Character-Design-Box-Cutter-Graffiti-Style.png",
    "Gatorade-Character-18-03-2025.png",
    "gpu-crazy-image-thing.jpg",
    "photo-of-dog.jpg",
    "untitled.jpg",
    "a.jpg",
    "randomhash123.jpg",
]

good = []
bad = []

for s in samples:
    ok, reason = clean_base(s)
    if ok:
        good.append((s, reason))
    else:
        bad.append((s, reason))

print("GOOD:")
for s, reason in good:
    print("  OK  ", s)

print("\nBAD:")
for s, reason in bad:
    print("  FAIL", s, "->", reason)

print(f"\nSummary: {len(good)} good, {len(bad)} bad")

tmp = Path(tempfile.mkdtemp(prefix="nameswipe_check_"))
for s, _ in good:
    (tmp / s).write_bytes(b"fake")
print(f"\nSample folder created: {tmp}")
