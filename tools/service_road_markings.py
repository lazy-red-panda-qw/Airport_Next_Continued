"""Vehicle-road components and matching presets, in metres before rasterisation.

FAA paint dimensions and CAAM crossing dimensions stay separate. Road widths
are package choices within FAA apron design guidance, measured between the
outermost white edges. CAAM's diagram leaves the crossing centre clear;
FAA two-lane roads retain lane dividers, interrupted at aircraft markings.
"""
from __future__ import annotations

import json

FAA_MARKINGS = 'FAA AC150/5340-1M Change1 §5.2.3/5.2.5.1、图A-15/A-25；采用正文米制值'
FAA_WIDTHS = 'FAA AC150/5300-13B Change1 §5.19.3；4/7.5m为指导范围内的包内档位'
CAAM_CROSSING = 'CAAM CAGM1403 Issue02 Rev00 (2025) §20、图20-1/2；C为单列笔画厚度'
FAA_CONTRAST = 'FAA AC150/5340-1M Change1 §1.4、§5.2、附录C；0.15m黑色对比边，间隙填黑；YVR 2026 §7.6实拍作外观对照'


def staggered_edge(c, x, block_width, block_length, color, mirror=False):
    """Two touching rows alternate; one full repeat is two block lengths."""
    for row in range(2):
        column = 1 - row if mirror else row
        for z in range(round(c.height / (2 * block_length))):
            c.rect(x + column * block_width, (2 * z + row) * block_length,
                   block_width, block_length, color)


