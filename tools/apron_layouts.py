"""Flexible, manually placed apron bases; all coordinates are metres.

Aircraft envelopes and service reserves are separate geometry. Facility-specific
PBB and equipment markings belong to independent components, never the base.
Turning layouts use a conservative disk about any possible nosewheel position;
their radii are scenery presets, not inferred steering limits of game aircraft.
"""
from __future__ import annotations

import math


def polyline(c, points, width, color, closed=False):
    pairs = list(zip(points, points[1:]))
    if closed:
        pairs.append((points[-1], points[0]))
    for a, b in pairs:
        if math.dist(a, b) > 1e-8:
            c.stroke(a, b, width, color)


def clip_convex(subject, boundary):
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(boundary, boundary[1:] + boundary[:1]))
    sign = 1 if area > 0 else -1
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        def distance(point):
            return sign * ((b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]))
        output = []
        for previous, current in zip(subject[-1:] + subject[:-1], subject):
            da, db = distance(previous), distance(current)
            if (da >= 0) != (db >= 0):
                t = da / (da - db)
                output.append(tuple(previous[i] + t * (current[i] - previous[i]) for i in (0, 1)))
            if db >= 0:
                output.append(current)
        subject = output
        if not subject:
            break
    return subject


def hatch(c, vertices, palette, stroke=0.1, gap=0.75, angle=45, border=True):
    a = math.radians(angle)
    nx, ny = math.cos(a), math.sin(a)
    tx, ty = -ny, nx
    projections = [x * nx + y * ny for x, y in vertices]
    reach = 4 * max(max(abs(x), abs(y)) for x, y in vertices) + 10
    for index in range(math.floor(min(projections) / (stroke + gap)) - 1,
                       math.ceil(max(projections) / (stroke + gap)) + 2):
        offset = index * (stroke + gap)
        points = [(nx * (offset + side * stroke / 2) + tx * tangent * reach,
                   ny * (offset + side * stroke / 2) + ty * tangent * reach)
                  for side, tangent in ((1, -1), (1, 1), (-1, 1), (-1, -1))]
        clipped = clip_convex(points, vertices)
        if clipped:
            c.polygon(clipped, palette["Red"])
    if border:
        polyline(c, vertices, stroke, palette["Red"], closed=True)
    return {"vertices_m": vertices, "stroke_m": stroke, "clear_gap_m": gap, "angle_degrees": angle}


def box(c, rect, stroke, ink):
    x, y, w, h = rect
    polyline(c, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], stroke, ink, closed=True)


def guidance(c, points, stroke, colors):
    polyline(c, points, stroke + 0.15, colors["Black"])
    polyline(c, points, stroke, colors["Yellow"])


