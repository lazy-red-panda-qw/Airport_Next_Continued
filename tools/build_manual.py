"""Build independent Chinese/English release manuals from the actual asset catalog.

Requires reportlab and Pillow. Use AIRPORT_MANUAL_FONT for a Chinese TrueType font
outside Windows. Generated PDFs include all current assets, grouped by provenance.
"""
from __future__ import annotations

from collections import Counter
import io
import json
import math
import os
from pathlib import Path
import re
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from PIL import Image as PILImage, ImageDraw
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, KeepTogether, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'Airport Decal Pack Countinue/CustomAssets'
CATALOG = json.loads((ROOT / 'docs/asset-catalog.json').read_text('utf-8'))
SPEC = json.loads((ROOT / 'asset-specs.json').read_text('utf-8'))
DIMENSIONS = json.loads((ROOT / 'docs/manual/dimensions.json').read_text('utf-8'))
SOURCES = json.loads((ROOT / 'docs/manual/sources.json').read_text('utf-8'))
VERSION = ElementTree.parse(ROOT / 'Airport Decal Pack Countinue/Properties/PublishConfiguration.xml').getroot().find('ModVersion').get('Value')
REPO = 'https://github.com/lazy-red-panda-qw/Airport_Next_Continued'
PAGE_W, PAGE_H = A4
MARGIN = 42
WIDTH = PAGE_W - MARGIN * 2
NAVY = colors.HexColor('#182b3b')
YELLOW = colors.HexColor('#f2cf48')
GREY = colors.HexColor('#536574')
PALE = colors.HexColor('#edf2f5')
LANG = 'zh-CN'
STYLES = {}
LOCALES = {}
ROWS = {row['UiPriority']: row for row in CATALOG}
THUMBS = {}
MENU_COUNTS = Counter(row['path'].split('/')[1] for row in CATALOG)
TYPE_COUNTS = Counter(row['path'].split('/')[0] for row in CATALOG)
ADDED_COUNT = sum(row['new'] for row in CATALOG)


def tr(zh, en):
    return zh if LANG == 'zh-CN' else en


def configure(lang):
    global LANG, STYLES, LOCALES
    LANG = lang
    if lang == 'zh-CN':
        font_path = Path(os.environ.get('AIRPORT_MANUAL_FONT', 'C:/Windows/Fonts/simhei.ttf'))
        if not font_path.exists():
            raise FileNotFoundError('Set AIRPORT_MANUAL_FONT to an embeddable Chinese TrueType font.')
        if 'ManualCJK' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('ManualCJK', str(font_path)))
            pdfmetrics.registerFontFamily('ManualCJK', normal='ManualCJK', bold='ManualCJK', italic='ManualCJK', boldItalic='ManualCJK')
        font, bold = 'ManualCJK', 'ManualCJK'
    else:
        font, bold = 'Helvetica', 'Helvetica-Bold'
    STYLES = {
        'body': ParagraphStyle('body', fontName=font, fontSize=9.4, leading=15, textColor=NAVY, spaceAfter=8, wordWrap='CJK' if lang == 'zh-CN' else None),
        'small': ParagraphStyle('small', fontName=font, fontSize=7.5, leading=11, textColor=GREY, spaceAfter=5, wordWrap='CJK'),
        'table': ParagraphStyle('table', fontName=font, fontSize=8, leading=12, textColor=NAVY, wordWrap='CJK'),
        'tablehead': ParagraphStyle('tablehead', fontName=bold, fontSize=8, leading=11, textColor=colors.white, wordWrap='CJK'),
        'h1': ParagraphStyle('h1', fontName=bold, fontSize=20, leading=27, textColor=NAVY, spaceAfter=14, keepWithNext=True),
        'h2': ParagraphStyle('h2', fontName=bold, fontSize=13, leading=18, textColor=NAVY, spaceBefore=9, spaceAfter=8, keepWithNext=True),
        'card': ParagraphStyle('card', fontName=font, fontSize=7.8, leading=9.5, textColor=NAVY, wordWrap='CJK'),
        'toc': ParagraphStyle('toc', fontName=font, fontSize=10, leading=19, textColor=NAVY, leftIndent=0, firstLineIndent=0, spaceBefore=3),
    }
    locale = 'zh-HANS' if lang == 'zh-CN' else 'en-US'
    LOCALES = json.loads((ASSETS / f'Localization/{locale}.json').read_text('utf-8'))


def para(text, style='body'):
    return Paragraph(escape(text).replace('\n', '<br/>'), STYLES[style])


def name(row):
    return LOCALES[f"Assets.NAME[{row['prefab_name']}]"]


def heading(zh, en, level=1):
    p = para(tr(zh, en), f'h{level}')
    p.outline_level = level - 1
    return p


def section(story, zh, en, toc=True):
    if story:
        story.append(PageBreak())
    p = heading(zh, en)
    p.include_toc = toc
    story.append(p)