def generate_service_roads(p, Canvas, spec, colors, padding):
    cfg = spec['service_roads']
    priority = cfg['priorities']
    white = colors['White']
    continuous = cfg['continuous_tile_m']
    edge = cfg['edge_width_m']
    divider = cfg['divider_width_m']
    dash = cfg['divider_paint_m']
    gap = cfg['divider_gap_m']
    period = dash + gap
    rows = []

    def emit(key, name, title, c, paint_span, tile, zh, en, reference,
             role, lanes=None, road_width=None, pattern=None, contrast=False,
             centre_line=False):
        path = 'CustomNetlanes/RoadMarking/' + name
        p.asset(path, priority[key], c.width, c.height, title, zh, reference,
                canvas=c, period=tile, painted=(paint_span, c.height),
                draw_order=cfg['draw_order'], note_en=en)
        rows.append({'UiPriority': priority[key], 'path': path, 'role': role,
                     'lanes': lanes, 'road_width_m': road_width,
                     'paint_span_m': paint_span, 'tile_period_m': tile,
                     'pattern': pattern, 'reference': reference,
                     'contrast': contrast, 'centre_line': centre_line,
                     'white_span_m': road_width if road_width else paint_span -
                     (2 * cfg['contrast_border_m'] if contrast else 0)})

    c = Canvas(edge + 2 * padding, continuous, cfg['texture_px'])
    c.rect(padding, 0, edge, continuous, white)
    emit('edge', 'Vehicle Road Edge FAA 15cm', '车辆道路边线 · FAA · 15 cm',
         c, edge, continuous,
         '白色连续边线，宽0.15m。两侧分别拉取，自由选择车辆道路宽度；航空器通道交叉处保留原有航空器标线。',
         'Continuous white 0.15 m road edge. Draw each side separately at a chosen road width; leave aircraft markings clear at crossings.',
         FAA_MARKINGS, 'edge', pattern='FAA')

    c = Canvas(divider + 2 * padding, period, cfg['texture_px'])
    c.rect(padding, 0, divider, dash, white)
    # The paint bounding box is 4.5 m long, rather than the 12 m UV repeat.
    p.asset('CustomNetlanes/RoadMarking/Vehicle Road Divider FAA 15cm',
            priority['divider'], c.width, c.height,
            '车辆道路分道虚线 · FAA · 15 cm · 12 m 周期',
            '白色车道分隔虚线，宽0.15m、实段4.5m、空段7.5m，周期12m。独立放在车辆道路中心；不作为航空器引导线。',
            FAA_MARKINGS, canvas=c, period=period, painted=(divider, dash),
            draw_order=cfg['draw_order'],
            note_en='White vehicle-lane divider: 0.15 m wide, 4.5 m paint and 7.5 m gap, 12 m repeat. Place separately in the road centre; not aircraft guidance.')
    rows.append({'UiPriority': priority['divider'],
                 'path': 'CustomNetlanes/RoadMarking/Vehicle Road Divider FAA 15cm',
                 'role': 'divider', 'lanes': None, 'road_width_m': None,
                 'paint_span_m': divider, 'tile_period_m': period,
                 'pattern': 'FAA', 'reference': FAA_MARKINGS,
                 'contrast': False, 'centre_line': True, 'white_span_m': divider})

    block, length = cfg['faa']['block_width_m'], cfg['faa']['block_length_m']
    border = cfg['contrast_border_m']
    band = 2 * block + 2 * border
    c = Canvas(band + 2 * padding, 2 * length, cfg['texture_px'])
    c.rect(padding, 0, band, c.height, colors['Black'])
    staggered_edge(c, padding + border, block, length, white)
    emit('crossing_faa_contrast', 'Vehicle Crossing Edge FAA Black Contrast 30cm',
         '车辆道路黑底棋盘边线 · FAA · 30 cm 笔画', c, band, c.height,
         '两列交错白块配真实黑色对比底，每块1.2×0.30m；白块带总宽0.60m、两侧黑边各0.15m、总带宽0.90m，周期2.4m。浅色道面也保留黑白棋盘外观；两侧独立拉取，遇航空器标线分段留空。',
         'Staggered white 1.2 x 0.30 m blocks on painted black contrast. White band 0.60 m; 0.15 m black border each side; total band 0.90 m; repeat 2.4 m. Draw each road edge separately and leave gaps at aircraft markings.',
         FAA_CONTRAST, 'crossing_edge', pattern='FAA', contrast=True)

    for region in ('caam', 'faa'):
        block = cfg[region]['block_width_m']
        length = cfg[region]['block_length_m']
        tile = 2 * length
        label = region.upper()
        c = Canvas(2 * block + 2 * padding, tile, cfg['texture_px'])
        staggered_edge(c, padding, block, length, white)
        emit('crossing_' + region,
             f'Vehicle Crossing Edge {label} {round(block * 100)}cm',
             f'车辆道路穿越交错边线 · {label} · {block:g} m 笔画',
             c, 2 * block, tile,
             f'两列交错白块，每块长{length:g}m、单列厚{block:g}m，交错带总宽{2 * block:g}m、完整周期{tile:g}m。沿服务道路穿越航空器通道的两侧分别拉取；不作行人斑马线，遇航空器标线时分段留空。',
             f'Two staggered white rows: each block {length:g} m long and {block:g} m wide, {2 * block:g} m overall band, {tile:g} m full repeat. Draw each edge of a vehicle-road crossing separately; not a pedestrian crossing. Leave gaps at aircraft markings.',
             CAAM_CROSSING if region == 'caam' else FAA_MARKINGS,
             'crossing_edge', pattern=label)

    stop = cfg['stop_width_m']
    c = Canvas(stop + 2 * padding, continuous, cfg['texture_px'])
    c.rect(padding, 0, stop, continuous, white)
    emit('stop', 'Vehicle Road Stop Bar FAA 60cm', '车辆停止横线 · FAA · 60 cm',
         c, stop, continuous,
         '白色车辆停止横条，厚0.60m，横向拉过需要停止的车道，长度自由选择。停止位置、道路文字与牌体由玩家另放；不是机位飞机停止线。',
         'White 0.60 m vehicle stop bar. Draw transversely across the approach lane to a chosen length. Position, lettering and signs are separate; not an aircraft-stand stop datum.',
         FAA_MARKINGS, 'stop', pattern='FAA')

    for lanes, suffix, road_width in (
            (1, 'single', cfg['single_road_width_m']),
            (2, 'double', cfg['double_road_width_m'])):
        chinese = '单车道' if lanes == 1 else '双车道'
        english = 'Single Lane' if lanes == 1 else 'Two Lane'
        tag = f'{round(road_width * 100)}cm'
        tile = continuous if lanes == 1 else period
        c = Canvas(road_width + 2 * padding, tile, cfg['texture_px'])
        c.rect(padding, 0, edge, tile, white)
        c.rect(padding + road_width - edge, 0, edge, tile, white)
        if lanes == 2:
            c.rect(c.width / 2 - divider / 2, 0, divider, dash, white)
        centre_zh = '无中心线' if lanes == 1 else '带0.15m分道虚线，实4.5m、空7.5m'
        centre_en = 'No centre line' if lanes == 1 else 'Includes a 0.15 m divider, 4.5 m paint / 7.5 m gap'
        emit('normal_' + suffix, f'Vehicle Road Preset {english} FAA {tag}',
             f'车辆道路成套预设 · {chinese} · {road_width:g} m',
             c, road_width, tile,
             f'两侧白色连续边线各0.15m，标线外缘总宽{road_width:g}m；{centre_zh}。整套沿道路中心路径拉取，路宽为包内档位，透明内部由Surface另铺；箭头、编号和停止横线另放。缩放会同时改变线宽、路宽和周期。',
             f'Two continuous white 0.15 m edges, {road_width:g} m overall painted outer-edge span. {centre_en}. Draw the complete preset along the road centre path. Width is a package choice; add pavement, arrows, identifiers and stop bars separately. Scaling changes road width, strokes and repeats together.',
             FAA_MARKINGS + '；' + FAA_WIDTHS, 'normal_preset',
             lanes=lanes, road_width=road_width, pattern='FAA', centre_line=lanes == 2)

        for region, contrast in (('caam', False), ('faa', False), ('faa', True)):
            block = cfg[region]['block_width_m']
            length = cfg[region]['block_length_m']
            # 12 m carries five FAA zipper repeats and one complete lane divider.
            has_centre = region == 'faa' and lanes == 2
            tile = period if has_centre else 2 * length
            label = region.upper()
            extra = border if contrast else 0
            c = Canvas(road_width + 2 * (padding + extra), tile, cfg['texture_px'])
            left = padding + extra
            right = left + road_width - 2 * block
            if contrast:
                c.rect(left - border, 0, 2 * block + 2 * border, tile, colors['Black'])
                c.rect(right - border, 0, 2 * block + 2 * border, tile, colors['Black'])
            staggered_edge(c, left, block, length, white)
            staggered_edge(c, right,
                           block, length, white, mirror=True)
            if has_centre:
                if contrast:
                    c.rect(c.width / 2 - divider / 2 - border, 0,
                           divider + 2 * border, dash + border, colors['Black'])
                    c.rect(c.width / 2 - divider / 2 - border, tile - border,
                           divider + 2 * border, border, colors['Black'])
                c.rect(c.width / 2 - divider / 2, 0, divider, dash, white)
            centre_zh = '带0.15m分道虚线，实4.5m、空7.5m' if has_centre else '中央不自带分道线'
            centre_en = 'Includes 0.15 m lane divider, 4.5 m paint / 7.5 m gap' if has_centre else 'No centre divider'
            contrast_zh = '黑底棋盘' if contrast else '白色交错'
            contrast_en = ' Black Contrast' if contrast else ''
            contrast_note_zh = '白块间隙填黑，两侧黑边各0.15m；黑色外缘总宽增加0.30m。' if contrast else ''
            contrast_note_en = 'Black-filled gaps and 0.15 m borders; black outer-edge span is 0.30 m wider. ' if contrast else ''
            emit(region + ('_contrast' if contrast else '') + '_' + suffix,
                 f'Vehicle Crossing Preset {english} {label}{contrast_en} {tag}',
                 f'车辆道路穿越段预设 · {label} · {contrast_zh} · {chinese} · {road_width:g} m',
                 c, road_width + 2 * extra, tile,
                 f'两侧交错白块一次拉取，白色标线外缘总宽{road_width:g}m；每块长{length:g}m、单列厚{block:g}m，边线图样周期{2 * length:g}m，整套贴图周期{tile:g}m。{centre_zh}，铺装另画。{contrast_note_zh}遇航空器标线时整套分段留空，独立边线与7510可补齐局部。路宽及左右镜像同相位为包内预设。',
                 f'Both crossing edges in one draw, {road_width:g} m white outer-edge span; blocks {length:g} m long and {block:g} m wide, edge repeat {2 * length:g} m, combined tile {tile:g} m. {centre_en}; add pavement separately. {contrast_note_en}Leave gaps at aircraft markings; separate edges and 7510 can complete local sections. Width and mirrored in-phase layout are package presets.',
                 (FAA_CONTRAST if contrast else CAAM_CROSSING if region == 'caam' else FAA_MARKINGS) + '；' + FAA_WIDTHS,
                 'crossing_preset', lanes=lanes, road_width=road_width, pattern=label,
                 contrast=contrast, centre_line=has_centre)

    # Pipeline.output preserves --check's no-write behaviour for this manifest.
    from pathlib import Path
    output = Path(__file__).resolve().parents[1] / 'docs/service-roads.json'
    manifest = {'version': 1, 'width_definition': cfg['width_definition'],
                'crossing_centre': cfg['crossing_centre'],
                'assets': sorted(rows, key=lambda row: row['UiPriority'])}
    p.output(output, (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
