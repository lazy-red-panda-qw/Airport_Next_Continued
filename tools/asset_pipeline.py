"""Deterministic airport artwork and EAI configuration. Python 3 + Pillow + numpy.

--bootstrap captures the unmodified 187-asset baseline and the author's glyphs.
--apply writes only changed bytes; --check generates in memory and checks the
entire output, identities, draw orders, priorities and physical paint bounds.
All geometry below is in metres, before rasterisation. SVG masters are kept
outside CustomAssets so EAI's timestamp hash does not include authoring files.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import string
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Airport Decal Pack Countinue" / "CustomAssets"
SPEC = json.loads((ROOT / "asset-specs.json").read_text(encoding="utf-8"))
BASELINE = ROOT / "SourceAssets" / "baseline-assets.json"
AUTHOR_SYMBOLS = string.ascii_uppercase + string.digits + "-"
SYMBOLS = AUTHOR_SYMBOLS + "."
COLORS = {k: tuple(v) for k, v in SPEC["palette"].items()}
N = 1024
AA = 2
PADDING = SPEC["decal_padding_m"]
TRADITIONAL = str.maketrans(json.loads((ROOT / "tools" / "zh-hant-map.json").read_text(encoding="utf-8")))


def menu_path(rel):
    """Use ExtraLib's existing categories; this only changes asset folders."""
    parts = rel.split("/")
    if parts[0] == "CustomDecals":
        parts[1] = "Alphabet" if parts[1] in ("Alphabet", "AssemblyCharacters") else "RoadMarkings"
    elif parts[0] == "CustomNetlanes":
        parts[1] = "RoadMarking"
    return "/".join(parts)


def player_description(rel, painted, period):
    """Player-facing descriptions contain dimensions, content and purpose."""
    name = Path(rel).name
    w,h = painted or (0,0)
    size_zh, size_en = f"{w:g} × {h:g} m", f"{w:g} × {h:g} m"
    if "/MarkingBackgrounds/" in rel:
        theme = next(t for t in ("White Red", "Location", "Direction", "Mandatory") if name.startswith(t))
        zh,en = {"Location":("黑底黄框","Black fill with a yellow border"),
                 "Direction":("黄底黑框","Yellow fill with a black border"),
                 "Mandatory":("纯红底","Solid red background"),
                 "White Red":("白底红框","White fill with a red border")}[theme]
        height = 2 if "2m" in name else 4
        if "Strip" in name:
            return (f"{zh}，宽 {w:g} m；搭配 {height} m 字高，长度沿线绘制。",
                    f"{en}, {w:g} m wide. Draw the length for {height} m lettering.")
        if "Cap" in name:
            return (f"{zh}端帽，{size_zh}；搭配同尺寸背景主体，旋转 180° 用于另一端。",
                    f"{en} end cap, {size_en}. Rotate 180 degrees for the other end of the matching strip.")
        return (f"{zh}，{size_zh}；搭配 {height} m 字高的固定矩形背景。",
                f"{en}, {size_en}. Fixed rectangular background for {height} m lettering.")
    if name.startswith("Runway Centerline"):
        return (f"白色跑道中线，宽 {w:g} m；实段 30 m、空段 30 m。",
                f"White runway centre line, {w:g} m wide; 30 m paint / 30 m gap.")
    if name.startswith("Runway Edge"):
        return (f"白色跑道边线，宽 {w:g} m；沿跑道边缘连续绘制。",
                f"White runway edge line, {w:g} m wide. Draw continuously along the runway edge.")
    if name.startswith("Threshold Half"):
        n=int(name.split()[2])
        return (f"白色跑道入口条纹，单侧 {n} 根，范围 {size_zh}；每根宽 1.8 m、长 30 m。",
                f"Half-threshold group of {n} white stripes, {size_en}; each stripe is 1.8 m wide and 30 m long.")
    if name.startswith("Aiming Point"):
        return (f"白色瞄准点单块，{size_zh}；在跑道两侧成对布置。",
                f"White aiming-point block, {size_en}. Place as a pair on both sides of the runway centre line.")
    if name.startswith("Touchdown Zone Coded"):
        n=int(name.split()[3])
        return (f"白色接地带标记，{n} 条，范围 {size_zh}；每条 1.8 × 22.5 m。",
                f"Coded touchdown-zone group of {n} white stripes, {size_en}; each stripe is 1.8 × 22.5 m.")
    exact = {
        "Threshold Stripe 180cm x30m": ("白色跑道入口条纹，1.8 × 30 m；用于组合入口条纹组。", "White threshold stripe, 1.8 × 30 m. Assemble into threshold groups."),
        "Touchdown Zone Basic 3x2250cm": ("白色基本式接地带单块，3 × 22.5 m；在跑道两侧成对布置。", "White basic touchdown-zone block, 3 × 22.5 m. Place in pairs on both sides of the runway centre line."),
        "Displaced Threshold Bar 180cm Module": ("白色内移入口横条，10 × 1.8 m；首尾拼接至跑道全宽。", "White displaced-threshold bar module, 10 × 1.8 m. Join end-to-end across the runway."),
        "Displaced Threshold Arrow 30m": ("白色内移入口箭头，长 30 m；用于跑道内移入口之前的中线。", "White displaced-threshold arrow, 30 m long. Place on the centre line before a displaced threshold."),
        "Prethreshold Chevron 30m": ("黄色 V 形标记，跨宽约 30 m、笔画宽 0.9 m；用于前入口非可用区域。", "Yellow chevron, approximately 30 m across with 0.9 m strokes. Marks unusable pavement before the threshold."),
        "Closed Runway X": (f"白色跑道关闭标记，外接范围 {size_zh}、笔画宽 1.8 m。", f"White runway closure cross, {size_en} overall, with 1.8 m strokes."),
        "Closed Taxiway X": (f"黄色滑行道关闭标记，外接范围 {size_zh}、笔画宽 1.5 m。", f"Yellow taxiway closure cross, {size_en} overall, with 1.5 m strokes."),
        "Calibration Grid 10m": ("10 × 10 m 校准网格，格距 1 m；用于测量贴花尺寸。", "10 × 10 m calibration grid with 1 m spacing. Measures decal dimensions."),
        "Calibration Ruler 20m": ("20 m 校准尺，刻度间距 1 m、每 5 m 一个长刻度；用于测量长度。", "20 m calibration ruler with 1 m ticks and major ticks every 5 m. Measures lengths."),
        "Stand Lead In 15cm": ("黄色实线，宽 0.15 m；用于机位引导线或黄色区域描边。", "Yellow solid line, 0.15 m wide. Use for aircraft-stand guidance or yellow outlines."),
        "Apron Safety Red 10cm": ("红色实线，宽 0.10 m；用于机坪安全边界或红色区域描边。", "Red solid line, 0.10 m wide. Use for apron safety boundaries or red outlines."),
    }
    if name in exact:
        return exact[name]
    if name.startswith("TaxiWay") or name.startswith("ILS") or name.startswith("Taxi Side"):
        light = "Light" in name or name in ("TaxiWay Stopline Enhanced", "TaxiWay Stopline", "ILS Critical Area Boundary")
        border_zh = "，带黑色对比边" if light else ""
        border_en = " with black contrast edging" if border_zh else ""
        if "Centerline Enhanced" in name:
            zh,en="增强滑行道中线，三条黄线各宽 0.15 m；两侧虚线实段 3 m、空段 1 m", "Enhanced taxiway centre line: three 0.15 m yellow lines; side dashes are 3 m paint / 1 m gap"
        elif name in ("TaxiWay Light Surface","TaxiWay Dark Surface"):
            zh,en="黄色滑行道中线，宽 0.15 m", "Yellow taxiway centre line, 0.15 m wide"
        elif name in ("TaxiWay Runway Holding Dark Surface","TaxiWay Stopline Enhanced"):
            zh,en="跑道等待线 A2，四条黄线各宽 0.30 m、净距 0.30 m；虚线实段和空段各 0.90 m", "A2 runway holding marking: four 0.30 m yellow lines with 0.30 m clear spacing; dashes and gaps are 0.90 m"
        elif name.startswith("ILS"):
            zh,en="ILS 等待线 B2，两条 0.30 m 黄线与双横档；重复周期 3.90 m", "B2 ILS holding marking: two 0.30 m yellow lines with paired cross-bars; 3.90 m repeat"
        elif "Intermediate" in name or name=="TaxiWay Stopline":
            zh,en="中间等待线，黄色虚线宽 0.30 m；实段和空段各 0.90 m", "Intermediate holding marking: 0.30 m yellow dashes; 0.90 m paint / 0.90 m gap"
        else:
            zh,en="黄色非承重铺装边界，两条实线各宽 0.15 m、净距 0.15 m", "Yellow non-load-bearing pavement boundary: two 0.15 m solid lines with 0.15 m clear spacing"
        return zh+border_zh+"。",en+border_en+"."
    raise ValueError(f"Missing player description: {rel}")


