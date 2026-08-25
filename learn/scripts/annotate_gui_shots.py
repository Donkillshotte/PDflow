#!/usr/bin/env python3
"""Label OpenROAD GUI screenshots for the pixel-level atlas."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SHOT = Path("/workspace/learn/reference/gui-shots")


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def box_label(draw, xy, text, color, fnt, fill=(0, 0, 0, 170)):
    x0, y0, x1, y1 = xy
    overlay_color = color + (90,)
    draw.rectangle([x0, y0, x1, y1], outline=color, width=4)
    tw = draw.textlength(text, font=fnt)
    th = 22
    tx, ty = x0 + 6, max(4, y0 - th - 4)
    if ty < 2:
        ty = y0 + 6
    draw.rectangle([tx - 4, ty - 2, tx + tw + 8, ty + th], fill=fill)
    draw.text((tx, ty), text, fill=color, font=fnt)


def annotate_anatomy() -> None:
    src = SHOT / "win_anatomy.png"
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(18)
    # Measured on 1680x1000 Qt window (OpenROAD 26Q2).
    regions = [
        ((0, 0, w - 1, 28), (255, 210, 40), "A  Menu: File  View  Tools  Windows  Options  Help"),
        ((0, 28, 420, 56), (255, 140, 40), "B  Toolbar: Fit | Find | Inspect | Timing"),
        ((0, 56, 268, 760), (80, 200, 255), "C  Display Control (layer tree)"),
        ((268, 56, 1390, 760), (90, 255, 120), "D  Layout canvas (die + metals)"),
        ((1390, 56, w - 1, 760), (255, 90, 200), "E  Inspector / Timing / Charts / Help"),
        ((0, 760, w - 1, h - 28), (255, 255, 255), "F  Scripting console + TCL commands"),
        ((0, h - 28, w - 1, h - 1), (180, 180, 180), "G  Status: Idle"),
    ]
    for xy, color, text in regions:
        box_label(d, xy, text, color, f)
    out = Image.alpha_composite(im, overlay).convert("RGB")
    dest = SHOT / "win_anatomy_labeled.png"
    out.save(dest, quality=92)
    print(f"WROTE {dest} {dest.stat().st_size}")


def annotate_pdn_canvas() -> None:
    src = SHOT / "03_pdn.png"
    if not src.exists():
        return
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(22)
    notes = [
        (12, 12, "DIE (bordo blu) — 2_4_floorplan_pdn.odb"),
        (12, 48, "Linee blu sottili = rail M1 sulle rows (followpin)"),
        (12, 84, "Barre verdi verticali = strap power (metal alto)"),
        (12, 120, "Barre rosa orizzontali = strap power (metal alto)"),
        (12, h - 40, "Nessuna cella logica: il PDN esiste prima del placement"),
    ]
    for x, y, text in notes:
        tw = d.textlength(text, font=f)
        d.rectangle([x - 4, y - 2, x + tw + 10, y + 28], fill=(0, 0, 0, 200))
        d.text((x, y), text, fill=(255, 230, 80), font=f)
    dest = SHOT / "03_pdn_labeled.png"
    Image.alpha_composite(im, overlay).convert("RGB").save(dest, quality=92)
    print(f"WROTE {dest}")


def annotate_place() -> None:
    src = SHOT / "04_place_gp.png"
    if not src.exists():
        return
    im = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(22)
    notes = [
        (12, 12, "Global placement — celle sparse nel core (non ancora 'piastrellate')"),
        (12, 48, "Triangoli ciano/rossi sul bordo = pin I/O"),
        (12, 84, "Strap PDN ancora visibili sotto/sopra le celle"),
    ]
    for x, y, text in notes:
        tw = d.textlength(text, font=f)
        d.rectangle([x - 4, y - 2, x + tw + 10, y + 28], fill=(0, 0, 0, 200))
        d.text((x, y), text, fill=(120, 220, 255), font=f)
    dest = SHOT / "04_place_gp_labeled.png"
    Image.alpha_composite(im, overlay).convert("RGB").save(dest, quality=92)
    print(f"WROTE {dest}")


def annotate_route() -> None:
    src = SHOT / "08_route.png"
    if not src.exists():
        return
    im = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(22)
    notes = [
        (12, 12, "Detailed route — spaghetti colorati = wire su layer diversi"),
        (12, 48, "Rosso ≈ metal2   verde ≈ metal3   (vedi Display Control)"),
        (12, 84, "Confronto: 07_grt.png ha guide, non questi wire fini"),
    ]
    for x, y, text in notes:
        tw = d.textlength(text, font=f)
        d.rectangle([x - 4, y - 2, x + tw + 10, y + 28], fill=(0, 0, 0, 200))
        d.text((x, y), text, fill=(255, 160, 160), font=f)
    dest = SHOT / "08_route_labeled.png"
    Image.alpha_composite(im, overlay).convert("RGB").save(dest, quality=92)
    print(f"WROTE {dest}")


def crop_display_control() -> None:
    src = SHOT / "win_anatomy.png"
    im = Image.open(src)
    crop = im.crop((0, 0, 280, 780))
    dest = SHOT / "win_display_control_crop.png"
    crop.save(dest)
    print(f"WROTE {dest}")


def crop_inspector() -> None:
    src = SHOT / "win_inspector_tab.png"
    im = Image.open(src)
    w, h = im.size
    crop = im.crop((1385, 50, w, 760))
    dest = SHOT / "win_inspector_clk_crop.png"
    crop.save(dest)
    print(f"WROTE {dest}")


if __name__ == "__main__":
    annotate_anatomy()
    annotate_pdn_canvas()
    annotate_place()
    annotate_route()
    crop_display_control()
    crop_inspector()