def ground_layout(profile, spec, Canvas, colors, padding, stamp):
    padding = max(padding, 0.35)
    cfg = spec["apron_layouts"]
    kind = profile["layout"]
    clearance = spec["stand_presets"]["clearances_m"][profile["code"]]
    inner_w = profile["span_m"] + 2 * clearance
    inner_h = profile["length_m"] + 2 * clearance
    lane = cfg["left_service_strip_width_m"] if kind != "ga" else 3.0
    equipment_width = cfg["right_service_strip_width_m"] if kind != "ga" else 5.0
    head = 10.0 if kind == "ga" else 12.0
    core_x, core_w = padding + lane, inner_w + 0.2
    core_end = padding + head + inner_h + 0.2
    rear = core_end + 0.8
    width = lane + core_w + equipment_width + 2 * padding
    height = rear + cfg["lead_extension_m"] + padding
    c = Canvas(width, height, resolution=profile["texture_px"])
    axis = core_x + core_w / 2
    chamfer = min(8.0, core_w * 0.2, head - 1)
    safety = [(core_x, padding + chamfer), (core_x + chamfer, padding),
              (core_x + core_w - chamfer, padding), (core_x + core_w, padding + chamfer),
              (core_x + core_w, core_end), (core_x, core_end)]
    hatches = []
    for vertices in (
        [(core_x, padding), (core_x + chamfer, padding), (core_x, padding + chamfer)],
        [(core_x + core_w - chamfer, padding), (core_x + core_w, padding), (core_x + core_w, padding + chamfer)]):
        hatches.append(hatch(c, vertices, colors))
    # Basic apron boundary and service reserves; no airport-specific zigzag,
    # double back-of-stand boundary, bridge sweep or fixed equipment bays.
    outer = [(padding, rear), (padding, padding), (width - padding, padding), (width - padding, rear)]
    polyline(c, outer, 0.25, colors["Black"])
    polyline(c, outer, 0.15, colors["White"])
    c.stroke((padding, rear), (width - padding, rear), 0.25, colors["Black"])
    c.stroke((padding, rear), (width - padding, rear), 0.15, colors["White"])
    polyline(c, safety[:4], 0.1, colors["Red"])
    for edge in ((safety[0], safety[-1]), (safety[3], safety[4]),
                 (safety[-1], (axis - 3, core_end)), ((axis + 3, core_end), safety[4])):
        c.stroke(*edge, 0.1, colors["Red"])
    access = [padding + 0.25, padding + chamfer + 0.5, lane - 0.5, rear - padding - chamfer - 1]
    right_reserve = [core_x + core_w + .25, access[1], equipment_width - .5, access[3]]
    for x in (core_x - .35, core_x + core_w + .35):
        c.stroke((x, access[1]), (x, rear), .25, colors["Black"])
        c.stroke((x, access[1]), (x, rear), .15, colors["White"])
    gap_end = core_end - 1.0
    gap_start = gap_end - 3.0
    for start, end in ((padding + head - 2, gap_start), (gap_end, height - padding)):
        guidance(c, [(axis, start), (axis, end)], profile["lead_width_m"], colors)
    return c, {"layout": kind, "clearance_m": clearance, "inner_m": [inner_w, inner_h],
               "axis_x_m": axis, "nose_reference_y_m": padding + head + clearance + 0.1,
               "aircraft_rect_m": [core_x + clearance + 0.1, padding + head + clearance + 0.1,
                                   profile["span_m"], profile["length_m"]],
               "safety_polygon_m": safety, "hatches": hatches, "equipment_rects_m": [],
               "clearway_rect_m": access, "service_strips_m": [access, right_reserve],
               "bridges": [], "head_service_depth_m": head, "facilities": "independent components",
               "rear_boundary_y_m": rear, "id_gap_y_m": [gap_start, gap_end],
               "lead_width_m": profile["lead_width_m"], "safety_line_m": 0.1,
               "stop_datum": "separate; place for actual nosewheel/cockpit"}


def hull(points):
    points = sorted(set(points))
    def cross(a, b, p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    def half(items):
        result = []
        for point in items:
            while len(result) > 1 and cross(result[-2], result[-1], point) <= 0:
                result.pop()
            result.append(point)
        return result
    return half(points)[:-1] + half(reversed(points))[:-1]


def curved_layout(profile, spec, Canvas, colors, padding, stamp):
    padding = max(padding, 0.35)
    clearance = spec["stand_presets"]["clearances_m"][profile["code"]]
    radius = 12.0
    path = [(0, 20), (0, 0)]
    path += [(radius + radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a)))
             for a in range(181, 406)]
    end = path[-1]
    path.append((end[0] - 8 / math.sqrt(2), end[1] + 8 / math.sqrt(2)))
    # Any point of an L x S aircraft with its nosewheel anywhere on its
    # longitudinal axis lies in this disk. No guessed game wheelbase is used.
    disk = math.hypot(profile["length_m"], profile["span_m"] / 2)
    buffer = (disk + clearance + 0.1) / math.cos(math.pi / 48)
    envelope = hull([(x + buffer * math.cos(i * math.tau / 48), y + buffer * math.sin(i * math.tau / 48))
                     for x, y in path for i in range(48)])
    min_x, max_x = min(x for x, y in path), max(x for x, y in path)
    min_y, max_y = min(y for x, y in path), max(y for x, y in path)
    shift_x, shift_y = padding - min_x, padding - min_y
    path = [(x + shift_x, y + shift_y) for x, y in path]
    envelope = [(x + shift_x, y + shift_y) for x, y in envelope]
    width = max_x - min_x + 2 * padding
    height = max_y - min_y + 2 * padding
    c = Canvas(width, height, resolution=2048)
    guidance(c, path, profile["lead_width_m"], colors)
    # Exit arrow follows the lead-out direction; stop and turn bars stay separate.
    tip = path[-1]
    dx, dy = (tip[0] - path[-2][0]) / 8, (tip[1] - path[-2][1]) / 8
    arrow = [tip, (tip[0] - 2 * dx - dy, tip[1] - 2 * dy + dx),
             (tip[0] - 2 * dx + dy, tip[1] - 2 * dy - dx)]
    c.polygon(arrow, colors['Yellow'])
    return c, {"layout": profile["layout"], "clearance_m": clearance,
               "inner_m": [profile["span_m"] + 2 * clearance, profile["length_m"] + 2 * clearance],
               "path_m": path, "path_radius_m": radius,
               "aircraft_disk_m": disk, "movement_polygon_m": envelope,
               "equipment_rects_m": [], "clearway_rect_m": None, "service_strips_m": [],
               "painted_movement_boundary": False, "direction_arrows_m": [arrow],
               "facilities": "independent components",
               "hatches": [], "bridges": [], "lead_width_m": profile["lead_width_m"],
               "safety_line_m": 0.1,
               "stop_datum": "separate; turning radius is a scenery preset, not a universal steering limit"}


