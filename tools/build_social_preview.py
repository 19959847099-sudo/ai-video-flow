"""Compose a GitHub social preview from the real public Production capture."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT = ROOT / "docs/assets/screenshots/production-1600x1000.png"
OUTPUT = ROOT / "docs/assets/social-preview.png"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def main() -> None:
    image = Image.new("RGB", (1280, 640), "#f6f8f9")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 28, 1252, 612), radius=24, fill="#ffffff", outline="#dce5e9", width=2)
    draw.rounded_rectangle((56, 61, 65, 111), radius=4, fill="#22a08a")
    draw.text((85, 58), "AI Video Flow", font=font(53, True), fill="#142430")
    draw.text((85, 141), "AI video production workflow", font=font(24), fill="#425968")
    draw.text((85, 184), "for Windows", font=font(24), fill="#425968")
    draw.line((85, 249, 405, 249), fill="#d6e1e6", width=2)
    labels = ("PREPARATION", "PRODUCTION", "CREATIVE", "ASSEMBLY")
    for index, label in enumerate(labels):
        y = 280 + index * 54
        draw.rounded_rectangle((85, y, 388, y + 40), radius=9,
                               fill="#edf5f4" if index == 1 else "#f5f7f8")
        draw.text((105, y + 10), label, font=font(17, True), fill="#21434a")
    draw.text((85, 553), "v0.1.0-rc.1  ·  Real D-layout capture", font=font(17), fill="#6a7c86")

    with Image.open(SCREENSHOT) as source:
        ui = source.convert("RGB")
        ui.thumbnail((767, 510), Image.Resampling.LANCZOS)
    frame = Image.new("RGB", (780, 523), "#d8e2e7")
    frame.paste(ui, ((780 - ui.width) // 2, (523 - ui.height) // 2))
    image.paste(frame, (445, 58))
    image.save(OUTPUT, optimize=True)
    print(f"{OUTPUT.name}: {OUTPUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