def text(story, zh, en, style='body'):
    story.append(para(tr(zh, en), style))


def table(rows, widths, header=True):
    formatted = [[para(str(cell), 'tablehead' if header and i == 0 else 'table') for cell in row] for i, row in enumerate(rows)]
    t = Table(formatted, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
    rules = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
             ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7), ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#cdd6dc'))]
    if header:
        rules += [('BACKGROUND', (0, 0), (-1, 0), NAVY), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE])]
    t.setStyle(TableStyle(rules))
    return t


def cached_image(row, physical=False):
    key = (row['UiPriority'], physical)
    if key in THUMBS:
        return THUMBS[key]
    im = PILImage.open(ASSETS / row['path'] / '_BaseColorMap.png').convert('RGBA')
    if physical and row['mesh_x_m'] and row['mesh_z_m']:
        ratio = row['mesh_x_m'] / row['mesh_z_m']
        size = (max(1, round(600 * min(1, ratio))), max(1, round(600 * min(1, 1 / ratio))))
    else:
        size = (360, 360)
    im = im.resize(size, PILImage.Resampling.LANCZOS)
    stream = io.BytesIO()
    im.save(stream, format='PNG')
    result = ImageReader(stream)
    THUMBS[key] = (result, im.size)
    return THUMBS[key]


def place_asset(c, priority, x, y, w, h, physical=True):
    reader, size = cached_image(ROWS[priority], physical)
    scale = min(w / size[0], h / size[1])
    aw, ah = size[0] * scale, size[1] * scale
    c.drawImage(reader, x + (w - aw) / 2, y + (h - ah) / 2, aw, ah, mask='auto')


class ArtPanel(Flowable):
    def __init__(self, kind, height=270):
        super().__init__()
        self.kind, self.width, self.height = kind, WIDTH, height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor('#343c42'))
        c.roundRect(0, 0, self.width, self.height, 8, fill=1, stroke=0)
        c.setFont(STYLES['body'].fontName, 9)
        c.setFillColor(colors.white)
        if self.kind == 'apron':
            for i, caption in enumerate([tr('基础贴花', 'Base decal'), tr('玩家组合示意', 'Player assembly')]):
                x = 16 + i * (self.width / 2)
                c.drawString(x, self.height - 20, caption)
                place_asset(c, 7740, x, 20, self.width / 2 - 32, self.height - 53)
            x = self.width / 2 + 30
            place_asset(c, 7832, x + 35, self.height - 99, 47, 50)
            place_asset(c, 7820, x + 51, self.height - 83, 11, 11)
            place_asset(c, 7840, x + 145, self.height / 2 - 35, 20, 34)
            c.setStrokeColor(colors.HexColor('#95a4b0'))
            c.setFillColor(colors.HexColor('#778590'))
            cx, cy = x + 88, self.height / 2
            p = c.beginPath()
            for n, (dx, dy) in enumerate([(0, 58), (8, 38), (8, -5), (63, -33), (63, -44), (8, -28), (8, -65), (20, -82), (20, -89), (0, -82), (-20, -89), (-20, -82), (-8, -65), (-8, -28), (-63, -44), (-63, -33), (-8, -5), (-8, 38)]):
                (p.moveTo if n == 0 else p.lineTo)(cx + dx, cy + dy)
            p.close()
            c.drawPath(p, fill=1, stroke=1)
            c.setFillColor(YELLOW)
            c.drawCentredString(cx, 34, '314')
        elif self.kind == 'runway':
            for i, priority in enumerate([5601, 5602, 5603]):
                row = ROWS[priority]
                x = 20 + i * (self.width / 3)
                w = (self.width / 3 - 38) * [0.6, 0.8, 1][i]
                x += (self.width / 3 - 38 - w) / 2
                c.setFillColor(colors.HexColor('#555b5e'))
                c.rect(x, 22, w, self.height - 58, fill=1, stroke=0)
                reader, _ = cached_image(row)
                tile_h = (self.height - 64) / 4
                for j in range(4):
                    c.drawImage(reader, x, 24 + j * tile_h, w, tile_h, mask='auto')
                c.setFillColor(colors.HexColor('#b1b1b1'))
                c.rect(x, self.height - 42, w, 3, fill=1, stroke=0)
                c.setFillColor(colors.white)
                c.drawCentredString(x + w / 2, self.height - 20, f'{priority} / {30 + i * 15} m')
        elif self.kind == 'lettering':
            for i, (background, letter, caption) in enumerate([
                (8203, 2011, tr('位置标记组合', 'Location assembly')),
                (8243, 2021, tr('方向标记组合', 'Direction assembly')),
            ]):
                x = 16 + i * (self.width / 2)
                c.drawString(x, self.height - 20, caption)
                place_asset(c, background, x, 26, self.width / 2 - 32, 72)
                place_asset(c, letter, x + 76, 28, 24, 64)
                if i == 1:
                    place_asset(c, 7301, x + 115, 28, 21, 64)
        else:
            for i, (priority, title) in enumerate([(8160, tr('混凝土', 'Concrete')), (8170, tr('沥青', 'Asphalt')), (8500, tr('禁停斜线', 'No-parking hatch'))]):
                x = 16 + i * (self.width / 3)
                if priority == 8500:
                    reader, _ = cached_image(ROWS[priority])
                    edge = min(self.width / 3 - 28, self.height - 53)
                    for yy in range(5):
                        for xx in range(5):
                            c.drawImage(reader, x + xx * edge / 5, 20 + yy * edge / 5, edge / 5, edge / 5, mask='auto')
                else:
                    place_asset(c, priority, x, 20, self.width / 3 - 28, self.height - 53, False)
                c.drawString(x, self.height - 20, f'{priority} / {title}')


