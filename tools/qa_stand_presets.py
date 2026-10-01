"""0.6.6 release QA: prior-package preservation and independent raster measurements.

Run after asset_pipeline.py --apply, with --baseline artifacts/pre-qa-0.6.6.
Does not import the generator; measures the actual shipped PNG/config files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Airport Decal Pack Countinue/CustomAssets"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return list(zip(np.where(edges == 1)[0], np.where(edges == -1)[0]))


def inspect_texture(record, palette):
    folder = ASSETS / record["path"]
    config = read(folder / "decal.json")
    width, height = record["mesh_m"]
    mesh = config["Vector"]["colossal_MeshSize"]
    check(np.allclose([mesh["x"], mesh["z"]], [width, height], rtol=0, atol=0.000001), f"Mesh mismatch: {folder}")
    check(config["UiPriority"] == record["UiPriority"], f"Priority mismatch: {folder}")
    check(config["Float"]["_DrawOrder"] == record["draw_order"], f"Layer mismatch: {folder}")
    im = Image.open(folder / "_BaseColorMap.png").convert("RGBA")
    check(im.size == (record["texture_px"],) * 2, f"Resolution mismatch: {folder}")
    data = np.asarray(im)
    px, py = width / im.width, height / im.height
    check(np.max(data[0, :, 3]) == np.max(data[-1, :, 3]) == 0, "Vertical texture clipping")
    check(np.max(data[:, 0, 3]) == np.max(data[:, -1, 3]) == 0, "Horizontal texture clipping")

    def color(name):
        # Antialiased strokes may blend with their opaque black edging. Count
        # pixels by the nearest paint colour rather than only perfectly solid RGB.
        rgb = data[:, :, :3].astype(np.int32)
        distance = np.sum((rgb - palette[name]) ** 2, axis=2)
        mask = data[:, :, 3] >= 128
        for other, value in palette.items():
            if other != name:
                mask &= distance < np.sum((rgb - value) ** 2, axis=2)
        return mask

    def sample(mask, x, y):
        xi = np.clip((np.asarray(x) / px).astype(int), 0, im.width - 1)
        yi = np.clip((np.asarray(y) / py).astype(int), 0, im.height - 1)
        return mask[yi, xi]

    measured = {"priority": record["UiPriority"], "kind": record["kind"], "texture_px": im.width,
                "pixel_m": [px, py]}

    def near(value, target, tolerance, label):
        check(abs(value - target) <= tolerance, f"{record['path']}: {label} {value:.5f} != {target}")
        measured[label] = round(float(value), 6)

    kind = record["kind"]
    if kind == "stand":
        red, yellow = color("Red"), color("Yellow")
        middle = int(im.height / 2)
        side = runs(red[middle])[0]
        near((side[1] - side[0]) * px, 0.1, px * 1.6, "red_line_m")
        lead = runs(yellow[middle])
        check(len(lead) == 1, "Missing/unexpected guidance stroke")
        near((lead[0][1] - lead[0][0]) * px, record["lead_width_m"], px * 1.6, "lead_m")
        near((side[1] + 0.5) * px, 0.15 + 0.1, px * 1.6, "inner_left_m")
        for y in np.linspace(*record["id_gap_y_m"], 9)[1:-1]:
            check(not sample(yellow, width / 2, y), "Identification gap painted over")
        profile = record["profile"]
        limits = {"A": (0, 15), "B": (15, 24), "C": (24, 36), "D": (36, 52), "E": (52, 65), "F": (65, 80)}
        lo, hi = limits[profile["code"]]
        check(lo <= profile["span_m"] < hi, "Wrong wingspan code boundary")
        clearance = {"A": 3, "B": 3, "C": 4.5, "D": 7.5, "E": 7.5, "F": 7.5}[profile["code"]]
        check(np.allclose(record["inner_m"], [profile["span_m"] + 2 * clearance, profile["length_m"] + 2 * clearance]), "Insufficient envelope")
        check(record["stop_datum"].startswith("separate"), "Fixed stop baked into stand")
        measured["inner_m"] = record["inner_m"]
    elif kind in ("nosewheel_stop", "pipb_stop", "cockpit_stop"):
        yellow = color("Yellow")
        x, y, w, h = record["bar_rect_m"]
        row = yellow[int((y + h / 2) / py)]
        a, b = int((x - 0.025) / px), math.ceil((x + w + 0.025) / px)
        rr = runs(row[a:b])
        near(max(v - u for u, v in rr) * px, w, px * 1.6, "bar_length_m")
        column = yellow[:, int((x + w / 4) / px)]
        near(max(v - u for u, v in runs(column)) * py, h, py * 1.6, "bar_stroke_m")
        if kind == "pipb_stop":
            check(record["bar_extension_m"] == 1.0 and w == 1.3, "CAAM extension confused with centred bar")
        if "text_rect_m" in record:
            tx, ty, tw, th = record["text_rect_m"]
            region = yellow[max(0, int(ty / py) - 1):math.ceil((ty + th) / py) + 1,
                            max(0, int(tx / px) - 1):math.ceil((tx + tw) / px) + 1]
            yy, xx = np.where(region)
            check(len(xx) > 0, "Empty type text")
            near((yy.max() - yy.min() + 1) * py, th, py * 2.5, "type_cap_m")
            check(record["text_rotation_deg"] == 180, "Wrong type text direction")
    elif kind == "no_parking_frame":
        red = color("Red")
        outer_w, outer_h = record["outer_m"]
        check(np.allclose([width, height], [outer_w + 0.3, outer_h + 0.3]), "Wrong hatch outer size")
        extent = min(outer_w, outer_h) / 3
        t = np.linspace(-extent, extent, 8001)
        stripe = sample(red, width / 2 + t / math.sqrt(2), height / 2 - t / math.sqrt(2))
        rr = runs(stripe)[1:-1]
        paint = np.median([(b - a) * (t[1] - t[0]) for a, b in rr])
        pitch = np.median([(rr[i + 1][0] - rr[i][0]) * (t[1] - t[0]) for i in range(len(rr) - 1)])
        near(paint, 0.1, 2 * math.hypot(px, py), "hatch_stroke_m")
        near(pitch - paint, 0.75, 2 * math.hypot(px, py), "transparent_gap_m")
        check(np.any(~stripe) and np.any(stripe), "Hatch lacks transparent gaps")
    elif kind in ("equipment_frame", "pbb_wheel"):
        white = color("White")
        if kind == "pbb_wheel":
            check(sample(white, width / 2, height / 2), "PBB wheel is not white filled")
            check(list(data[im.height // 2, im.width // 2, :3]) == [177, 177, 177], "White changed")
            edge = runs(color("Red")[im.height // 2])[0]
        else:
            check(not data[im.height // 2, im.width // 2, 3], "Equipment frame interior not transparent")
            edge = runs(white[im.height // 2])[0]
        near((edge[1] - edge[0]) * px, 0.1, px * 1.6, "border_m")
    elif kind == "pbb_fan":
        white = color("White")
        ox, oy = record["origin_m"]
        radius = record["radius_m"]
        ray = runs(white[int((oy - radius / 2) / py)])
        u, v = min(ray, key=lambda uv: abs((uv[0] + uv[1]) * px / 2 - ox))
        near((v - u) * px, 0.1, px * 1.6, "ray_stroke_m")
        a = math.radians(-82.5)
        check(not data[int((oy + radius / 2 * math.sin(a)) / py), int((ox + radius / 2 * math.cos(a)) / px), 3], "Fan interior opaque")
    return measured


def preview(records):
    font_path = "C:/Windows/Fonts/arial.ttf"
    title_font = ImageFont.truetype(font_path, 34)
    font = ImageFont.truetype(font_path, 23)
    small = ImageFont.truetype(font_path, 20)
    sheet = Image.new("RGB", (1600, 1780), (30, 34, 40))
    draw = ImageDraw.Draw(sheet)
    draw.text((28, 20), "AIRPORT 0.6.6 | STATIC STAND TEMPLATES", fill="white", font=title_font)
    draw.text((28, 64), "True physical aspect ratio; transparent markings on grey. Stop positions are separate.", fill=(195, 205, 215), font=font)
    selected = [r for r in records if r["kind"] == "stand"]
    selected += [next(r for r in records if r["UiPriority"] == p) for p in (7450, 7451, 7452, 7780, 7781, 7800, 7820, 7830, 7840)]
    for i, r in enumerate(selected):
        if i < 8:
            x, y = (i % 4) * 400, 108 + (i // 4) * 425
            cell_w, image_h = 400, 320
            label = f"{r['UiPriority']}  {r['profile']['key']}"
            subtitle = "Inside: " + " x ".join(f"{n:g}" for n in r["inner_m"]) + " m"
        else:
            j = i - 8
            x, y = (j % 3) * 532, 976 + (j // 3) * 260
            cell_w, image_h = 532, 174
            label = f"{r['UiPriority']}  " + {7450: "CAAC nosewheel stop", 7451: "CAAM PIPB stop", 7452: "Cockpit reference stop", 7780: "CAAC + 0.3m type", 7781: "CAAM + 1m type", 7800: "PBB movement R12m", 7820: "PBB wheel 3m", 7830: "No-parking 6 x 10m", 7840: "Equipment 3 x 5m"}[r["UiPriority"]]
            subtitle = ""
        draw.rounded_rectangle((x + 12, y, x + cell_w - 12, y + image_h + 75), radius=10, fill=(65, 70, 76))
        draw.text((x + 24, y + 10), label, fill="white", font=font)
        if subtitle:
            draw.text((x + 24, y + 40), subtitle, fill=(205, 210, 215), font=small)
        width, height = r["mesh_m"]
        scale = min((cell_w - 55) / width, (image_h - 10) / height)
        im = Image.open(ASSETS / r["path"] / "_BaseColorMap.png").convert("RGBA")
        im = im.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
        sheet.paste(im, (round(x + (cell_w - im.width) / 2), y + 67), im)
    sheet.save(ROOT / "docs/stand-preview.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    old = read(args.baseline / "asset-catalog.json")
    rows = read(ROOT / "docs/asset-catalog.json")
    current = {r["path"]: r for r in rows}
    check(len(old) == 469 and len(rows) == 500, "Wrong release counts")
    check(all(current[r["path"]] == r for r in old), "Old catalog changed")
    check(Counter(r["type"] for r in rows) == {"StaticObjectPrefab": 457, "NetLaneGeometryPrefab": 34, "SurfacePrefab": 9}, "Wrong asset types")
    check(len({r["UiPriority"] for r in rows}) == len(rows), "Duplicate menu priority")
    check(len({r["prefab_name"] for r in rows}) == len(rows), "Duplicate prefab identity")
    check({str(Path(r["path"]).parent).replace('\\', '/') for r in rows} == {"CustomDecals/Alphabet", "CustomDecals/RoadMarkings", "CustomNetlanes/RoadMarking", "Surfaces/Pavement"}, "Unverified menu category")
    hashes = read(args.baseline / "source-sha256.json")
    preserved = 0
    for rel, expected in hashes.items():
        if rel.startswith("Localization/"):
            original = read(args.baseline / "LocalMod" / rel)
            now = read(ASSETS / rel)
            check(all(now.get(k) == v for k, v in original.items()), f"Existing {rel} text changed")
            check(len(now) == 1000, f"Incomplete {rel}")
        else:
            check(hashlib.sha256((ASSETS / rel).read_bytes()).hexdigest() == expected, f"Existing file changed: {rel}")
            preserved += 1
    details = read(ROOT / "docs/stand-presets.json")["assets"]
    check(len(details) == 31, "Incomplete new details")
    check({r["path"] for r in details} == set(current) - {r["path"] for r in old}, "Unexpected added asset")
    measured_planes = {7730: (34, 38), 7740: (50.5, 50.5), 7750: (58, 60)}
    for record in details:
        if record["UiPriority"] in measured_planes:
            check((record["profile"]["length_m"], record["profile"]["span_m"]) == measured_planes[record["UiPriority"]], "Game measurements changed")
    palette = read(ROOT / "asset-specs.json")["palette"]
    results = [inspect_texture(r, palette) for r in details]
    preview(details)
    report = {"version": "0.6.6", "status": "passed", "assets": 500, "added": 31,
              "existing_catalog_preserved": 469, "existing_asset_files_sha256_preserved": preserved,
              "existing_locale_entries_preserved": True, "raster_measurements": results,
              "game_validation": "pending; docs/test-round-7.md"}
    path = ROOT / "artifacts/qa-0.6.6.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: 500 assets; all 469 old records / {preserved} files / old locale values preserved; 31 raster checks.")
    print("Preview: docs/stand-preview.png; report: artifacts/qa-0.6.6.json")


if __name__ == "__main__":
    main()