def through_layout(profile, spec, Canvas, colors, padding, stamp):
    padding = max(padding, .35)
    clearance = spec['stand_presets']['clearances_m'][profile['code']]
    inner_w = profile['span_m'] + 2 * clearance
    inner_h = profile['length_m'] + 2 * clearance
    lane, right = 3.0, 5.0
    extension = spec['apron_layouts']['lead_extension_m']
    core_x, core_y, core_w = padding + lane, padding + extension, inner_w + .2
    core_end = core_y + inner_h + .2
    width, height = lane + core_w + right + 2 * padding, core_end + extension + padding
    c = Canvas(width, height, resolution=2048)
    axis = core_x + core_w / 2
    safety = [(core_x, core_y), (core_x + core_w, core_y), (core_x + core_w, core_end), (core_x, core_end)]
    for x in (core_x, core_x + core_w):
        c.stroke((x, core_y), (x, core_end), .1, colors['Red'])
    for x in (padding, core_x - .35, core_x + core_w + .35, width - padding):
        c.stroke((x, core_y), (x, core_end), .25, colors['Black'])
        c.stroke((x, core_y), (x, core_end), .15, colors['White'])
    gap_end, gap_start = core_end - 1, core_end - 4
    guidance(c, [(axis, padding), (axis, gap_start)], profile['lead_width_m'], colors)
    guidance(c, [(axis, gap_end), (axis, height - padding)], profile['lead_width_m'], colors)
    arrow = [(axis, padding + 2), (axis - 1, padding + 4), (axis + 1, padding + 4)]
    c.polygon(arrow, colors['Yellow'])
    left_reserve = [padding + .25, core_y + .25, lane - .5, inner_h - .3]
    right_reserve = [core_x + core_w + .25, core_y + .25, right - .5, inner_h - .3]
    return c, {'layout': 'through', 'clearance_m': clearance, 'inner_m': [inner_w, inner_h],
               'axis_x_m': axis, 'nose_reference_y_m': core_y + clearance + .1,
               'aircraft_rect_m': [core_x + clearance + .1, core_y + clearance + .1,
                                   profile['span_m'], profile['length_m']],
               'safety_polygon_m': safety, 'painted_safety_edges': [1, 3],
               'open_ends': True, 'external_taxilane_curves': 'not included; connect separately',
               'hatches': [], 'equipment_rects_m': [], 'bridges': [],
               'clearway_rect_m': left_reserve, 'service_strips_m': [left_reserve, right_reserve],
               'id_gap_y_m': [gap_start, gap_end], 'lead_width_m': profile['lead_width_m'],
               'direction_arrows_m': [arrow], 'facilities': 'independent components',
               'head_service_depth_m': 0, 'stop_datum': 'separate; straight parking segment only'}


def make_layout(profile, spec, Canvas, colors, padding, stamp):
    if profile['layout'] == 'through':
        return through_layout(profile, spec, Canvas, colors, padding, stamp)
    if profile["layout"] == "loop":
        return curved_layout(profile, spec, Canvas, colors, padding, stamp)
    return ground_layout(profile, spec, Canvas, colors, padding, stamp)