class AtlasPage(Flowable):
    def __init__(self, rows, group, number, total):
        super().__init__()
        self.rows, self.group, self.number, self.total = rows, group, number, total
        self.width, self.height = WIDTH, 696

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.setFont(STYLES['h2'].fontName, 11)
        c.drawString(0, self.height - 13, f'{self.group} - {self.number}/{self.total}')
        c.setFillColor(GREY)
        c.setFont(STYLES['small'].fontName, 7)
        c.drawString(0, self.height - 29, tr('Decal按物理比例；NetLane/Surface展示UV贴图。每卡尺寸均为米。', 'Decals use physical aspect; NetLane/Surface show UV tiles. Card dimensions are metres.'))
        cell_w = self.width / 3
        cell_h = 130
        for i, row in enumerate(self.rows):
            col, line = i % 3, i // 3
            x, y = col * cell_w, self.height - 43 - (line + 1) * cell_h
            c.setFillColor(colors.HexColor('#f6f8f9'))
            c.setStrokeColor(colors.HexColor('#d9e0e5'))
            c.roundRect(x + 2, y + 2, cell_w - 6, cell_h - 5, 4, fill=1, stroke=1)
            c.setFillColor(NAVY)
            c.setFont('Helvetica-Bold', 8)
            asset_type = 'Surface' if row['path'].startswith('Surfaces/') else 'NetLane' if row['path'].startswith('CustomNetlanes/') else 'Decal'
            c.drawString(x + 8, y + cell_h - 15, f"{row['UiPriority']}   {asset_type}")
            # A grey checkerboard separates transparent gaps from opaque paint.
            gx, gy, gw, gh = x + 8, y + 55, cell_w - 18, 58
            c.setFillColor(colors.HexColor('#7b858d'))
            c.rect(gx, gy, gw, gh, fill=1, stroke=0)
            c.setFillColor(colors.HexColor('#8b959d'))
            for rr in range(6):
                for cc in range(16):
                    if (rr + cc) % 2 == 0:
                        c.rect(gx + cc * gw / 16, gy + rr * gh / 6, gw / 16, gh / 6, fill=1, stroke=0)
            place_asset(c, row['UiPriority'], gx + 1, gy + 1, gw - 2, gh - 2, asset_type == 'Decal')
            p = para(name(row), 'card')
            _, ph = p.wrap(cell_w - 18, 35)
            if ph > 29:
                raise ValueError(f"Atlas name too tall: {row['UiPriority']} ({ph} pt)")
            p.drawOn(c, x + 8, y + 50 - ph)
            c.setFont(STYLES['small'].fontName, 6.4)
            c.setFillColor(GREY)
            if row['mesh_x_m']:
                meta = f"P {row['mesh_x_m']:.3f} x {row['mesh_z_m']:.3f} | D {row['draw_order']}"
                paint = f"G {row['paint_x_m']:.3f} x {row['paint_z_m']:.3f}"
                if row['tile_period_m']:
                    paint += f" | T {row['tile_period_m']:g}"
            else:
                meta = f"T {(row['tile_period_m'] or 5):.5g} | D {row['draw_order']}"
                paint = tr('自由绘制区域', 'Free area and outline')
            c.drawString(x + 8, y + 14, meta)
            c.drawString(x + 8, y + 5, paint)


