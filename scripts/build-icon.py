from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "assets" / "app-icon.png"
OUTPUT = PROJECT_ROOT / "desktop" / "app.ico"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> None:
    with Image.open(SOURCE) as source:
        icon = ImageOps.fit(
            source.convert("RGBA"),
            (1024, 1024),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        icon.save(OUTPUT, format="ICO", sizes=[(size, size) for size in ICON_SIZES])

    print(f"Windows icon generated: {OUTPUT}")


if __name__ == "__main__":
    main()