def json_bytes(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def png_bytes(im):
    out = io.BytesIO()
    im.save(out, format="PNG", compress_level=6)
    return out.getvalue()


def glyph_name(s):
    return "Dash Mark" if s == "-" else ("Num " if s.isdigit() else "Mark ") + s


def bootstrap():
    if BASELINE.exists():
        raise ValueError("Baseline already exists; refusing to overwrite source artwork.")
    rows = []
    for path in sorted(ASSETS.rglob("decal.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows.append({"path": path.parent.relative_to(ASSETS).as_posix(),
                     "draw_order": data["Float"]["_DrawOrder"], "decal": data})
    if len(rows) != 187:
        raise ValueError(f"Expected the original 187 assets, got {len(rows)}.")
    for s in AUTHOR_SYMBOLS:
        source = ASSETS / "CustomDecals" / "Alphabet" / glyph_name(s) / "_BaseColorMap.png"
        dest = ROOT / "SourceAssets" / "Glyphs" / ("dash.png" if s == "-" else s + ".png")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_bytes(json_bytes({"git_commit": "7cf18e12ead9e64ea901eec36520b5a4e9f30be1", "assets": rows}))
    print("Captured 187 original configurations and 37 author glyphs.")


class Canvas:
    """Raster and SVG use the same metre coordinates; no external font needed."""
    def __init__(self, width, height):
        self.width, self.height = float(width), float(height)
        self.im = Image.new("RGBA", (N * AA, N * AA))
        self.draw = ImageDraw.Draw(self.im)
        self.svg = []

    def point(self, x, y):
        return x * N * AA / self.width, y * N * AA / self.height

    def polygon(self, points, color):
        color = tuple(color)
        self.draw.polygon([self.point(*p) for p in points], fill=color + (255,) if len(color) == 3 else color)
        if len(color) == 4 and color[3] == 0:
            # Holes use an SVG mask supplied by svg_bytes().
            fill = "black"
            kind = "hole"
        else:
            fill = "#%02x%02x%02x" % color[:3]
            kind = "paint"
        pts = " ".join(f"{x:.8g},{y:.8g}" for x, y in points)
        self.svg.append((kind, f'<polygon points="{pts}" fill="{fill}"/>'))

    def rect(self, x, y, w, h, color):
        self.polygon([(x, y), (x+w, y), (x+w, y+h), (x, y+h)], color)

    def stroke(self, p1, p2, width, color):
        dx, dy = p2[0]-p1[0], p2[1]-p1[1]
        length = math.hypot(dx, dy)
        nx, ny = -dy/length*width/2, dx/length*width/2
        self.polygon([(p1[0]+nx,p1[1]+ny), (p2[0]+nx,p2[1]+ny),
                      (p2[0]-nx,p2[1]-ny), (p1[0]-nx,p1[1]-ny)], color)

    def finish(self):
        return self.im.resize((N, N), Image.Resampling.LANCZOS)

    def svg_bytes(self):
        holes = [s for kind,s in self.svg if kind == "hole"]
        mask = '' if not holes else ('<defs><mask id="cut"><rect width="100%" height="100%" fill="white"/>' + ''.join(holes) + '</mask></defs>')
        group = '<g>' if not holes else '<g mask="url(#cut)">'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width*100:.8g}" height="{self.height*100:.8g}" '
                f'viewBox="0 0 {self.width:.8g} {self.height:.8g}"><title>Geometry coordinates in metres</title>{mask}{group}' +
                ''.join(s for kind,s in self.svg if kind == "paint") + '</g></svg>\n').encode()


def paint_box(im):
    return im.getchannel("A").point(lambda a: 255 if a >= 128 else 0).getbbox()


def load_glyph(s):
    path = ROOT / "SourceAssets" / "Glyphs" / ("dash.png" if s == "-" else s + ".png")
    im = Image.open(path).convert("RGBA")
    return im.crop(paint_box(im)).getchannel("A")