class ManualDoc(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(str(filename), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=43, bottomMargin=42,
                         title=f'Airport Details Pack Continued {VERSION} - {LANG}', author='Airport Details Pack creator', pageCompression=1)
        frame = Frame(MARGIN, 42, WIDTH, PAGE_H - 85, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate('manual', frames=[frame], onPage=self.decorations))
        self.heading_number = 0

    def beforeDocument(self):
        # TOC links must use stable keys on every layout pass.
        self.heading_number = 0

    def decorations(self, c, doc):
        c.saveState()
        c.setStrokeColor(YELLOW)
        c.setLineWidth(2)
        c.line(MARGIN, PAGE_H - 30, PAGE_W - MARGIN, PAGE_H - 30)
        c.setFont('Helvetica', 7.5)
        c.setFillColor(GREY)
        c.drawString(MARGIN, PAGE_H - 23, f'Airport Details Pack Continued | {VERSION} | WIP')
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 23, 'ZH-CN' if LANG == 'zh-CN' else 'EN-US')
        c.setStrokeColor(colors.HexColor('#d3dce2'))
        c.setLineWidth(.4)
        c.line(MARGIN, 31, PAGE_W - MARGIN, 31)
        c.setFont(STYLES['small'].fontName, 7)
        c.drawString(MARGIN, 20, tr('首个公开版本 | 静态机场造景组件 | 2026-10-02', 'First public edition | Static airport scenery | 2026-10-02'))
        c.drawRightString(PAGE_W - MARGIN, 20, str(doc.page))
        c.restoreState()

    def afterFlowable(self, flowable):
        if hasattr(flowable, 'outline_level'):
            self.heading_number += 1
            label = flowable.getPlainText()
            key = f'section-{self.heading_number}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(label, key, level=flowable.outline_level)
            if flowable.outline_level == 0 and getattr(flowable, 'include_toc', True):
                self.notify('TOCEntry', (0, label, self.page, key))


def illustration(story, path, caption_zh, caption_en, max_h=290):
    im = PILImage.open(path)
    scale = min(WIDTH / im.width, max_h / im.height)
    story.append(KeepTogether([Image(str(path), im.width * scale, im.height * scale), para(tr(caption_zh, caption_en), 'small')]))


