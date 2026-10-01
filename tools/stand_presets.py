"""Offline aircraft-stand templates. No runtime layout or save-game operations."""
from __future__ import annotations

import base64
import json
import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
# Supplement only this release's vocabulary; keep existing locale entries intact.
STAND_TRADITIONAL = str.maketrans({
    "参": "參", "务": "務", "干": "幹", "货": "貨", "后": "後",
    "桥": "橋", "动": "動", "圆": "圓", "备": "備", "从": "從",
    "竖": "豎", "范": "範", "过": "過", "于": "於", "辆": "輛",
    "凈": "淨", "驶": "駛", "驾": "駕", "员": "員", "适": "適", "轴": "軸",
})


def generate_stand_presets(p, Canvas, glyph, spec, colors, padding, png_bytes):
    records = []

    def add(name, priority, c, title, note, note_en, reference, geometry):
        rel = f"CustomDecals/RoadMarkings/{name}"
        order = 40 if geometry["kind"] == "no_parking_frame" else 41 if geometry["kind"] in (
            "stand", "pbb_fan", "pbb_wheel", "equipment_frame") else 42
        p.asset(rel, priority, c.width, c.height, title, note, reference,
                canvas=c, draw_order=order, note_en=note_en)
        full = p.rows[-1]["prefab_name"]
        for field in ("NAME", "DESCRIPTION"):
            key = f"Assets.{field}[{full}]"
            p.locales["zh-HANT"][key] = p.locales["zh-HANT"][key].translate(STAND_TRADITIONAL)
        records.append({"UiPriority": priority, "path": rel, "texture_px": c.resolution,
                        "mesh_m": [c.width, c.height], "draw_order": order, **geometry})

    def metrics(text, height):
        widths = [glyph(char).width / glyph(char).height * height for char in text]
        spacing = height * 0.15
        return sum(widths) + spacing * (len(widths) - 1), widths, spacing

    def text_stamp(c, text, x, y, height, rotate=180):
        """Preserve the author's PNG glyphs, including in the SVG authoring master."""
        width, widths, spacing = metrics(text, height)
        sx, sy = c.im.width / c.width, c.im.height / c.height
        mask = Image.new("L", (max(1, round(width * sx)), max(1, round(height * sy))))
        offset = 0.0
        for char, w in zip(text, widths):
            letter = glyph(char).resize((max(1, round(w * sx)), mask.height), Image.Resampling.LANCZOS)
            mask.paste(letter, (round(offset * sx), 0))
            offset += w + spacing
        stamp = Image.new("RGBA", mask.size, colors["Yellow"] + (0,))
        stamp.putalpha(mask)
        if rotate == 180:
            stamp = stamp.transpose(Image.Transpose.ROTATE_180)
        c.im.alpha_composite(stamp, (round(x * sx), round(y * sy)))
        encoded = base64.b64encode(png_bytes(stamp)).decode("ascii")
        c.svg.append(("paint", f'<image x="{x:.8g}" y="{y:.8g}" width="{width:.8g}" '
                      f'height="{height:.8g}" href="data:image/png;base64,{encoded}"/>'))
        return [x, y, width, height]

    def frame(c, x, y, width, height, stroke, color, entry=0):
        c.rect(x, y, width, stroke, color)
        c.rect(x, y, stroke, height, color)
        c.rect(x + width - stroke, y, stroke, height, color)
        side = (width - entry) / 2
        c.rect(x, y + height - stroke, side, stroke, color)
        c.rect(x + width - side, y + height - stroke, side, stroke, color)

    stand = spec["stand_presets"]
    border = stand["safety_line_m"]
    for profile in stand["profiles"]:
        clearance = stand["clearances_m"][profile["code"]]
        inner_w = profile["span_m"] + 2 * clearance
        inner_h = profile["length_m"] + 2 * clearance
        width, height = inner_w + 2 * border, inner_h + 2 * border
        c = Canvas(width + 2 * padding, height + 2 * padding, resolution=profile["texture_px"])
        entry = 4.0 if profile["code"] in "AB" else 6.0
        frame(c, padding, padding, width, height, border, colors["Red"], entry)
        axis = c.width / 2
        lead = profile["lead_width_m"]
        contrast = stand["lead_contrast_each_side_m"]
        inner_top = padding + border
        entry_y = inner_top + inner_h
        gap_end = entry_y - stand["id_gap_from_entry_m"]
        gap_start = gap_end - stand["id_gap_height_m"]
        head_y = inner_top + 1.0
        for start, end in [(head_y, gap_start), (gap_end, padding + height)]:
            c.rect(axis - lead / 2 - contrast, start, lead + 2 * contrast, end - start, colors["Black"])
            c.rect(axis - lead / 2, start, lead, end - start, colors["Yellow"])
        note = (f"透明直入机位模板：框内 {inner_w:g} × {inner_h:g} m，参照机长 {profile['length_m']:g} m、"
                f"翼展 {profile['span_m']:g} m；每侧预留 {clearance:g} m。黄线 {lead:g} m、红线 0.10 m。"
                "编号与停止线另放；机头朝红框封闭端。")
        add(f"Stand Template {profile['key']}", profile["priority"], c,
            f"直入机位模板 · {profile['title']} · {inner_w:g} × {inner_h:g} m", note,
            f"Transparent nose-in stand: {inner_w:g} x {inner_h:g} m inside the frame, for a "
            f"{profile['length_m']:g} m length / {profile['span_m']:g} m span reference. "
            f"{clearance:g} m margin on each side; {lead:g} m yellow guidance and 0.10 m red boundary. "
            "Place identification and stop marks separately. Nose toward the closed end.",
            "ICAO Annex 14 3.13.7/5.2.13/5.2.14；保守 S+2C、L+2C 包内矩形预设；原版三机型来自用户实测",
            {"kind": "stand", "profile": profile, "clearance_m": clearance,
             "inner_m": [inner_w, inner_h], "safety_line_m": border,
             "entry_opening_m": entry, "lead_width_m": lead,
             "axis_x_m": axis, "id_gap_y_m": [gap_start, gap_end],
             "nose_reference_y_m": inner_top + clearance,
             "stop_datum": "separate; nosewheel/cockpit distances were not measured"})

    detail = spec["stand_details"]

    def caac_stop(name, priority, label=None):
        cfg = detail["nosewheel_caac"]
        length, stroke, black = cfg["bar_length_m"], cfg["bar_width_m"], cfg["contrast_border_m"]
        cap = cfg["text_height_m"]
        text_w = metrics(label, cap)[0] if label else 0
        label_w, label_h = text_w + 0.10, cap + 0.10
        gap = 0.15
        paint_w = length + 2 * black + (gap + label_w if label else 0)
        paint_h = label_h if label else stroke + 2 * black
        c = Canvas(paint_w + 2 * padding, paint_h + 2 * padding)
        x, y = padding + black, c.height / 2 - stroke / 2
        c.rect(x - black, y - black, length + 2 * black, stroke + 2 * black, colors["Black"])
        c.rect(x, y, length, stroke, colors["Yellow"])
        geometry = {"kind": "nosewheel_stop", "region": "CAAC", "bar_m": [length, stroke],
                    "bar_rect_m": [x, y, length, stroke], "datum_m": [x + length / 2, y + stroke / 2]}
        if label:
            lx, ly = padding + length + 2 * black + gap, padding
            c.rect(lx, ly, label_w, label_h, colors["Black"])
            geometry.update({"text": label, "text_height_m": cap, "text_rotation_deg": 180,
                             "text_rect_m": text_stamp(c, label, lx + 0.05, ly + 0.05, cap)})
        suffix = f" · {label} · 30 cm 字" if label else ""
        add(name, priority, c, "鼻轮停止线 · CAAC · 2 m" + suffix,
            "黄色横线长 2 m、宽 0.15 m，黑边 0.05 m；横线中点对齐引导线，按鼻轮实际停止位置摆放。"
            + (f"旁注 {label}，作者字形、字高 0.30 m。" if label else "适用于人工或设备引导的鼻轮停止点。"),
            "Yellow 2 m x 0.15 m nosewheel stop bar with 0.05 m black contrast edging. "
            "Centre the bar on the guidance line; position it for the actual nosewheel. "
            + (f"{label} label in the author's font, 0.30 m high." if label else "For a marshalled or guided nosewheel stop."),
            "CAAC MH 5001—2021 6.2.16(7)、图 6.2.16-7；2025 第四修订案未涉及此条；标签间距为包内预设", geometry)

    def caam_stop(name, priority, label=None):
        cfg = detail["pipb_caam"]
        extension, lead, stroke = cfg["bar_extension_m"], cfg["lead_width_m"], cfg["bar_width_m"]
        cap = cfg["text_height_m"]
        label_h = cfg["label_height_m"]
        margin = cfg["label_side_margin_m"]
        label_w = metrics(label, cap)[0] + 2 * margin if label else 0
        gap = 0.15 if label else 0
        width = label_w + gap + extension + lead
        height = label_h if label else stroke + 0.6
        c = Canvas(width + 2 * padding, height + 2 * padding)
        x = padding + label_w + gap
        axis = x + extension + lead / 2
        y = padding + height / 2 - stroke / 2 if label else padding
        c.rect(x, y, extension + lead, stroke, colors["Yellow"])
        c.rect(axis - lead / 2, y, lead, stroke + 0.6, colors["Yellow"])
        geometry = {"kind": "pipb_stop", "region": "CAAM", "bar_extension_m": extension,
                    "bar_m": [extension + lead, stroke], "bar_rect_m": [x, y, extension + lead, stroke],
                    "datum_m": [axis, y + stroke / 2], "join_stub_m": 0.6}
        if label:
            c.rect(padding, padding, label_w, label_h, colors["Black"])
            geometry.update({"text": label, "text_height_m": cap, "text_rotation_deg": 180,
                             "text_rect_m": text_stamp(c, label, padding + margin, padding + (label_h - cap) / 2, cap)})
        suffix = f" · {label} · 1 m 字" if label else ""
        add(name, priority, c, "后推机位停止标记 · CAAM · 左伸 1 m" + suffix,
            "黄色横条从 0.30 m 引导线左缘伸出 1 m，横条宽 0.30 m；短竖段对齐机位中线，停止位置另定。"
            + (f"旁注 {label}，1 m 黄字、1.5 m 高黑底。" if label else "机型文字可另加。"),
            "Yellow stop bar extending 1 m left of the 0.30 m guidance line, with a 0.30 m stroke. "
            "Align the short vertical join with the stand centreline; select the stop position separately. "
            + (f"{label}: 1 m yellow lettering on a 1.5 m high black panel." if label else "Add an aircraft label separately."),
            "CAAM CAGM 1403 (2025) 图 5-9/5-14/5-15；1 m 指中线左缘外的净伸长；0.6 m 连接段为包内预设", geometry)

    caac_stop("Stand Nosewheel Stop CAAC 2m", 7450)
    caam_stop("Stand PIPB Stop CAAM 1m", 7451)
    cfg = detail["cockpit_stop"]
    length, stroke, black = cfg["bar_length_m"], cfg["bar_width_m"], 0.05
    c = Canvas(length + 2 * black + 2 * padding, stroke + 2 * black + 2 * padding)
    c.rect(padding, padding, length + 2 * black, stroke + 2 * black, colors["Black"])
    c.rect(padding + black, padding + black, length, stroke, colors["Yellow"])
    add("Stand Cockpit Stop 6m", 7452, c, "驾驶员参照停止线 · 6 m",
        "黄色横线长 6 m、宽 0.15 m，黑边 0.05 m；与机位轴线成直角，按左座驾驶员实际位置摆放。",
        "Yellow 6 m x 0.15 m stop bar with 0.05 m contrast edging. "
        "Place perpendicular to the stand axis, abeam the actual left pilot position.",
        "ICAO Annex 14 5.2.13.11；CAAM 4.3；独立停止线，不预设游戏飞机驾驶舱位置",
        {"kind": "cockpit_stop", "bar_m": [length, stroke],
         "bar_rect_m": [padding + black, padding + black, length, stroke],
         "datum_m": [padding + black + length, c.height / 2]})
    for index, label in enumerate(detail["type_labels"]):
        caac_stop(f"Stand Stop CAAC {label} 30cm Text", 7780 + index * 2, label)
        caam_stop(f"Stand Stop CAAM {label} 1m Text", 7781 + index * 2, label)

    for index, radius in enumerate(detail["pbb_fan_radii_m"]):
        angle, stroke = detail["pbb_fan_angle_degrees"], detail["pbb_fan_line_m"]
        half = math.radians(angle / 2)
        width, height = 2 * radius * math.sin(half) + stroke, radius + stroke
        c = Canvas(width + 2 * padding, height + 2 * padding, resolution=2048)
        origin = (c.width / 2, padding + radius + stroke / 2)
        start, end = -90 - angle / 2, -90 + angle / 2
        def point(degrees):
            a = math.radians(degrees)
            return origin[0] + radius * math.cos(a), origin[1] + radius * math.sin(a)
        steps = round(angle / detail["pbb_fan_ray_step_degrees"])
        for i in range(steps + 1):
            c.stroke(origin, point(start + i * angle / steps), stroke, colors["White"])
        arc_steps = 120
        for i in range(arc_steps):
            c.stroke(point(start + i * angle / arc_steps), point(start + (i + 1) * angle / arc_steps), stroke, colors["White"])
        add(f"PBB Movement Fan Heathrow R{radius:g}m", 7800 + index * 10, c,
            f"廊桥活动扇区 · Heathrow 样式 · 半径 {radius:g} m",
            f"透明白色放射线扇区，半径 {radius:g} m、张角 90°、线宽 0.10 m。尺寸为造景预设，按廊桥实际活动范围调整；轮位另放。",
            f"Transparent white starburst: {radius:g} m radius, 90 degrees, 0.10 m strokes. "
            "Scenery dimensions; fit the actual bridge movement envelope and place its wheel parking mark separately.",
            "Heathrow OSI 030 v3 §4.1.12 的活动区放射线样式；R12/R18、90°、15° 分线及0.10m为包内预设",
            {"kind": "pbb_fan", "radius_m": radius, "angle_degrees": angle,
             "stroke_m": stroke, "origin_m": origin})

    for index, size in enumerate(detail["pbb_wheel_sizes_m"]):
        border = detail["pbb_wheel_border_m"]
        c = Canvas(size + 2 * padding, size + 2 * padding)
        if index == 0:
            cx = cy = c.width / 2
            outer = [(cx + size / 2 * math.cos(i * math.tau / 256), cy + size / 2 * math.sin(i * math.tau / 256)) for i in range(256)]
            inner = [(cx + (size / 2 - border) * math.cos(i * math.tau / 256), cy + (size / 2 - border) * math.sin(i * math.tau / 256)) for i in range(256)]
            c.polygon(outer, colors["Red"]); c.polygon(inner, colors["White"])
            name, shape = f"PBB Wheel CAAM Circle {size:g}m", "圆形"
        else:
            c.rect(padding, padding, size, size, colors["Red"])
            c.rect(padding + border, padding + border, size - 2 * border, size - 2 * border, colors["White"])
            name, shape = f"PBB Wheel CAAM Square {size:g}m", "方形"
        add(name, 7820 + index, c, f"廊桥轮位 · CAAM · {shape} {size:g} m",
            f"白色轮位、红边 0.10 m，外径／外边长 {size:g} m。按轮组尺寸调整，外轮至标记边缘不超过 0.50 m；活动区另放。",
            f"White PBB wheel parking mark with a 0.10 m red border; {size:g} m outer diameter/side. "
            "Fit the wheel group so outer wheels are no more than 0.50 m from the marked edge. Movement area is separate.",
            "CAAM CAGM 1403 (2025) §12、图12-1；3/4m为可缩放包内预设，不代表所有廊桥轮组",
            {"kind": "pbb_wheel", "outer_m": [size, size], "border_m": border})

    def clip_rectangle(points, width, height):
        for axis, limit, sign in [(0, 0, 1), (0, width, -1), (1, 0, 1), (1, height, -1)]:
            output = []
            for previous, current in zip(points[-1:] + points[:-1], points):
                a, b = sign * (previous[axis] - limit) >= 0, sign * (current[axis] - limit) >= 0
                if a != b:
                    t = (limit - previous[axis]) / (current[axis] - previous[axis])
                    output.append(tuple(previous[k] + t * (current[k] - previous[k]) for k in (0, 1)))
                if b:
                    output.append(current)
            points = output
            if not points:
                break
        return points

    for index, (width, height) in enumerate(detail["no_parking_rectangles_m"]):
        hatch = spec["hatch_surface"]
        stroke, gap = hatch["width_m"], hatch["clear_gap_m"]
        c = Canvas(width + 2 * padding, height + 2 * padding, resolution=2048)
        frame(c, padding, padding, width, height, stroke, colors["Red"])
        iw, ih = width - 2 * stroke, height - 2 * stroke
        period = (stroke + gap) * math.sqrt(2)
        # Each coordinate moves in opposite directions, so x-y changes by
        # twice this offset. The resulting perpendicular full width is stroke.
        half_width = stroke / (2 * math.sqrt(2))
        reach = iw + ih
        for i in range(math.floor(-ih / period) - 1, math.ceil(iw / period) + 2):
            offset = i * period
            quad = [(-reach + half_width, -reach - offset - half_width),
                    (reach + half_width, reach - offset - half_width),
                    (reach - half_width, reach - offset + half_width),
                    (-reach - half_width, -reach - offset + half_width)]
            points = clip_rectangle(quad, iw, ih)
            if points:
                c.polygon([(x + padding + stroke, y + padding + stroke) for x, y in points], colors["Red"])
        add(f"No Parking Hatch CAAM Frame {width:g}x{height:g}m", 7830 + index, c,
            f"禁停斜线框 · CAAM · {width:g} × {height:g} m",
            f"透明红色禁停框，外框 {width:g} × {height:g} m、边框与斜线宽 0.10 m，45° 斜线垂直净距 0.75 m；一张贴花放置。",
            f"One transparent red no-parking decal: {width:g} x {height:g} m outer frame, "
            "0.10 m border and hatching; 45-degree stripes with 0.75 m perpendicular gaps.",
            "CAAM CAGM 1403 (2025) §11；复用已验证8500图样比例；矩形外尺寸为包内快捷模板",
            {"kind": "no_parking_frame", "outer_m": [width, height], "stroke_m": stroke,
             "perpendicular_period_m": stroke + gap, "clear_gap_m": gap, "angle_degrees": 45})

    for index, (width, height) in enumerate(detail["equipment_rectangles_m"]):
        c = Canvas(width + 2 * padding, height + 2 * padding)
        frame(c, padding, padding, width, height, 0.1, colors["White"])
        add(f"Equipment Parking CAAM {width:g}x{height:g}m", 7840 + index, c,
            f"设备停放框 · CAAM · {width:g} × {height:g} m",
            f"透明白色设备停放框，外框 {width:g} × {height:g} m、线宽 0.10 m。用于车辆／设备停车，按场地与设备尺寸布置。",
            f"Transparent white equipment parking outline, {width:g} x {height:g} m outer size, "
            "0.10 m stroke. Fit the site and equipment dimensions.",
            "CAAM CAGM 1403 (2025) §15、图15-1/15-2；外框尺寸为包内预设，语义区别于禁停区",
            {"kind": "equipment_frame", "outer_m": [width, height], "stroke_m": 0.1})

    p.output(ROOT / "docs/stand-presets.json", (json.dumps({"version": "0.6.6", "units": "metres",
             "orientation": "nose toward image top / closed boundary", "assets": records},
             ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