def decal_config(width, height, priority, order=42, original=None):
    data = json.loads(json.dumps(original)) if original else {
        "Float": {"_Metallic": 0, "_Smoothness": 0, "colossal_DecalLayerMask": 7,
                  "_NormalOpacity": 0, "_MetallicAlphaSource": 0,
                  "_MetallicOpacity": 0, "_NormalAlphaSource": 0, "_DrawOrder": order},
        "Vector": {"colossal_TextureArea": {"x": 0, "y": 0, "z": 1, "w": 1}}}
    data["Float"].pop("UiPriority", None)
    data["Float"]["_DrawOrder"] = order
    data["UiPriority"] = priority
    data["Vector"]["colossal_MeshSize"] = {"x": round(width, 9), "y": 1,
                                           "z": round(height, 9), "w": 0}
    return data


def curve_config(priority, period):
    return {"UiPriority": priority,
            "curveProperties": {"TilingCount": 0, "SmoothingDistance": 0,
                                "OverrideLength": period, "GeometryTiling": False,
                                "StraightTiling": False, "SubFlow": False, "InvertCurve": False},
            "utilityLane": None, "prefabIdentifierInfos": []}


class Pipeline:
    def __init__(self, check):
        self.check = check
        self.changed = []
        self.rows = []
        self.baseline = {a["path"]: a for a in json.loads(BASELINE.read_text(encoding="utf-8"))["assets"]}
        self.seen = set()
        self.locales = {"en-US": {}, "zh-HANS": {}, "zh-HANT": {}}
        self.contacts = []

    def output(self, path, content):
        if path.exists() and path.read_bytes() == content:
            return
        self.changed.append(path.relative_to(ROOT).as_posix())
        if not self.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def asset(self, rel, priority, width, height, title, note, ref, canvas=None,
              image=None, period=None, painted=None, draw_order=None, note_en=None):
        requested_rel = rel
        rel = SPEC["legacy_asset_renames"].get(rel, rel)
        if requested_rel != rel and requested_rel in self.baseline:
            raise ValueError(f"Cannot rename an original asset: {requested_rel}")
        if "." in Path(rel).name:
            raise ValueError(f"Legacy EAI misreads dots in asset names: {rel}")
        if priority in SPEC["reserved_removed_priorities"]:
            raise ValueError(f"Removed UiPriority remains reserved: {priority}: {rel}")
        if priority in self.seen:
            raise ValueError(f"Duplicate UiPriority {priority}: {rel}")
        self.seen.add(priority)
        if not 1000 <= priority < 10000:
            raise ValueError(f"Priority out of reserved ranges: {rel}")
        source_rel = rel
        rel = menu_path(rel)
        folder = ASSETS / rel
        old = self.baseline.get(source_rel)
        order = SPEC["draw_order_overrides"].get(source_rel,
            old["draw_order"] if old else (42 if draw_order is None else draw_order))
        is_lane = rel.startswith("CustomNetlanes/")
        data = decal_config(width, height, priority, order, old["decal"] if old else None)
        # Unpublished pack: use the final identities without migration aliases.
        data.pop("prefabIdentifierInfos", None)
        if is_lane:
            data.pop("UiPriority")
            if period is None:
                raise ValueError(f"Missing explicit tile length: {rel}")
            lane_data = curve_config(priority, period)
            self.output(folder / "netlane.json", json_bytes(lane_data))
        self.output(folder / "decal.json", json_bytes(data))
        if canvas is not None:
            image = canvas.finish()
            self.output(ROOT / "SourceAssets" / "Vectors" / (rel + ".svg"), canvas.svg_bytes())
        if image is None:
            image = Image.open(folder / "_BaseColorMap.png").convert("RGBA")
        self.output(folder / "_BaseColorMap.png", png_bytes(image))
        self.output(folder / "icon.png", png_bytes(image.resize((128,128),Image.Resampling.LANCZOS)))
        box = paint_box(image)
        if box is None:
            raise ValueError(f"Empty texture: {rel}")
        actual = ((box[2]-box[0]) / image.width * width, (box[3]-box[1]) / image.height * height)
        if painted:
            for measured,expected,mesh in zip(actual,painted,(width,height)):
                if abs(measured-expected) > mesh / N * 2.1:
                    raise ValueError(f"Painted bounds mismatch: {rel}: {actual}, expected {painted}")
        cat, name = folder.parent.name, folder.name
        full = f'{SPEC["mod_name"]} {cat} {name} ' + ("NetLane" if is_lane else "Decal")
        if note_en is None:
            note,note_en = player_description(source_rel, painted or actual, period)
        self.record(rel,priority,width,height,actual,period,order,title,note,ref,full,
                    "NetLaneGeometryPrefab" if is_lane else "StaticObjectPrefab", not old,
                    source_rel=source_rel,note_en=note_en)
        self.contacts.append((priority,title,image.resize((128,128),Image.Resampling.LANCZOS)))

    def record(self,rel,priority,width,height,painted,period,order,title,note,ref,full,kind,new,
               source_rel=None,note_en=None):
        self.rows.append({"UiPriority":priority,"path":rel,"source_path":source_rel or rel,"type":kind,"new":new,
                          "mesh_x_m":round(width,6) if width else None,
                          "mesh_z_m":round(height,6) if height else None,
                          "paint_x_m":round(painted[0],6) if painted else None,
                          "paint_z_m":round(painted[1],6) if painted else None,
                          "tile_period_m":period,"draw_order":order,"title":title,
                          "reference":ref,"notes":note,"prefab_name":full})
        english = Path(rel).name
        if note_en and "runway character" not in note_en and any(note_en.startswith(color+" ") for color in ("White","Black","Yellow")):
            m=re.search(r"character ([A-Z0-9]),",note_en)
            letter=m.group(1) if m else "hyphen" if "hyphen," in note_en else "decimal point" if "decimal point," in note_en else None
            if letter is not None:
                english=f"{note_en.split()[0]} {letter} · {title.rsplit(' · ',1)[1]}"
        if english.startswith("Aiming Point"):
            english=f"Aiming point · {painted[0]:.2f} × {painted[1]:.2f} m"
        if re.fullmatch(r"Runway [0-9LCR] (Small|Medium|Large)",english):
            english=title.replace("跑道 ","Runway ",1)
        if "Background Cap" in english:
            english = english.replace("Background Cap Left", "Background End Cap")
        for lang, values in self.locales.items():
            values[f"Assets.NAME[{full}]"] = english if lang == "en-US" else title.translate(TRADITIONAL) if lang == "zh-HANT" else title
            values[f"Assets.DESCRIPTION[{full}]"] = note_en if lang == "en-US" else note.translate(TRADITIONAL) if lang == "zh-HANT" else note

    def character(self,s,height,rel,priority,title,background=None,foreground="White",margin=0,ref="造景字符预设；保留作者字形"):
        mask = Image.new("L",(1,1),255) if s == "." else load_glyph(s)
        # The dash shares the author's H cap-height; its short stroke is not
        # itself a 2/4 m capital. Other glyphs retain the tested dimensions.
        metric_height = load_glyph("H").height if s == "-" else mask.height
        gw, gh = (height*SPEC["decimal_point_ratio"],)*2 if s == "." else (mask.width/metric_height*height, mask.height/metric_height*height)
        cell_height = height if background else gh
        width, length = gw+margin*2+PADDING*2, cell_height+margin*2+PADDING*2
        canvas = Canvas(width,length)
        if background:
            canvas.rect(PADDING,PADDING,gw+margin*2,cell_height+margin*2,COLORS[background])
        pw, ph = max(1,round(gw/width*N*AA)),max(1,round(gh/length*N*AA))
        stamp = Image.new("RGBA",(pw,ph),COLORS[foreground]+(0,))
        stamp.putalpha(mask.resize((pw,ph),Image.Resampling.LANCZOS))
        canvas.im.alpha_composite(stamp,(round((PADDING+margin)/width*N*AA),
            round((PADDING+margin+(cell_height-gh)/2)/length*N*AA)))
        color={"White":"白色","Black":"黑色","Yellow":"黄色"}[foreground]
        content="连字符" if s=="-" else "小数点" if s=="." else f"字符 {s}"
        note=f"{color}{content}，涂漆范围 {gw:.3f} × {gh:.3f} m；配套 {height:g} m 字高，透明底，可与独立背景组合。"
        note_en=f"{foreground} {'hyphen' if s=='-' else 'decimal point' if s=='.' else 'character '+s}, {gw:.3f} × {gh:.3f} m paint bounds. For {height:g} m lettering; transparent background for separate assembly."
        self.asset(rel,priority,width,length,title,note,ref,image=canvas.finish(),
                   painted=(gw+margin*2,cell_height+margin*2),note_en=note_en)

    def surface(self,name,priority,color,pavement=False):
        if priority in SPEC["reserved_removed_priorities"]:
            raise ValueError(f"Removed Surface UiPriority remains reserved: {priority}: {name}")
        if priority in self.seen or not 1000 <= priority < 10000:
            raise ValueError(f"Duplicate or invalid Surface UiPriority {priority}: {name}")
        self.seen.add(priority)
        rel=f"Surfaces/Pavement/{name}"
        folder=ASSETS/rel
        fade = SPEC["surface_edge_defaults"]["fade"]
        noise_range = SPEC["surface_edge_defaults"]["noise"]
        if tuple(noise_range) == (0,0):
            raise ValueError("EdgeNoise=(0,0) made Surface invisible in the A/B/C/D game test.")
        rng=np.random.default_rng(20261001+priority)
        rgb=np.empty((512,512,4),dtype=np.uint8)
        noise=rng.normal(0,2.8 if pavement else 0,(512,512,1))
        rgb[:,:,:3]=np.clip(np.array(color)[None,None,:]+noise,0,255).astype(np.uint8)
        rgb[:,:,3]=255
        image=Image.fromarray(rgb)
        self.output(folder/"_BaseColorMap.png",png_bytes(image))
        self.output(folder/"icon.png",png_bytes(image.resize((128,128),Image.Resampling.LANCZOS)))
        self.output(folder/"Prefab.json",json_bytes({"Components":{
            "Game.Prefabs.UIObject":{"m_Priority":priority,"m_IsDebugObject":False},
            "Game.Prefabs.RenderedArea":{"m_Roundness":0}}}))
        self.output(folder/"Material.json",json_bytes({"Float":{
            "_DrawOrder":35 if pavement else 38,"colossal_DecalLayerMask":7,
            "_Metallic":0,"_Smoothness":0.15 if pavement else 0,
            "_NormalOpacity":0,"_MetallicOpacity":0,"colossal_UVScale":0.2,
            "colossal_EdgeNormal":0},"Vector":{
                "_BaseColor":{"x":1,"y":1,"z":1,"w":1},
                "colossal_EdgeFadeRange":{"x":fade[0],"y":fade[1],"z":0,"w":0},
                "colossal_EdgeNoise":{"x":noise_range[0],"y":noise_range[1],"z":0,"w":0}}}))
        full=f'{SPEC["mod_name"]} Pavement {name} Surface'
        title={"Airport Asphalt":"机场沥青表面","Airport Concrete":"机场混凝土表面",
               "Paint White":"白色涂漆表面","Paint Yellow":"黄色涂漆表面",
               "Paint Red":"红色涂漆表面","Paint Black":"黑色涂漆表面"}[name]
        note="面积与形状由玩家绘制；用于机场道面铺装。" if pavement else "面积与形状由玩家绘制；用于标记背景或涂漆区域，可搭配独立描边和字符。"
        note_en="Draw the area and shape for airport pavement." if pavement else "Draw the area and shape for marking backgrounds or painted areas. Combine with separate outlines and characters."
        self.record(rel,priority,None,None,None,None,35 if pavement else 38,title,
                    note,
                    "EAI 1.7.5/1.7.6 新版 Surfaces 导入器",full,"SurfacePrefab",True,note_en=note_en)
        self.contacts.append((priority,title,image.resize((128,128),Image.Resampling.LANCZOS)))

    def finish(self):
        rows=sorted(self.rows,key=lambda x:x["UiPriority"])
        missing=set(self.baseline)-{r["source_path"] for r in rows}
        allowed_removed = set(self.baseline) & set(SPEC["removed_assets"])
        if missing != allowed_removed:
            raise ValueError(f"Unexpected original identity removal: {sorted(missing ^ allowed_removed)}")
        if {r["source_path"] for r in rows} & set(SPEC["removed_assets"]):
            raise ValueError("Removed assets must not be generated or deployed.")
        actual = {f.parent.relative_to(ASSETS).as_posix() for root in ("CustomDecals", "CustomNetlanes")
                  for f in (ASSETS/root).rglob("decal.json")}
        actual.update(f.parent.relative_to(ASSETS).as_posix() for f in (ASSETS/"Surfaces").rglob("Prefab.json"))
        expected = {r["path"] for r in rows}
        if actual != expected:
            raise ValueError(f"Asset folder set mismatch; stale={sorted(actual-expected)}, missing={sorted(expected-actual)}")
        csvout=io.StringIO(newline="")
        writer=csv.DictWriter(csvout,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
        self.output(ROOT/"docs"/"asset-catalog.csv",csvout.getvalue().encode("utf-8-sig"))
        self.output(ROOT/"docs"/"asset-catalog.json",json_bytes(rows))
        for lang,data in self.locales.items():
            self.output(ASSETS/"Localization"/(lang+".json"),json_bytes(data))
        # Representative contact sheet, instead of hundreds of unreadable thumbnails.
        selected=[r for r in sorted(self.contacts) if r[0] in [1000,1001,1002,1370,2010,2011,2012,2750,4000,4010,4040,4060,4090,4100,4110,4120]
                  or 5000<=r[0]<6100 or r[0] in [7000,7001,7180,7181,7400,8100,8110,8120,8130,8140,8150,9900,9910]
                  or 8200<=r[0]<8430 or 7300<=r[0]<7330]
        from PIL import ImageFont
        font=ImageFont.load_default()
        thumb=Image.new("RGB",(8*160,math.ceil(len(selected)/8)*170),(48,48,48))
        draw=ImageDraw.Draw(thumb)
        by_priority={r["UiPriority"]:r for r in rows}
        for i,(priority,title,im) in enumerate(selected):
            x=(i%8)*160+16;y=(i//8)*170+8
            row=by_priority[priority]
            w,h=row["mesh_x_m"],row["mesh_z_m"]
            if w and h:
                scale=128/max(w,h)
                im=im.resize((max(1,round(w*scale)),max(1,round(h*scale))),Image.Resampling.LANCZOS)
            thumb.paste(im,(x+(128-im.width)//2,y+(128-im.height)//2),im)
            draw.text((x,y+133),str(priority),fill="white",font=font)
        self.output(ROOT/"docs"/"asset-preview.png",png_bytes(thumb))
        print(f'{len(rows)} assets ({sum(r["new"] for r in rows)} new), '
              f'{len(self.baseline)-len(missing)} original sources retained, {len(missing)} explicitly removed; '
              f'UiPriority {min(self.seen)}..{max(self.seen)}, unique; {len(self.changed)} changed outputs.')
        if self.check and self.changed:
            print("Outputs need regeneration:\n"+"\n".join(self.changed[:30]),file=sys.stderr)
            return 1
        return 0


def stamp_mask(mask, width, height, color):
    canvas = Canvas(width+2*PADDING, height+2*PADDING)
    pw,ph = round(width/canvas.width*N*AA),round(height/canvas.height*N*AA)
    stamp = Image.new("RGBA",(pw,ph),COLORS[color]+(0,))
    stamp.putalpha(mask.resize((pw,ph),Image.Resampling.LANCZOS))
    canvas.im.alpha_composite(stamp,(round(PADDING/canvas.width*N*AA),round(PADDING/canvas.height*N*AA)))
    # Source-font antialiasing can span multiple output pixels after scaling.
    # Size the projection from the final visible bounds, preserving the bitmap.
    box=paint_box(canvas.finish())
    canvas.width=width*N/(box[2]-box[0])
    canvas.height=height*N/(box[3]-box[1])
    return canvas


def generate_runway_characters(p):
    # Keep the author's original glyph contours; normalize the outer paint bounds.
    for i,symbol in enumerate("0123456789LCR"):
        original=Image.open(ROOT/"SourceAssets"/"RunwayGlyphs"/(symbol+".png")).convert("RGBA")
        mask=original.crop(paint_box(original)).getchannel("A")
        width={"1":1.1,"4":3.9,"7":3.5}.get(symbol,3)
        height=9.5 if symbol in "69" else 9
        for offset,(size,scale) in enumerate(SPEC["runway_scales"].items()):
            w,h=width*scale,height*scale
            canvas=stamp_mask(mask,w,h,"White")
            p.asset(f"CustomDecals/RoadMarkings/Runway {symbol} {size}",4000+i*10+offset,
                    canvas.width,canvas.height,f"跑道 {symbol} · {w:g} × {h:g} m",
                    f"白色跑道字符 {symbol}，涂漆范围 {w:g} × {h:g} m；用于组合跑道编号。",
                    "作者 ICAO 跑道字体母版；Annex 14 图 5-3 外接尺寸；放大档为包内预设",
                    image=canvas.finish(),painted=(w,h),
                    note_en=f"White runway character {symbol}, {w:g} × {h:g} m paint bounds. Assemble into runway designations.")


def generate_characters(p):
    for i,symbol in enumerate(SYMBOLS):
        for color in ("White","Black","Yellow"):
            for offset,height in enumerate(SPEC["character_heights_m"]):
                if color=="White":
                    name=(f"Decimal Point {height}m" if symbol=="." else
                          glyph_name(symbol)+(" Small" if height==2 else "" if height==4 else " 1m"))
                    rel=f"CustomDecals/Alphabet/{name}"
                    priority=1000+i*10+offset
                else:
                    name="Point" if symbol=="." else "Dash" if symbol=="-" else symbol
                    rel=f"CustomDecals/AssemblyCharacters/{color} {name} {height}m"
                    priority=2000+i*20+(10 if color=="Yellow" else 0)+offset
                zh={"White":"白","Black":"黑","Yellow":"黄"}[color]
                content="小数点" if symbol=="." else "连字符" if symbol=="-" else symbol
                p.character(symbol,height,rel,priority,f"{zh}字 {content} · {height} m",foreground=color,
                            ref="作者 ICAO 通用字体母版" if symbol!="." else "包内小数点组件，边长为配套字高的 0.1 倍")


def generate_arrows(p):
    original=Image.open(ROOT/"SourceAssets"/"Glyphs"/"arrow.png").convert("RGBA")
    mask=original.crop(paint_box(original)).getchannel("A")
    for color_index,color in enumerate(("Black","Yellow","White")):
        for offset,height in enumerate(SPEC["character_heights_m"]):
            w=mask.width/mask.height*height
            canvas=stamp_mask(mask,w,height,color)
            rel="CustomDecals/RoadMarkings/Arrow Straight" if color=="Black" and height==4 else f"CustomDecals/RoadMarkings/Arrow {color} {height}m"
            zh={"Black":"黑色","Yellow":"黄色","White":"白色"}[color]
            p.asset(rel,7300+color_index*10+offset,canvas.width,canvas.height,f"{zh}方向箭头 · {height} m",
                    f"{zh}方向箭头，长 {height} m、宽 {w:.3f} m；用于组合方向或信息标记。",
                    "作者原始箭头；1/2/4 m 为包内组合尺寸预设",image=canvas.finish(),painted=(w,height),draw_order=42,
                    note_en=f"{color} direction arrow, {height} m long and {w:.3f} m wide. Assemble into direction or information markings.")


def generate_backgrounds(p):
    """Repeat only the long sides; terminal borders belong to separate caps."""
    for theme_index,(name,title,fill,edge) in enumerate([
        ("Location", "位置背景 · 黑底黄框", "Black", "Yellow"),
        ("Direction", "方向背景 · 黄底黑框", "Yellow", "Black"),
        ("Mandatory", "强制背景 · 红底", "Red", None),
        ("White Red", "通用背景 · 白底红框", "White", "Red"),
    ]):
        for height_index,height in enumerate((2,4)):
            priority = 8200+theme_index*40+height_index*10
            margin = SPEC["sign_background_margin_m"]
            border = SPEC["background_border_m"] if edge else 0
            inner = height+2*margin
            outer = inner+2*border
            order = SPEC["background_draw_order"]
            purpose = ("红底白字强制标记的背景；文字四周至少 0.5 m 留白。" if name == "Mandatory"
                       else "白底红框保留宽框外观，搭配黑字；不是红底白字强制标记。" if name == "White Red"
                       else "与对应透明底黄字/黑字组合；外框笔画 0.15 m 为包内预设。")
            note = (f"配套字高 {height} m，内区高 {inner:g} m，整体宽 {outer:g} m。"+purpose
                    +"沿长度绘制；宽度固定。"
                    +("主体不包含端边，同一端帽旋转 180° 用于另一端。" if edge else "纯红底主体无需端帽；长度需包含文字两端留白。")
                    +"背景层级 41、字符 42；第二轮游戏测试确认铺底方案可用。")
            ref = "ICAO 5.2.16/5.2.17 的颜色与留白；边框/端帽/长度为造景预设"
            c=Canvas(outer+2*PADDING,9)
            c.rect(PADDING,0,outer,9,COLORS[edge or fill])
            c.rect(PADDING+border,0,inner,9,COLORS[fill])
            p.asset(f"CustomNetlanes/MarkingBackgrounds/{name} Background Strip {height}m",priority,
                    c.width,c.height,f"{title} · {height} m 字高 · 拉线主体",note,ref,
                    canvas=c,period=9,painted=(outer,9),draw_order=order)
            cap_depth=margin+border
            if edge:
                c=Canvas(outer+2*PADDING,cap_depth+2*PADDING)
                c.rect(PADDING,PADDING,outer,cap_depth,COLORS[edge or fill])
                c.rect(PADDING+border,PADDING+border,inner,cap_depth-border,COLORS[fill])
                p.asset(f"CustomDecals/MarkingBackgrounds/{name} Background Cap Left {height}m",priority+1,
                        c.width,c.height,f"{title} · {height} m 字高 · 通用端帽（可旋转）",
                        note+"端帽内缘对齐主体端点，可少量重叠防止接缝。",ref,
                        canvas=c,painted=(outer,cap_depth),draw_order=order)
            length=SPEC["background_wide_lengths_m"][str(height)]
            c=Canvas(length+2*PADDING,outer+2*PADDING)
            c.rect(PADDING,PADDING,length,outer,COLORS[edge or fill])
            c.rect(PADDING+border,PADDING+border,length-2*border,inner,COLORS[fill])
            p.asset(f"CustomDecals/MarkingBackgrounds/{name} Background Wide {height}m",priority+3,
                    c.width,c.height,f"{title} · {height} m 字高 · {length:g} m 宽幅贴花",
                    note+f"固定长度 {length:g} m，保留宽框铺底形式；不是标准规定的固定长度。",ref,
                    canvas=c,painted=(length,outer),draw_order=order)


def generate(p):
    generate_characters(p)
    generate_runway_characters(p)
    generate_backgrounds(p)
    generate_arrows(p)

    # Yellow taxiway patterns. Both dark and light pavement versions share geometry.
    for role,base in [("center",6000),("enhanced",6010),("hold",6020),("ils",6040),("intermediate",6060),("edge",6070)]:
        for light in (False,True):
            yellow=COLORS["Yellow"]; black=COLORS["Black"]; b=.075 if light else 0
            if role=="center":extent=.15;period=9
            elif role=="enhanced":extent=.75;period=4
            elif role in ("hold","ils"):extent=2.1;period=1.8 if role=="hold" else 3.9
            elif role=="intermediate":extent=.3;period=1.8
            else:extent=.45;period=9
            c=Canvas(extent+b*2+.3,period);mid=c.width/2
            def line(x,width,start=0,length=None):
                length=period if length is None else length
                if light:c.rect(mid+x-width/2-b,start,width+b*2,length,black)
                c.rect(mid+x-width/2,start,width,length,yellow)
            if role=="center":
                line(0,.15);name="TaxiWay Light Surface" if light else "TaxiWay Dark Surface"
                title="滑行道中线";note="黄色中线 0.15 m；亮铺装版两侧各 0.075 m 黑色对比边。";ref="ICAO 5.2.8.7"
            elif role=="enhanced":
                line(0,.15)
                for x in (-.3,.3):
                    if light:c.rect(mid+x-.075-b,0,.15+2*b,period,black)
                    c.rect(mid+x-.075,0,.15,3,yellow)
                name=f'TaxiWay Centerline Enhanced {"Light" if light else "Dark"} Surface'
                title="增强滑行道中线";note="中线与两侧虚线均宽 0.15 m，净距 0.15 m；虚线 3 m / 间隔 1 m。由等待线起绘制至约 47 m 处结束。";ref="ICAO 5.2.8，图 5-7"
            elif role=="hold":
                for x in (-.9,-.3):line(x,.3)
                for x in (.3,.9):
                    if light:c.rect(mid+x-.15-b,0,.3+2*b,period,black)
                    c.rect(mid+x-.15,0,.3,.9,yellow)
                name="TaxiWay Stopline Enhanced" if light else "TaxiWay Runway Holding Dark Surface"
                title="跑道等待线 A2";note="四条黄线各宽 0.30 m，净距 0.30 m；虚线长/空各 0.90 m。实线朝等待侧；本 NetLane 沿等待线横向绘制。";ref="ICAO 5.2.10，图 5-8 A2（2026-11-26 起生效）"
            elif role=="ils":
                for x in (-.9,.9):line(x,.3)
                for z in (0,.6):
                    if light:c.rect(mid-1.05-b,z,2.1+2*b,.3,black)
                    c.rect(mid-1.05,z,2.1,.3,yellow)
                name="ILS Critical Area Boundary" if light else "ILS Critical Area Boundary Dark Surface"
                title="ILS 等待线 B2";note="纵向两条黄线各宽 0.30 m、净距 1.50 m；双横档各 0.30 m、档间 0.30 m，双档组间空 3 m；周期 3.90 m。";ref="ICAO 5.2.10，图 5-8 B2（2026-11-26 起生效）"
            elif role=="intermediate":
                if light:c.rect(mid-.15-b,0,.3+2*b,period,black)
                c.rect(mid-.15,0,.3,.9,yellow)
                name="TaxiWay Stopline" if light else "TaxiWay Intermediate Holding Dark Surface"
                title="中间等待线";note="单条黄虚线宽 0.30 m，实段/空段均 0.90 m；不是跑道入口等待线。";ref="ICAO 5.2.11，图 5-6"
            else:
                for x in (-.15,.15):line(x,.15)
                name=f'Taxi Side Stripe {"Light" if light else "Dark"} Surface'
                title="非承重铺装边界双线";note="两条黄色实线各 0.15 m，净距 0.15 m。沿承重铺装边缘绘制。";ref="ICAO 7.2.3"
            p.asset(f"CustomNetlanes/RoadMarking/{name}",base+int(light),c.width,c.height,title+(" · 带黑边" if light else " · 无黑边"),
                    note,ref,canvas=c,period=period)

    def block(name,priority,w,h,note,ref,category="RunwayMarkings"):
        c=Canvas(w+PADDING*2,h+PADDING*2);c.rect(PADDING,PADDING,w,h,COLORS["White"])
        label="瞄准点" if name.startswith("Aiming Point") else "入口单条纹" if name.startswith("Threshold Stripe") else "基本式接地带" if name.startswith("Touchdown Zone Basic") else "内移入口横条"
        p.asset(f"CustomDecals/{category}/{name}",priority,c.width,c.height,f"{label} · {w:g} × {h:g} m",note,ref,canvas=c,painted=(w,h))
    block("Threshold Stripe 1.8x30m",5000,1.8,30,"入口条纹单根。起点距入口 6 m；普通条纹净距约 1.8 m，中心净距 3.6 m；总条纹数随跑道宽度选择。","ICAO 5.2.4")
    for i,n in enumerate((2,3,4,6,8)):
        w=n*1.8+(n-1)*1.8;c=Canvas(w+.3,30+.3)
        for j in range(n):c.rect(.15+j*3.6,.15,1.8,30,COLORS["White"])
        p.asset(f"CustomDecals/RunwayMarkings/Threshold Half {n} Stripes",5010+i,c.width,c.height,f"入口条纹 · 单侧 {n} 根",
                "单侧条纹组；两组间须另留 3.6 m 中央净距。18/23/30/45/60 m 跑道分别需总计 4/6/8/12/16 根。","ICAO 5.2.4",canvas=c,painted=(w,30))
    for i,width in enumerate((.3,.45,.9)):
        c=Canvas(width+.3,60);c.rect(.15,0,width,30,COLORS["White"])
        p.asset(f"CustomNetlanes/RunwayMarkings/Runway Centerline {width:g}m",5100+i,c.width,c.height,f"跑道中线 · {width:g} m",
                "白虚线 30 m / 间隔 30 m，周期 60 m。宽度按跑道仪表类别/代码选用。","ICAO 5.2.3",canvas=c,period=60,painted=(width,30))
    for i,(w,h,offset,gap,label) in enumerate([(4,30,150,6,"LDA under 800m"),(6,30,250,9,"LDA 800-1200m"),(6,45,300,18,"LDA 1200-2400m"),(10,60,400,22.5,"Large preset")]):
        block(f"Aiming Point {label}",5204 if label=="Large preset" else 5200+i,w,h,
              f"单侧瞄准点块 {w} × {h} m；两块内缘距 {gap} m，起点距入口 {offset} m。",
              "ICAO 表 5-1；6×45 m 共用模块按 LDA 分别在 300/400 m 处放置")
    block("Touchdown Zone Basic 3x22.5m",5300,3,22.5,"基本式接地带单块；两侧成对布置，纵向站距 150 m；瞄准点前后 50 m 内应省略相冲突的站。","ICAO 5.2.6")
    for i,n in enumerate((1,2,3)):
        w=1.8*n+1.5*(n-1);c=Canvas(w+.3,22.5+.3)
        for j in range(n):c.rect(.15+j*3.3,.15,1.8,22.5,COLORS["White"])
        p.asset(f"CustomDecals/RunwayMarkings/Touchdown Zone Coded {n} Stripes",5310+i,c.width,c.height,f"接地带编码式 · {n} 条",
                "每条 1.8 × 22.5 m、净距 1.5 m；选择正确组数并在跑道两侧成对摆放。","ICAO 5.2.6",canvas=c,painted=(w,22.5))
    for i,width in enumerate((.45,.9)):
        c=Canvas(width+.3,9);c.rect(.15,0,width,9,COLORS["White"])
        p.asset(f"CustomNetlanes/RunwayMarkings/Runway Edge {width:g}m",5400+i,c.width,c.height,f"跑道边线 · {width:g} m",
                "跑道宽度不少于 30 m 时边线至少宽 0.9 m；较窄跑道至少宽 0.45 m。","ICAO 5.2.7",canvas=c,period=9,painted=(width,9))
    block("Displaced Threshold Bar 1.8m Module",5500,10,1.8,"1.8 m 厚内移入口横线；此 10 m 宽模块可首尾拼接到跑道全宽。","ICAO 图 5-4")
    # Displaced arrow head: h=10 m minimum, width h/3, stroke h/12.
    head_half_width=10/6
    head_extra=(10/12)/2*10/math.hypot(10,head_half_width)
    c=Canvas(10/3+head_extra*2+.3,30+.3);cx=c.width/2;y=.15
    # Butt-ended, symmetric strokes; head length and spread follow Figure 5-4.
    for tip in ((cx-10/6,y+10),(cx+10/6,y+10)):
        c.stroke((cx,y+0.42),tip,10/12,COLORS["White"])
    c.rect(cx-.225,y+10,.45,20,COLORS["White"])
    p.asset("CustomDecals/RunwayMarkings/Displaced Threshold Arrow 30m",5510,c.width,c.height,"内移入口箭头 · 30 m",
            "30 m 长度预设、箭头段约 10 m、箭头张角宽 h/3、笔画 h/12。细杆 0.45 m；与 0.9 m 跑道中线搭配。沿中线每 50 m 设一箭头；另按图 5-4 放置入口横线。斜端与接缝待游戏/图样复核。",
            "ICAO 图 5-4；杆宽/段长为包内预设",canvas=c)
    # Non-operational pre-threshold chevron; 0.9 m stripes at 45 degrees.
    end_extra=.9/2/math.sqrt(2)
    c=Canvas(30+end_extra*2+.3,15+end_extra*2+.3)
    for end in ((.15+end_extra,.15+end_extra+15),(.15+end_extra+30,.15+end_extra+15)):
        c.stroke((.15+end_extra+15,.15+end_extra),end,.9,COLORS["Yellow"])
    p.asset("CustomDecals/RunwayMarkings/Prethreshold Chevron 30m",5600,c.width,c.height,"前入口非可用区域 V 形 · 30 m",
            "黄色笔画 0.9 m、约 45°；30 m 跨宽造景预设。根据跑道宽度与图 7-3 的距边、纵向间距调整布置。","ICAO 7.3 / 图 7-3",canvas=c)
    # X markings made from two rotated, butt-ended rectangles.
    # Runway figure labels 14.5 m between stroke-end centrelines, 36 m between ends.
    for name,priority,length,separation,stroke,color in [("Closed Runway X",5700,36,14.5,1.8,"White"),("Closed Taxiway X",5710,9/math.sqrt(2),9/math.sqrt(2),1.5,"Yellow")]:
        halfx=separation/2;halfy=length/2
        extra_x=stroke/2*length/math.hypot(length,separation)
        extra_y=stroke/2*separation/math.hypot(length,separation)
        w=separation+extra_x*2;h=length+extra_y*2;c=Canvas(w+.3,h+.3);cx=c.width/2;cy=c.height/2
        for direction in (-1,1):c.stroke((cx-halfx,cy-direction*halfy),(cx+halfx,cy+direction*halfy),stroke,COLORS[color])
        p.asset(f"CustomDecals/RunwayMarkings/{name}",priority,c.width,c.height,"跑道关闭标记 · 白色 X" if color=="White" else "滑行道关闭标记 · 黄色 X",
                f"图 7-1：{'白色跑道关闭标记，笔画 1.8 m，端点基准距 14.5 × 36 m' if color=='White' else '黄色滑行道关闭标记，单斜臂全长 9 m、笔画 1.5 m'}。外接尺寸含斜端外伸部分。",
                "ICAO 7.1 / 图 7-1",canvas=c,painted=(w,h))
    # Aircraft stand lead-in and apron safety are separate purposes.
    for name,priority,width,color,note,ref in [
        ("Stand Lead In 0.15m",7400,.15,"Yellow","机位滑入线至少宽 0.15 m；航空器停车位置按机型和净距规划。","ICAO 5.2.13"),
        ("Apron Safety Red 0.1m",7410,.1,"Red","机坪安全线 0.10 m；红色为醒目对比色预设，标准要求与机位线不同且醒目。","ICAO 5.2.14")]:
        c=Canvas(width+.3,9);c.rect(.15,0,width,9,COLORS[color])
        p.asset(f"CustomNetlanes/Apron/{name}",priority,c.width,c.height,
                "黄色引导／描边线 · 15 cm" if color=="Yellow" else "红色安全／描边线 · 10 cm",
                note,ref,canvas=c,period=9,painted=(width,9),draw_order=41)
    # Thin outline pieces complement Surface fills; existing red/yellow lines are reused.
    for color,priority,width in [("White",8400,.1),("Black",8410,.1),("Black",8411,.15),("Yellow",8420,.1)]:
        c=Canvas(width+2*PADDING,9);c.rect(PADDING,0,width,9,COLORS[color])
        zh={"White":"白色","Black":"黑色","Yellow":"黄色"}[color]
        p.asset(f"CustomNetlanes/RoadMarking/Outline {color} {round(width*100)}cm",priority,c.width,c.height,
                f"{zh}描边线 · {round(width*100)} cm",f"{zh}实线，宽 {width:g} m；用于标记背景或涂漆区域描边。",
                "包内描边组件；宽度档位按所选标记图样使用",canvas=c,period=9,painted=(width,9),draw_order=41,
                note_en=f"{color} solid line, {width:g} m wide. Outline marking backgrounds or painted areas.")
    for name,priority,color,pavement in [("Airport Asphalt",8100,(67,69,70),True),("Airport Concrete",8110,(155,153,145),True),
        ("Paint White",8120,COLORS["White"],False),("Paint Yellow",8130,COLORS["Yellow"],False),
        ("Paint Red",8140,COLORS["Red"],False),("Paint Black",8150,COLORS["Black"],False)]:
        p.surface(name,priority,color,pavement)
    c=Canvas(10+.3,10+.3)
    for i in range(11):
        x=.15+i;c.rect(x-.015,.15,.03,10,COLORS["White"]);c.rect(.15,x-.015,10,.03,COLORS["White"])
    p.asset("CustomDecals/Calibration/Calibration Grid 10m",9900,c.width,c.height,"校准网格 · 10 m / 1 m",
            "网格基准中心线间距 1 m，整体首末线中心距 10 m；只用于实测比例。","包内校准工具",canvas=c)
    c=Canvas(20+.3,1+.3);c.rect(.15,.15+.45,20,.1,COLORS["White"])
    for i in range(21):c.rect(.15+i-.025,.15,.05,1 if i%5==0 else .5,COLORS["White"])
    p.asset("CustomDecals/Calibration/Calibration Ruler 20m",9910,c.width,c.height,"校准尺 · 20 m / 1 m",
            "刻度中心距 1 m，长刻度每 5 m；总基准长度 20 m。","包内校准工具",canvas=c)
    return p.finish()


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--bootstrap",action="store_true")
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if args.bootstrap:
        bootstrap()
    elif not BASELINE.exists():
        parser.error("Run --bootstrap on the original baseline first.")
    else:
        sys.exit(generate(Pipeline(args.check)))