def story_body():
    s = []
    s += [Spacer(1, 23), para(tr('机场地面细节包', 'AIRPORT DETAILS PACK'), 'h1'), para('Continued', 'h1'), Spacer(1, 12)]
    text(s, f'{VERSION} | 中文说明书 | 首个公开 WIP 版本', f'{VERSION} | English manual | First public WIP release')
    text(s, '模块化标线、机坪布局与机场铺装', 'Modular markings, apron layouts and pavement surfaces', 'h2')
    s += [Spacer(1, 20), ArtPanel('apron', 280), Spacer(1, 18)]
    text(s, f"{len(CATALOG)}项资产：{TYPE_COUNTS['CustomDecals']} Decal、{TYPE_COUNTS['CustomNetlanes']} NetLane、{TYPE_COUNTS['Surfaces']} Surface。", f"{len(CATALOG)} assets: {TYPE_COUNTS['CustomDecals']} Decals, {TYPE_COUNTS['CustomNetlanes']} NetLanes and {TYPE_COUNTS['Surfaces']} Surfaces.")
    text(s, '本说明书随版本生成：使用方法、规范图节选、数值附录与完整精灵图索引。示意图不模拟游戏光照。', 'This versioned manual includes workflows, public standard-figure excerpts, dimensional appendices and the complete sprite atlas. Illustrations do not simulate game lighting.')
    section(s, '目录与阅读方法', 'Contents and how to read this guide', toc=False)
    toc = TableOfContents()
    toc.levelStyles = [STYLES['toc']]
    s.append(toc)
    s.append(Spacer(1, 15))
    text(s, '主体先讲怎样搭建；附录A区分规范、地区指导和包内预设；附录B给出10种机坪尺寸；最后的精灵图逐项列出所有当前资产及实际涂漆范围。', 'Start with the assembly workflows. Appendix A distinguishes standards, regional guidance and package presets. Appendix B lists ten apron-base sizes. The final atlas indexes every current asset and its paint bounds.')
    text(s, '精灵图中的编号是菜单排序UiPriority。P为完整投影，G为可见涂漆外接范围，T为周期，D为绘制层。透明留白不算涂漆。', 'Atlas numbers are menu UiPriority values. P is complete projection, G is visible paint bounds, T is repeat/tile size and D is draw order. Transparent padding is not paint.')
    section(s, '01 / 本包包含什么', '01 / What is included')
    text(s, '本包是同作者Airport Details Pack的续作，为Cities: Skylines II提供可以自由组合的机场地面标记和铺装。它们是静态资产，玩家决定放置位置并组合场景。', 'This sequel to the same creator\'s Airport Details Pack supplies modular airport ground markings and pavement for Cities: Skylines II. These are static assets placed and assembled by the player.')
    s.append(table([[tr('入口', 'Menu'), tr('数量', 'Count'), tr('内容', 'Contents')],
                    [tr('Decal / 字符', 'Decal / Alphabet'), MENU_COUNTS['Alphabet'], tr('三色透明字符，1/2/4 m，含连字符与小数点', 'Transparent characters in three colours and 1/2/4 m sizes, including hyphens and points')],
                    [tr('Decal / 道路贴花', 'Decal / RoadMarkings'), MENU_COUNTS['RoadMarkings'], tr('跑道、箭头、背景、10种机坪、25项配套、量尺', 'Runway blocks, arrows, backgrounds, ten apron bases, 25 details and measurement helpers')],
                    [tr('NetLane / 道路线条', 'NetLane / RoadMarking'), MENU_COUNTS['RoadMarking'], tr('跑道、滑行道、等待、引导、背景条与描边', 'Runway/taxiway/holding/guidance lines, background strips and outlines')],
                    [tr('Surface / 铺装', 'Surface / Pavement'), MENU_COUNTS['Pavement'], tr('混凝土、沥青、四色涂漆、红色禁停斜线', 'Concrete, asphalt, four paint colours and red no-parking hatching')]], [150, 45, WIDTH - 195]))
    s += [Spacer(1, 15), ArtPanel('materials', 185)]
    text(s, '当前服务车辆道路专用交错块与分道虚线尚未加入；机位多机型黄虚线用于航空器引导。', 'Dedicated service-vehicle crossing blocks and lane-separation dashes are planned. The yellow secondary stand dashes guide aircraft.')
    section(s, '02 / 安装、工具与基本步骤', '02 / Setup, tools and first steps')
    text(s, '启用Extra Assets Importer（80529）、Extra Detailing Tools（80528）及其所需ExtraLib（75724）。在EAI设置中启用旧Decal/NetLane、Surfaces和Localization导入。发布配置目标为1.6.*，作者当前游戏为1.6.2f。', 'Enable Extra Assets Importer (80529), Extra Detailing Tools (80528) and their required ExtraLib (75724). Enable legacy Decal/NetLane, Surfaces and Localization imports in EAI. The release targets game 1.6.*; the author currently uses 1.6.2f.')
    for zh, en in [
        ('1. 用混凝土或沥青Surface绘道面。', '1. Draw pavement with the concrete or asphalt Surface.'),
        ('2. 用NetLane沿线拉取标记，先保持默认比例。', '2. Draw NetLane markings along a line, starting at default scale.'),
        ('3. 用Decal放置标记块、背景、字符和机坪基础。', '3. Place Decal blocks, backgrounds, characters and apron bases.'),
        ('4. 用20 m量尺复核比例；工具缩放会同时改变笔画与周期。', '4. Check scale with the 20 m ruler; tool scaling changes strokes and repeats together.'),
        ('5. 选好独立配套、校准一组，再成组复制。', '5. Choose separate details, align one assembly, then duplicate the group.')]:
        text(s, zh, en)
    text(s, '铺装在底层，涂漆与斜线其次，背景和组件在上，字符与箭头最高。不同包叠放时先选小面积试放。', 'Pavement sits below paint and hatching; backgrounds and details sit above, with characters and arrows at the top. Start with a small area when combining packs.')
    section(s, '03 / 组合文字、箭头与背景', '03 / Assemble lettering and backgrounds')
    text(s, '先选择用途与字高，再按白/黑/黄配色放置字符、连字符和小数点。背景条用于自由长度标记，固定宽幅用于快捷布置，端帽可旋转180度。多行或复杂轮廓用涂漆Surface加独立描边。', 'Choose the purpose and lettering height, then place white, black or yellow characters, hyphens and points. Strips provide a chosen length, fixed blocks provide quick layouts, and caps rotate 180 degrees. Use paint Surfaces and separate outlines for multiple lines or complex shapes.')
    s += [ArtPanel('lettering', 135), Spacer(1, 10)]
    text(s, '例如黑底黄框配黄字A组合位置标记，黄底黑框配黑字B与箭头组合方向标记；透明1/2 m字可组合314或314L机位编号。用途还需要正确的位置与布置。', 'For example, assemble a location marking from yellow A on black with a yellow border, or a direction marking from black B and an arrow on yellow with a black border. Transparent 1/2 m lettering can form stand 314 or 314L. Use also depends on correct position and arrangement.')
    text(s, '字符尺寸指可见涂漆字高，投影还包含透明留白。白色RGB177是作者选择的游戏配色；不要把本包档位当作每种机场标记的统一法定字高。', 'Character sizes refer to visible paint height; projections include transparent margins. RGB177 white is the author\'s game palette. Package sizes are not a universal regulatory text-height rule for every marking role.')
    section(s, '04 / 跑道与前入口区域', '04 / Runways and pre-threshold areas')
    text(s, '组合两位跑道编号，按跑道宽度选择入口条纹；中线沿纵向拉取，瞄准点及接地带按LDA和入口位置成对布置。内移入口白箭头用于可正常使用的入口前段，黄V形用于不适合正常使用的铺筑区域。', 'Assemble two-digit designators and select threshold stripes by runway width. Draw the centre line longitudinally, then place paired aiming points and touchdown-zone blocks according to LDA and threshold position. White arrows mark a usable displaced-threshold portion; yellow chevrons mark unsuitable paved areas.')
    s += [ArtPanel('runway', 290), Spacer(1, 8)]
    text(s, '5501横向画1.8 m白条；5601/5602/5603沿纵轴分别匹配30/45/60 m道面。5604是单根0.9 m黄色线，两个斜臂由玩家分别画，再按30 m顶点周期复制。', 'Draw 5501 transversely for a 1.8 m white bar. Draw 5601/5602/5603 longitudinally for 30/45/60 m pavement. 5604 is one 0.9 m yellow line: draw two arms separately, then duplicate at 30 m apex spacing.')
    text(s, 'V形尖端朝跑道。重复贴图起止处可能有局部斜臂，量完整相邻尖端，不能按首尾裁切判断周期。', 'Chevron tips face the runway. Endpoints may crop partial arms; measure consecutive complete tips rather than endpoint fragments.')
    section(s, '05 / 滑行道与等待位置', '05 / Taxiways and holding positions')
    text(s, '黄色中线分有黑边与无黑边档，按道面选择对比。增强中线与普通中线用途不同；A2等待线的实线朝等待侧，B2提供ILS等待图样，中间等待为单黄虚线。', 'Yellow centre lines have contrast-edged and unedged variants. Enhanced guidance differs from ordinary guidance. A2 solid lines face the holding side; B2 marks ILS holds; intermediate holds use a single yellow dashed line.')
    text(s, '等待线NetLane沿等待横条方向拉取，不沿飞机前进方向绘制。非承重双黄线用于侧区边界，不等同于机坪红安全线或车辆道路标线。', 'Draw a holding NetLane along the transverse marking, not the aircraft travel direction. Double yellow non-load-bearing boundaries are distinct from red apron safety lines and vehicle road markings.')
    text(s, '本包选择图5-8的A2/B2放大式。合并文本允许现阶段采用；2026-11-26起图样选择统一为A2/B2。', 'This pack uses the enlarged A2/B2 patterns from Figure 5-8. The consolidated text allows them now; from 26 November 2026 the pattern choices become A2/B2.')
    section(s, '06 / 机坪基础与独立组件', '06 / Apron bases and independent details')
    s += [ArtPanel('apron', 290), Spacer(1, 8)]
    text(s, '八档折角基础包含黄引导、红安全分界、角部禁停、白外界与侧留白。另有简洁开放回转和直线贯通。廊桥运动区、轮位、设备框、停止参照与编号独立摆放。', 'Eight chamfered bases combine yellow guidance, red safety boundaries, corner no-parking areas, white outlines and side reserves. There are also open turnaround and straight-through bases. Bridge areas, wheels, parking boxes, stop datums and identifiers are placed separately.')
    text(s, '先对齐实际飞机，再按实际鼻轮或左座驾驶员放停止点；名义鼻尖不能当鼻轮。三档原版参照长/翼展为34/38、50.5/50.5、58/60 m。其他档位为造景尺寸。', 'Align the actual aircraft first, then place the stop datum for its nosewheel or left-seat pilot. The nominal nose tip is not a nosewheel datum. Measured game reference length/span: 34/38, 50.5/50.5 and 58/60 m. Other profiles are scenery presets.')
    text(s, '基础留白不自动赋予道路、停车许可或廊桥净空。按实际道具检查完整结构与运动包络，校准一个机位后再复制。开放回转R12 m不是所有机型的最小转弯半径。', 'Base reserves do not automatically define roads, parking permission or bridge clearance. Check the actual prop structure and movement envelope before duplicating a calibrated stand. The open R12 m curve is not a universal minimum aircraft turning radius.')
    section(s, '07 / 禁停、廊桥与设备区', '07 / No-parking, bridge and equipment areas')
    text(s, '禁停斜线表示限制停放，设备框表示停放区域，廊桥轮位表示收回停放点，活动线表示桥的运动范围。这些功能分别选择，不按颜色任意互换。', 'Hatching indicates no-parking areas; boxes indicate equipment parking; wheel marks indicate a retracted bridge parking point; movement lines indicate the bridge envelope. Select by function rather than treating colours as interchangeable.')
    text(s, '8500 Surface适合任意多边形，红色0.10 m边框另画；7830-7833提供矩形、梯形和L形快捷模块。轮位和设备框可以独立定位，不把桥的放射圆心当成所有实际铰点。', 'Use Surface 8500 for a chosen polygon with a separate 0.10 m red outline. 7830-7833 provide rectangular, trapezoidal and L-shaped modules. Position wheel marks and boxes independently; the radial centre is not automatically the actual bridge pivot.')
    illustration(s, ROOT / 'docs/manual/figures/caam-hatch.png', '规范图节选：CAAM CAGM1403，图11-1，PDF第55页。A为线宽，B为垂直间距；原始文件链接见来源表。', 'Public figure excerpt: CAAM CAGM1403 Figure 11-1, PDF page 55. A is stroke thickness; B is perpendicular spacing. Source link is in the references.', 340)
    section(s, '08 / 公开规范图与来源', '08 / Public standard figures and sources')
    text(s, '下列为有限图样节选，保留原图线条和标注，仅裁切图样范围。来源文件控制规范含义；本包图样用于游戏造景。', 'The following limited excerpts retain the original diagram strokes and labels, cropped to the relevant figure. Original documents control the normative meaning; package artwork is for game scenery.')
    illustration(s, ROOT / 'docs/manual/figures/annex-chevron.png', 'ICAO Annex14，图7-3，印刷页7-7，PDF第245页：前入口不可正常使用铺筑区域的V形图示。[A14]', 'ICAO Annex14 Figure 7-3, printed page 7-7, PDF page 245: chevrons on unsuitable pre-threshold pavement. [A14]', 230)
    illustration(s, ROOT / 'docs/manual/figures/annex-displaced.png', 'ICAO Annex14，图5-4(B)，印刷页5-9，PDF第135页：内移入口横条与白箭头。[A14]', 'ICAO Annex14 Figure 5-4(B), printed page 5-9, PDF page 135: displaced-threshold bar and white arrows. [A14]', 265)
    section(s, '09 / 推荐搭配与后续维护', '09 / Optional companions and continued development')
    for zh, en in [
        ('G87：更多沥青、铺装、道路标线和斜线选择。', 'G87: more asphalt, pavement, ordinary road markings and hatching.'),
        ('Sully Airport Essentials Pack：高质量机场砖块Surface、跑道边缘与其他机场细节。', 'Sully Airport Essentials Pack: high-quality airport tile Surfaces, runway-edge options and additional detailing.'),
        ('Airport Pack / LAX Airport Props / Runway Guard Light：牌体、建筑、廊桥、设备与灯具。', 'Airport Pack / LAX Airport Props / Runway Guard Light: sign bodies, buildings, bridges, equipment and lights.')]:
        text(s, zh, en)
    text(s, '推荐包按需配置，不是强制要求，尚未全部联合适配测试。适量安装，检查各自依赖、游戏版本与叠层。', 'Companions are optional, not requirements, and have not all been fully tested together. Add a moderate selection and check each pack\'s dependencies, game version and layering.')
    text(s, '本版是首个公开WIP，持续更新维护。下一步扩展服务车辆车道、用途明确的机坪标记与其他细节，优先保持模块化和可查的规格。', 'This first public WIP edition will continue to receive updates and maintenance. Planned work expands service-vehicle roads, purpose-specific apron markings and other details while keeping components modular and specifications traceable.')
    section(s, '附录 A / 数值、条件与制作预设', 'Appendix A / Dimensions, conditions and presets')
    text(s, '表中A14是ICAO依据；CAAC/CAAM为地区依据；LHR是机场运营方样式；PKG为包内预设；EAI为游戏实现参数；USER为作者实测。下限、建议与固定档位分开阅读。', 'A14 denotes ICAO; CAAC/CAAM denote regional sources; LHR denotes an airport-operator style; PKG denotes package presets; EAI denotes game implementation; USER denotes author measurements. Read minima, recommendations and fixed presets separately.')
    for group in DIMENSIONS['groups']:
        s.append(heading(group['title_zh'], group['title_en'], 2))
        rows = [[tr('项目', 'Item'), tr('尺寸与适用条件', 'Dimensions and conditions'), tr('依据', 'Source')]]
        rows += [[r[0] if LANG == 'zh-CN' else r[1], r[2] if LANG == 'zh-CN' else r[3], r[4]] for r in group['rows']]
        s += [table(rows, [97, WIDTH - 176, 79]), Spacer(1, 12)]
    section(s, '附录 B / 十种机坪的物理尺寸', 'Appendix B / Physical sizes of ten apron bases')
    text(s, '机长与翼展是参照矩形；C为每侧净空建议；P是整张含服务留白的投影。形状和占地为本包基础布局，精灵图另列可见涂漆外接框。', 'Length/span describe the reference rectangle. C is the per-side clearance recommendation. P is full projection including reserves. Shape and footprint are package layouts; atlas cards separately list visible paint bounds.')
    profiles = {p['priority']: p for p in SPEC['stand_presets']['profiles']}
    for v in SPEC['apron_layouts']['variants']:
        base = next(p for p in profiles.values() if p['key'] == v['base'])
        profiles[v['priority']] = dict(base, **v)
    rows = [[tr('编号与布局', 'ID and layout'), tr('长 x 翼展 / C', 'Length x span / C'), tr('投影宽 x 长', 'Projection W x L')]]
    for priority in sorted(profiles):
        p = profiles[priority]
        row = ROWS[priority]
        clearance = SPEC['stand_presets']['clearances_m'][p['code']]
        rows.append([f'{priority} {name(row)}', f"{p['length_m']:g} x {p['span_m']:g} m / {clearance:g} m", f"{row['mesh_x_m']:.2f} x {row['mesh_z_m']:.2f} m"])
    s.append(table(rows, [220, 133, WIDTH - 353]))
    text(s, '原版三档来自作者实测；通航、通用窄体和大型宽体档为包内尺寸。停止点、廊桥位置与设备位不由上述参照矩形推算。', 'The three game-aircraft profiles are author measurements. GA, generic narrowbody and larger widebody profiles are package sizes. Stop, bridge and equipment positions are not inferred from these rectangles.')
    section(s, '附录 C / 来源、链接与范围', 'Appendix C / References, links and scope')
    for source in SOURCES['sources']:
        s.append(Paragraph(f"<b>{source['id']}</b> - <link href=\"{escape(source['url'])}\" color=\"#1e5f82\">{escape(source['title'])}</link>", STYLES['body']))
        if LANG == 'en-US':
            s.append(para(source['scope'], 'small'))
    text(s, '标准来源按引用版次使用。Doc9157 Part4 Amendment2全文尚未取得，ACI目录未作为未核实尺寸来源。本说明书不把造景预设或贴图配色表述为全球统一强制标准。', 'Sources are identified by the cited editions. Full Doc9157 Part4 Amendment2 has not been obtained; ACI contents listings are not used as unverified dimensional evidence. This manual does not turn scenery presets or texture colours into universal mandatory rules.')
    for label, suffix in [(tr('仓库', 'Repository'), ''), (tr('玩家指南', 'Player guide'), '/blob/main/docs/manual/README.md'), (tr('完整清单', 'Complete catalog'), f'/blob/v{VERSION}/docs/asset-catalog.csv')]:
        s.append(Paragraph(f'<link href="{REPO}{suffix}" color="#1e5f82">{label}: {REPO}{suffix}</link>', STYLES['small']))
    text(s, '图样节选的原始页码与裁切记录位于docs/manual/sources.json。原文和图样版权归其发布机构；本仓库只保存有限图样节选，不再分发整份标准文件。', 'Original page numbers and crop records are in docs/manual/sources.json. Source text and figures remain with their publishing bodies; the repository includes only limited diagram excerpts, not entire standards documents.')
    section(s, '附录 D / 完整资产精灵图', 'Appendix D / Complete asset sprite atlas')
    text(s, f'先列{ADDED_COUNT}项新增资产，再列{len(CATALOG) - ADDED_COUNT}项作者母版组件；共{len(CATALOG)}项，每项恰好出现一次。', f'The atlas lists {ADDED_COUNT} added assets followed by {len(CATALOG) - ADDED_COUNT} original author components: {len(CATALOG)} entries, exactly once each.')
    text(s, '名称来自对应语言的游戏本地化。尺寸从最终PNG与JSON清单读取：投影P、涂漆G、周期T、绘制层D。NetLane和Surface预览为UV贴图，不能从卡片像素测真实线宽。', 'Names come from the matching game localization. Dimensions come from final PNG/catalog data: projection P, paint G, repeat T and draw order D. NetLane and Surface pictures show UV textures; card pixels cannot measure real stroke widths.')
    s.append(Spacer(1, 14))
    s.append(table([[tr('新增资产', 'Added assets'), sum(r['new'] for r in CATALOG)], [tr('作者原始来源保留', 'Original author sources retained'), sum(not r['new'] for r in CATALOG)], [tr('完整资产总数', 'Complete asset count'), len(CATALOG)]], [WIDTH - 80, 80], False))
    for added in [True, False]:
        group_rows = sorted((r for r in CATALOG if r['new'] == added), key=lambda r: r['UiPriority'])
        label = tr('新增资产', 'Added assets') if added else tr('作者原始来源', 'Original author sources')
        total = math.ceil(len(group_rows) / 15)
        for i in range(total):
            s += [PageBreak(), AtlasPage(group_rows[i * 15:(i + 1) * 15], label, i + 1, total)]
    return s


def main():
    output = ROOT / 'output/pdf'
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for lang in ['zh-CN', 'en-US']:
        configure(lang)
        path = output / f'Airport-Details-Pack-Continued-{VERSION}-Manual-{lang}.pdf'
        doc = ManualDoc(path)
        doc.multiBuild(story_body())
        reports.append({'language': lang, 'file': path.relative_to(ROOT).as_posix(), 'assets': len(CATALOG), 'added': sum(r['new'] for r in CATALOG), 'bytes': path.stat().st_size})
        print(json.dumps(reports[-1], ensure_ascii=True))
    report_path = ROOT / 'artifacts/manual-work/build-report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(reports, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
