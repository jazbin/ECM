"""
Build contact-sheet montages from already-rendered per-case PNGs.
Pure 2D image compositing (PIL) -- no CAD/geometry operations here.

Usage: python3 make_montages.py <output_dir>
"""
import sys
import os
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from step_render_common import CASE_META, T_PROGRESSION

LABEL_H = 60
THUMB = 500


def load_thumb(path):
    im = Image.open(path).convert("RGBA")
    im.thumbnail((THUMB, THUMB), Image.LANCZOS)
    return im


def font(size=28):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def montage(case_ids, suffix, out_path, title, ncols=6):
    thumbs = []
    for cid in case_ids:
        p = os.path.join(os.path.dirname(out_path), f"{cid}_{suffix}.png")
        if not os.path.exists(p):
            continue
        thumbs.append((cid, load_thumb(p)))
    if not thumbs:
        print(f"WARNING: no images found for {suffix}")
        return
    nrows = (len(thumbs) + ncols - 1) // ncols
    cell_w, cell_h = THUMB, THUMB + LABEL_H
    canvas = Image.new("RGBA", (cell_w * ncols, cell_h * nrows + 70), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), title, fill=(0, 0, 0, 255), font=font(34))
    for i, (cid, im) in enumerate(thumbs):
        r, c = divmod(i, ncols)
        x = c * cell_w
        y = 70 + r * cell_h
        canvas.paste(im, (x + (cell_w - im.width) // 2, y), im)
        draw.text((x + 10, y + THUMB), cid, fill=(0, 0, 0, 255), font=font(30))
    canvas.save(out_path)
    print(f"wrote {out_path} ({len(thumbs)} panels)")


def t_progression_strip(out_path, suffix="D_POS_END_ZOOM_FIXED_SCALE", title_note="+Ve end zoom, FIXED camera/crop/scale (not auto-fit)"):
    thumbs = []
    for cid in T_PROGRESSION:
        p = os.path.join(os.path.dirname(out_path), f"{cid}_{suffix}.png")
        if os.path.exists(p):
            thumbs.append((cid, load_thumb(p)))
    if not thumbs:
        print(f"WARNING: T-progression strip ({suffix}): no images found")
        return
    cell_w, cell_h = THUMB, THUMB + LABEL_H
    canvas = Image.new("RGBA", (cell_w * len(thumbs), cell_h + 70), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), f"T01 | T04 | T05 | T06 | T07 | T08  ({title_note})",
               fill=(0, 0, 0, 255), font=font(30))
    for i, (cid, im) in enumerate(thumbs):
        x = i * cell_w
        y = 70
        canvas.paste(im, (x + (cell_w - im.width) // 2, y), im)
        draw.text((x + 10, y + THUMB), cid, fill=(0, 0, 0, 255), font=font(30))
        if i > 0:
            draw.line([(x, 70), (x, 70 + THUMB)], fill=(180, 180, 180, 255), width=2)
    canvas.save(out_path)
    print(f"wrote {out_path} ({len(thumbs)} panels)")


def main():
    out_dir = sys.argv[1]
    all_cases = list(CASE_META.keys())
    montage(all_cases, "A_FULL_TRANSPARENT_ISO", os.path.join(out_dir, "MONTAGE_FULL_TRANSPARENT_ISO.png"),
            "FULL_TRANSPARENT_ISO — all successful cases")
    montage(all_cases, "B_CAN_TRANSPARENT_ISO", os.path.join(out_dir, "MONTAGE_CAN_TRANSPARENT_ISO.png"),
            "CAN_TRANSPARENT_ISO — all successful cases")
    montage(all_cases, "C_INTERNALS_ISO", os.path.join(out_dir, "MONTAGE_INTERNALS_ISO.png"),
            "INTERNALS_ISO — all successful cases")
    t_progression_strip(os.path.join(out_dir, "T_PROGRESSION_T01_T04_T05_T06_T07_T08.png"))
    t_progression_strip(os.path.join(out_dir, "T_PROGRESSION_WHOLECELL_AUTOFIT.png"),
                         suffix="B_CAN_TRANSPARENT_ISO",
                         title_note="whole-cell CAN_TRANSPARENT_ISO, per-case auto-fit -- NOT same scale, context only")
    montage(all_cases, "E_THREEPART_CAN_TRANSPARENT_ISO",
            os.path.join(out_dir, "MONTAGE_THREEPART_CAN_TRANSPARENT_ISO.png"),
            "Three-part (Can+Jellyroll+Cap) only, Can transparent -- all successful cases")
    montage(all_cases, "F_THREEPART_INTERNALS_ISO",
            os.path.join(out_dir, "MONTAGE_THREEPART_INTERNALS_ISO.png"),
            "Three-part (Jellyroll+Cap only, Can hidden) -- all successful cases")


if __name__ == "__main__":
    main()
