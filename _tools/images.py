#!/usr/bin/env python3
"""Turns the App Store screenshots and the app stills into small WebP files for the site.

  python3 _tools/images.py <Sodalite/Marketing> [<extra-ui-dir>]

Reads asc/screenshots-1.1/<platform>/<asc locale>/*.png into media/shots/<code>/<slot>.webp and
the English UI stills from app-previews/clips into media/ui/<name>.webp. Idempotent: an output
newer than its source is skipped. Needs Pillow and cwebp.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from locales import LOCALES, asc_folder  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 150_000

# slot prefix -> (asc platform folder, file prefix, count, width)
SHOTS = {
    "tv": ("appletv", "tv", 6, 1400),
    "iphone": ("ios", "iphone", 6, 480),
    "ipad": ("ios", "ipad", 5, 1000),
    "mac": ("osx", "mac", 5, 1200),
}

# output name -> (path under Marketing/app-previews/clips, width)
UI = {
    "tvos-home": ("ph/home.png", 1400),
    "tvos-detail": ("ph/detail.png", 1400),
    "tvos-player": ("ph/player.png", 1400),
    "tvos-livetv": ("ph/livetv.png", 1400),
    "tvos-multiview": ("ph/multiview.png", 1400),
    "tvos-catalog": ("ph/catalog.png", 1400),
    "tvos-catalog-detail": ("ph/catalog_detail.png", 1400),
    "tvos-request": ("ph/request.png", 1400),
    "iphone-home": ("iphone-still/home.png", 480),
    "iphone-detail": ("iphone-still/detail.png", 480),
    "iphone-livetv": ("iphone-still/livetv.png", 480),
    "iphone-settings": ("iphone-still/settings.png", 480),
    "iphone-player": ("iphone-still/player.png", 900),
    "ipad-home": ("ipad-still/home.png", 1000),
    "ipad-livetv": ("ipad-still/livetv.png", 1000),
    "ipad-welcome": ("ipad-still/settings.png", 800),
    "mac-home": ("mac-still/home.png", 1200),
    "mac-detail": ("mac-still/detail.png", 1200),
}


def encode(src, dst, width):
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            im.save(tmp.name)
            tmp_path = tmp.name
    try:
        q = 78
        while True:
            subprocess.run(["cwebp", "-quiet", "-m", "6", "-q", str(q), tmp_path, "-o", dst], check=True)
            if os.path.getsize(dst) <= LIMIT or q <= 40:
                break
            q -= 6
    finally:
        os.unlink(tmp_path)
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    marketing = sys.argv[1]
    asc = os.path.join(marketing, "asc", "screenshots-1.1")
    clips = os.path.join(marketing, "app-previews", "clips")
    extra = sys.argv[2] if len(sys.argv) > 2 else None
    done = 0
    for code in LOCALES:
        for slot, (platform, prefix, count, width) in SHOTS.items():
            for n in range(1, count + 1):
                src = os.path.join(asc, platform, asc_folder(code), f"{prefix}_{n}.png")
                dst = os.path.join(ROOT, "media", "shots", code.lower(), f"{slot}-{n}.webp")
                done += encode(src, dst, width)
    for name, (rel, width) in UI.items():
        done += encode(os.path.join(clips, rel), os.path.join(ROOT, "media", "ui", f"{name}.webp"), width)
    if extra:
        for f in sorted(os.listdir(extra)):
            if f.endswith(".png"):
                done += encode(os.path.join(extra, f), os.path.join(ROOT, "media", "ui", f[:-4] + ".webp"), 1400)
    print(f"encoded {done} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
