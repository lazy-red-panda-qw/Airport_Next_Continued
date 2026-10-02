"""ICAO runway-end NetLane artwork in metres; players choose length and direction."""
from __future__ import annotations

import math


def generate_runway_netlanes(p, Canvas, spec, colors, padding):
    cfg = spec['runway_netlane_additions']
    bar = cfg['threshold_bar_width_m']
    c = Canvas(bar + 2 * padding, 9)
    c.rect(padding, 0, bar, 9, colors['White'])
    p.asset('CustomNetlanes/RoadMarking/Displaced Threshold Bar 180cm',
            cfg['threshold_bar_priority'], c.width, c.height,
            '内移入口横条 · 连续 1.8 m',
            '白色连续横条，厚1.80m；沿跑道横向从一侧边缘拉到另一侧，长度由玩家决定。内移入口之前的白色箭头另放。',
            'ICAO Annex14 5.2.4.6/7、图5-4(B)；横向拉取，保留原5500独立Decal',
            canvas=c, period=9, painted=(bar, 9), draw_order=42,
            note_en='Continuous white 1.80 m thick displaced-threshold bar. Draw across the runway from edge to edge; add the preceding white arrows separately.')

    stroke = cfg['chevron_stroke_m']
    c = Canvas(stroke + 2 * padding, 9)
    c.rect(padding, 0, stroke, 9, colors['Yellow'])
    p.asset('CustomNetlanes/RoadMarking/Prethreshold Chevron Single Line 90cm',
            cfg['chevron_single_line_priority'], c.width, c.height,
            '前入口 V 形拼装单线 · 黄色 0.9 m',
            '独立黄色连续线，笔画宽0.90m、长度自由拉取。分别画两条与跑道轴线成45°的斜臂，玩家自行选择跨度、对齐尖角并按30m顶点周期复制；不捆绑另一臂，不用于机位引导。',
            'ICAO Annex14 7.3、图7-3的0.90m笔画；角度、两臂、距边及顶点间距由玩家布置',
            canvas=c, period=9, painted=(stroke, 9), draw_order=42,
            note_en='Independent continuous yellow 0.90 m stroke with freely drawn length. Draw each 45-degree arm separately, choose the span, align the apex and repeat at 30 m apex spacing. Does not include a second arm; not a stand guidance line.')
    period = cfg['chevron_period_m']
    edge = cfg['chevron_edge_clearance_m']
    cap = stroke / (2 * math.sqrt(2))
    half_vertical = stroke / math.sqrt(2)
    for index, width in enumerate(cfg['chevron_runway_widths_m']):
        c = Canvas(width, period, resolution=cfg['texture_px'])
        left, right, axis = edge + cap, width - edge - cap, width / 2
        depth = axis - left
        # Repeat neighbouring chevrons through the tile boundary. Polygon joints
        # keep the apex continuous; the ends are perpendicular butt caps.
        for copy in range(-2, 3):
            tip_y = period / 2 + copy * period
            vertices = [(axis, tip_y - half_vertical),
                        (right + cap, tip_y + depth - cap),
                        (right - cap, tip_y + depth + cap),
                        (axis, tip_y + half_vertical),
                        (left + cap, tip_y + depth + cap),
                        (left - cap, tip_y + depth - cap)]
            c.polygon(vertices, colors['Yellow'])
        p.asset(f'CustomNetlanes/RoadMarking/Prethreshold Chevrons Runway {width:g}m',
                cfg['chevron_priority_start'] + index, c.width, c.height,
                f'前入口非可用区域 V 形 · {width:g} m 跑道 · 30 m 周期',
                f'黄色45°V形，笔画0.90m、顶点纵向周期30m；适配{width:g}m宽道面，两侧漆边各留1.50m。沿中心线拉取并使尖端朝向跑道，端部位置按场地另定；不用于可正常起降滑行的内移入口段。',
                'ICAO Annex14 7.3、图7-3；30m顶点间距，漆边侧距1.5m为包内档位（图示≤7.5m）；非FAA专用EMAS图样',
                canvas=c, period=period,
                painted=(width - 2 * edge, period if depth + cap > period / 2 else
                         depth + cap + half_vertical), draw_order=42,
                note_en=f'Yellow 45-degree chevrons: 0.90 m strokes and 30 m apex spacing for a {width:g} m pavement, leaving 1.50 m at each painted side edge. Draw on the centre line with tips toward the runway; position the ends for the site. For unusable pre-threshold pavement, not a normally usable displaced-threshold section.')
