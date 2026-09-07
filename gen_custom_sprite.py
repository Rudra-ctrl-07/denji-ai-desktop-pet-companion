"""
gen_custom_sprite.py — Renders the pet sprite: the classic Batman logo.

The iconic 1969-2000 emblem — a thick black-rimmed yellow oval with the
wide-winged black bat silhouette — is drawn from the bundled SVG
(assets/custom/batman_logo.svg, a vector recreation) and rasterized to a
transparent 128×128 PNG at assets/custom/pet.png.

To use a different image instead: simply replace assets/custom/pet.png with
your own PNG — the app loads it automatically for every state.
"""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SIZE = 128
FIT = 118  # max logo dimension inside the canvas (padding around it)


def render_pet(svg_path: Path, out_path: Path) -> bool:
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Could not load SVG: {svg_path}")

    img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    ds = renderer.defaultSize()
    scale = min(FIT / ds.width(), FIT / ds.height())
    w = ds.width() * scale
    h = ds.height() * scale
    target = QRectF((SIZE - w) / 2, (SIZE - h) / 2, w, h)
    renderer.render(p, target)
    p.end()

    return img.save(str(out_path))


def main() -> None:
    # A QGuiApplication is required for QSvgRenderer to work.
    _app = QGuiApplication.instance() or QGuiApplication([])

    svg = Path("assets") / "custom" / "batman_logo.svg"
    out = Path("assets") / "custom" / "pet.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = render_pet(svg, out)
    print(f"Rendered {svg} -> {out} ({'OK' if ok else 'FAILED'})")


if __name__ == "__main__":
    main()
