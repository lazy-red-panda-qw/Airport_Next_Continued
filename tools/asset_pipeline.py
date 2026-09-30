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
import string
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "Airport Decal Pack Countinue" / "CustomAssets"
SPEC = json.loads((ROOT / "asset-specs.json").read_text(encoding="utf-8"))
BASELINE = ROOT / "SourceAssets" / "baseline-assets.json"
SYMBOLS = string.ascii_uppercase + string.digits + "-"
COLORS = {k: tuple(v) for k, v in SPEC["palette"].items()}
N = 1024
AA = 2
PADDING = SPEC["decal_padding_m"]


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
    for s in SYMBOLS:
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
              image=None, period=None, painted=None):
        if priority in self.seen:
            raise ValueError(f"Duplicate UiPriority {priority}: {rel}")
        self.seen.add(priority)
        if not 1000 <= priority < 10000:
            raise ValueError(f"Priority out of reserved ranges: {rel}")
        folder = ASSETS / rel
        old = self.baseline.get(rel)
        order = old["draw_order"] if old else 42
        is_lane = rel.startswith("CustomNetlanes/")
        data = decal_config(width, height, priority, order, old["decal"] if old else None)
        if is_lane:
            data.pop("UiPriority")
            if period is None:
                raise ValueError(f"Missing explicit tile length: {rel}")
            self.output(folder / "netlane.json", json_bytes(curve_config(priority, period)))
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
        self.record(rel,priority,width,height,actual,period,order,title,note,ref,full,
                    "NetLaneGeometryPrefab" if is_lane else "StaticObjectPrefab", not old)
        self.contacts.append((priority,title,image.resize((128,128),Image.Resampling.LANCZOS)))

    def record(self,rel,priority,width,height,painted,period,order,title,note,ref,full,kind,new):
        self.rows.append({"UiPriority":priority,"path":rel,"type":kind,"new":new,
                          "mesh_x_m":round(width,6) if width else None,
                          "mesh_z_m":round(height,6) if height else None,
                          "paint_x_m":round(painted[0],6) if painted else None,
                          "paint_z_m":round(painted[1],6) if painted else None,
                          "tile_period_m":period,"draw_order":order,"title":title,
                          "reference":ref,"notes":note,"prefab_name":full})
        english = full.removeprefix(SPEC["mod_name"] + " ").removesuffix(" Decal").removesuffix(" NetLane").removesuffix(" Surface")
        for lang, values in self.locales.items():
            values[f"Assets.NAME[{full}]"] = english if lang == "en-US" else title
            values[f"Assets.DESCRIPTION[{full}]"] = note

    def character(self,s,height,rel,priority,title,background=None,foreground="White",margin=0,ref="造景字符预设；保留作者字形"):
        mask = load_glyph(s)
        gw = mask.width/mask.height*height
        width, length = gw+margin*2+PADDING*2, height+margin*2+PADDING*2
        canvas = Canvas(width,length)
        if background:
            canvas.rect(PADDING,PADDING,gw+margin*2,height+margin*2,COLORS[background])
        pw, ph = max(1,round(gw/width*N*AA)),max(1,round(height/length*N*AA))
        stamp = Image.new("RGBA",(pw,ph),COLORS[foreground]+(0,))
        stamp.putalpha(mask.resize((pw,ph),Image.Resampling.LANCZOS))
        canvas.im.alpha_composite(stamp,(round((PADDING+margin)/width*N*AA),round((PADDING+margin)/length*N*AA)))
        note = f"字符高度 {height:g} m，字符宽度 {gw:.3f} m。" + (f"底板四周外延 {margin:g} m。" if background else "")
        note += "字体保留作者原图；字形轮廓尚未逐笔画认证。"
        self.asset(rel,priority,width,length,title,note,ref,image=canvas.finish())

    def surface(self,name,priority,color,pavement=False):
        if priority in self.seen or not 1000 <= priority < 10000:
            raise ValueError(f"Duplicate or invalid Surface UiPriority {priority}: {name}")
        self.seen.add(priority)
        rel=f"Surfaces/Pavement/{name}"
        folder=ASSETS/rel
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
                "colossal_EdgeFadeRange":{"x":0.02,"y":0.005,"z":0,"w":0},
                "colossal_EdgeNoise":{"x":0,"y":0,"z":0,"w":0}}}))
        full=f'{SPEC["mod_name"]} Pavement {name} Surface'
        title={"Airport Asphalt":"机场沥青 Surface","Airport Concrete":"机场混凝土 Surface"}.get(name,name+" Surface")
        self.record(rel,priority,None,None,None,None,35 if pavement else 38,title,
                    "面积由 Surface 工具绘制；UVScale=0.2，贴图名义重复尺度约 5 m。平面颜色与微颗粒预设；非经认证 PBR 铺装。",
                    "EAI 1.7.5/1.7.6 新版 Surfaces 导入器",full,"SurfacePrefab",True)
        self.contacts.append((priority,title,image.resize((128,128),Image.Resampling.LANCZOS)))

    def finish(self):
        rows=sorted(self.rows,key=lambda x:x["UiPriority"])
        missing=set(self.baseline)-{r["path"] for r in rows}
        if missing:
            raise ValueError(f"Original asset identities missing: {sorted(missing)}")
        csvout=io.StringIO(newline="")
        writer=csv.DictWriter(csvout,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
        self.output(ROOT/"docs"/"asset-catalog.csv",csvout.getvalue().encode("utf-8-sig"))
        self.output(ROOT/"docs"/"asset-catalog.json",json_bytes(rows))
        manifest="\n".join(r["type"]+"\t"+r["prefab_name"] for r in rows)+"\n"
        self.output(ASSETS/"airport-prefabs.tsv",manifest.encode("utf-8"))
        for lang,data in self.locales.items():
            self.output(ASSETS/"Localization"/(lang+".json"),json_bytes(data))
        # Representative contact sheet, instead of hundreds of unreadable thumbnails.
        selected=[r for r in sorted(self.contacts) if r[0] in [1000,1001,3000,3010,4000,4010,4040,4060,4090,4100,4110,4120]
                  or 5000<=r[0]<6100 or r[0] in [7000,7001,7400,8100,8110,8120,8130,8140,8150,9000,9001,9002,9900,9910]]
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
        print(f'{len(rows)} assets ({sum(r["new"] for r in rows)} new), all 187 original identities retained; '
              f'UiPriority {min(self.seen)}..{max(self.seen)}, unique; {len(self.changed)} changed outputs.')
        if self.check and self.changed:
            print("Outputs need regeneration:\n"+"\n".join(self.changed[:30]),file=sys.stderr)
            return 1
        return 0


def runway(s):
    """Figure 5-3 geometry. 6/9 overhang the nominal 9 m body by 0.5 m."""
    polys=[];holes=[];w=3;h=9
    if s=="0":
        polys=[[(0,0),(3,0),(3,9),(0,9)]];holes=[[(.8,1.5),(2.2,1.5),(2.2,7.5),(.8,7.5)]]
    elif s=="1":
        w=1.1;polys=[[(.3,0),(1.1,0),(1.1,9),(.3,9),(.3,1.5),(0,1.5),(0,.4)]]
    elif s=="2":
        polys=[[(0,0),(3,0),(3,2.9),(.8,6.4),(.8,7.5),(3,7.5),(3,9),(0,9),(0,6.4),(2.2,2.9),(2.2,1.5),(.8,1.5),(.8,2.4),(0,2.4)]]
    elif s=="3":
        polys=[[(0,0),(3,0),(3,2.5),(1.8,3.6),(3,4.7),(3,9),(0,9),(0,7.5),(2.2,7.5),(2.2,5),(.8,3.6),(2.2,2.2),(2.2,1.5),(0,1.5)]]
    elif s=="4":
        w=3.9;polys=[[(0,7.1),(1.3,0),(2.1,0),(1.05,5.6),(2.4,5.6),(2.4,2.7),(3.2,2.7),(3.2,5.6),(3.9,5.6),(3.9,7.1),(3.2,7.1),(3.2,9),(2.4,9),(2.4,7.1)]]
    elif s=="5":
        polys=[[(0,0),(3,0),(3,1.5),(.8,1.5),(.8,2.7),(3,2.7),(3,9),(0,9),(0,7.5),(2.2,7.5),(2.2,4.2),(0,4.2)]]
    elif s in "69":
        h=9.5
        polys=[[(2.2,0),(2.2,1),(.8,3),(.8,4),(3,4),(3,9.5),(0,9.5),(0,2)]]
        holes=[[(.8,5.5),(2.2,5.5),(2.2,8),(.8,8)]]
        if s=="9":
            polys=[[(w-x,h-y) for x,y in p] for p in polys]
            holes=[[(w-x,h-y) for x,y in p] for p in holes]
    elif s=="7":
        w=3.5;polys=[[(0,0),(3.5,0),(1.1,9),(.3,9),(2.3,1.5),(0,1.5)]]
    elif s=="8":
        polys=[[(0,0),(3,0),(3,3.15),(2.2,3.9),(3,4.65),(3,9),(0,9),(0,4.65),(.8,3.9),(0,3.15)]]
        holes=[[(.8,1.5),(2.2,1.5),(2.2,3.15),(.8,3.15)],[(.8,4.65),(2.2,4.65),(2.2,7.5),(.8,7.5)]]
    elif s=="L":
        polys=[[(0,0),(.8,0),(.8,7.5),(3,7.5),(3,9),(0,9)]]
    elif s=="C":
        polys=[[(0,0),(3,0),(3,2.1),(2.2,2.1),(2.2,1.5),(.8,1.5),(.8,7.5),(2.2,7.5),(2.2,6.9),(3,6.9),(3,9),(0,9)]]
    elif s=="R":
        polys=[[(0,0),(3,0),(3,5.3),(2.2,5.3),(3,9),(2.2,9),(1.4,5.3),(.8,5.3),(.8,9),(0,9)]]
        holes=[[(.8,1.5),(2.2,1.5),(2.2,3.8),(.8,3.8)]]
    return w,h,polys,holes


def generate(p):
    for i,s in enumerate(SYMBOLS):
        for suffix,height,offset in [(" Small",2,0),("",4,1)]:
            height=SPEC["general_character_heights_m"]["Small" if suffix else "Standard"]
            p.character(s,height,f"CustomDecals/Alphabet/{glyph_name(s)}{suffix}",1000+i*10+offset,f"通用 {s} · {height:g} m")
        for outbound in (False,True):
            name=("Outbound " if outbound else "Taxiway ")+("Dash" if s=="-" else s)
            p.character(s,SPEC["information_character_height_m"],f"CustomDecals/Alphabet/{name}",3000+i*20+(10 if outbound else 0),
                        f'{"方向" if outbound else "位置"} {s} · 4 m',"Yellow" if outbound else "Black",
                        "Black" if outbound else "Yellow",SPEC["sign_background_margin_m"],"ICAO 5.2.17；原字形保留")
        for height,offset in [(2,0),(4,1)]:
            name=f'Mandatory {"Dash" if s=="-" else s} {height}m'
            p.character(s,height,f"CustomDecals/Mandatory/{name}",7000+i*5+offset,f"强制标记 {s} · {height} m",
                        "Red","White",.5,"ICAO 5.2.16.6 / 5.2.16.9 / 5.2.16.10；原字形保留")

    for i,s in enumerate("0123456789LCR"):
        w,h,polys,holes=runway(s)
        for offset,(size,scale) in enumerate(SPEC["runway_scales"].items()):
            c=Canvas(w*scale+PADDING*2,h*scale+PADDING*2)
            for shape in polys:c.polygon([(x*scale+PADDING,y*scale+PADDING) for x,y in shape],COLORS["White"])
            for shape in holes:c.polygon([(x*scale+PADDING,y*scale+PADDING) for x,y in shape],(0,0,0,0))
            p.asset(f"CustomDecals/RoadMarkings/Runway {s} {size}",4000+i*10+offset,c.width,c.height,
                    f"跑道 {s} · ICAO ×{scale}",f"图 5-3 基础图样 ×{scale}，涂漆外接尺寸 {w*scale:g} × {h*scale:g} m。6/9 含斜笔超出部分。放大档是包内预设，非 ICAO 三种尺寸等级；两位跑道号需要包含前导零。",
                    "ICAO 5.2.2.4/5.2.2.6，图 5-3",canvas=c,painted=(w*scale,h*scale))

    # Original blank swatches remain 1 m building blocks.
    for color,name,prio in [("Black","TaxiWay SignBlnk Black",8000),("Yellow","TaxiWay SignBlank Yellow",8010),("Red","TaxiWay SignBlank Red",8020)]:
        c=Canvas(1+PADDING*2,1+PADDING*2);c.rect(PADDING,PADDING,1,1,COLORS[color])
        p.asset(f"CustomDecals/RoadMarkings/{name}",prio,c.width,c.height,f"{color} 底板 · 1 m",
                "1 × 1 m 通用拼接底板；完整强制标记底板需超出文字四周至少 0.5 m。","造景模块；ICAO 5.2.16.10",canvas=c,painted=(1,1))
    old=ASSETS/"CustomDecals/RoadMarkings/Arrow Straight/_BaseColorMap.png"
    im=Image.open(old).convert("RGBA");box=paint_box(im);w=(box[2]-box[0])/(box[3]-box[1])*4
    # This legacy arrow's source PNG stays unchanged, so repeated generation is stable.
    p.asset("CustomDecals/RoadMarkings/Arrow Straight",7300,w*im.width/(box[2]-box[0]),4*im.height/(box[3]-box[1]),
            "通用方向箭头 · 4 m","原有箭头实际涂漆高度 4 m；与内移入口专用箭头分开使用。","造景预设",image=im,painted=(w,4))

    for i,color in enumerate(("White","Yellow","Red","Black")):
        for j,(size,stroke) in enumerate(SPEC["generic_line_widths_m"].items()):
            c=Canvas(stroke+.3,9);c.rect(.15,0,stroke,9,COLORS[color])
            p.asset(f"CustomNetlanes/RoadMarking/{color} Line {size}",9000+i*10+j,c.width,c.height,f"{color} 线 · {stroke:g} m",
                    f"实线宽 {stroke:g} m。四种颜色统一此宽度；可作通用模块，具体用途仍需遵循标记颜色和布局规定。",
                    "ICAO 5.2.8 / 5.2.4 / 5.2.6 的模块宽度",canvas=c,period=9,painted=(stroke,9))

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
            p.asset(f"CustomNetlanes/RoadMarking/{name}",base+int(light),c.width,c.height,title+(" · 亮铺装" if light else " · 暗铺装"),
                    note,ref,canvas=c,period=period)

    def block(name,priority,w,h,note,ref,category="RunwayMarkings"):
        c=Canvas(w+PADDING*2,h+PADDING*2);c.rect(PADDING,PADDING,w,h,COLORS["White"])
        p.asset(f"CustomDecals/{category}/{name}",priority,c.width,c.height,name,note,ref,canvas=c,painted=(w,h))
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
    for i,(w,h,offset,gap,label) in enumerate([(4,30,150,6,"LDA under 800m"),(6,30,250,9,"LDA 800-1200m"),(6,45,300,18,"LDA 1200-2400m"),(6,45,400,18,"LDA 2400m plus"),(10,60,400,22.5,"Large preset")]):
        block(f"Aiming Point {label}",5200+i,w,h,f"单侧瞄准点块 {w} × {h} m；两块内缘距 {gap} m，起点距入口 {offset} m。尺寸取表内允许值；Large preset 的位置需按实际 LDA 选择。","ICAO 表 5-1")
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
        p.asset(f"CustomDecals/RunwayMarkings/{name}",priority,c.width,c.height,name,
                f"图 7-1：{'白色跑道关闭标记，笔画 1.8 m，端点基准距 14.5 × 36 m' if color=='White' else '黄色滑行道关闭标记，单斜臂全长 9 m、笔画 1.5 m'}。外接尺寸含斜端外伸部分。",
                "ICAO 7.1 / 图 7-1",canvas=c,painted=(w,h))
    # Aircraft stand lead-in and apron safety are separate purposes.
    for name,priority,width,color,note,ref in [
        ("Stand Lead In 0.15m",7400,.15,"Yellow","机位滑入线至少宽 0.15 m；航空器停车位置按机型和净距规划。","ICAO 5.2.13"),
        ("Apron Safety Red 0.1m",7410,.1,"Red","机坪安全线 0.10 m；红色为醒目对比色预设，标准要求与机位线不同且醒目。","ICAO 5.2.14")]:
        c=Canvas(width+.3,9);c.rect(.15,0,width,9,COLORS[color])
        p.asset(f"CustomNetlanes/Apron/{name}",priority,c.width,c.height,name,note,ref,canvas=c,period=9,painted=(width,9))
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
