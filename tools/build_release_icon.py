"""Generate the owned, minimal V0.1 release icon; no external artwork."""
from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image, ImageDraw


def render() -> Image.Image:
    size = 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((34, 34, 990, 990), radius=228, fill="#192534")
    draw.rounded_rectangle((64, 64, 960, 960), radius=198, outline="#5BD2D8", width=38)
    draw.polygon(((370, 257), (370, 767), (759, 512)), fill="#F7FBFA")
    return image


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parents[1] / "packaging" / "windows" / "AI-Video-Flow.ico"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    render().save(target, format="ICO", sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256),
    ])
    print(target)


if __name__ == "__main__":
    main()
