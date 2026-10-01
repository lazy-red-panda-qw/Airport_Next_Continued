"""Independent geometry/raster QA for the flexible 0.6.7 apron layouts."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'Airport Decal Pack Countinue/CustomAssets'


def read(path):
    return json.loads(path.read_text('utf-8-sig'))


def check(value, message):
    if not value:
        raise AssertionError(message)


def segments(polygon):
    return list(zip(polygon, polygon[1:] + polygon[:1]))


def point_segment(point, a, b):
    v = (b[0] - a[0], b[1] - a[1])
    denominator = v[0] ** 2 + v[1] ** 2
    t = max(0, min(1, ((point[0] - a[0]) * v[0] + (point[1] - a[1]) * v[1]) / denominator))
    return math.dist(point, (a[0] + t * v[0], a[1] + t * v[1]))


def rect_vertices(rect):
    x, y, w, h = rect
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def separation(rect, points):
    corners = rect_vertices(rect)
    return min([point_segment(p, a, b) for p in corners for a, b in segments(points)] +
               [point_segment(p, a, b) for p in points for a, b in segments(corners)])


def inside_convex(point, polygon):
    crosses = [(b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
               for a, b in segments(polygon)]
    return all(v >= -1e-8 for v in crosses) or all(v <= 1e-8 for v in crosses)


def overlap_convex(first, second):
    # Separating-axis check also catches crossing edges and full containment.
    for a, b in segments(first) + segments(second):
        axis = (a[1] - b[1], b[0] - a[0])
        p = [x * axis[0] + y * axis[1] for x, y in first]
        q = [x * axis[0] + y * axis[1] for x, y in second]
        if max(p) < min(q) or max(q) < min(p):
            return False
    return True


def color(data, name, palette):
    rgb = data[..., :3].astype(np.int32)
    distance = np.sum((rgb - palette[name]) ** 2, axis=-1)
    mask = data[..., 3] >= 128
    for other, value in palette.items():
        if name != other:
            mask &= distance < np.sum((rgb - value) ** 2, axis=-1)
    return mask


def runs(mask):
    changes = np.diff(np.r_[False, mask, False].astype(int))
    return list(zip(np.where(changes == 1)[0], np.where(changes == -1)[0]))


def inspect(r, palette):
    profile = r['profile']
    limits = {'A': (0, 15), 'B': (15, 24), 'C': (24, 36), 'D': (36, 52), 'E': (52, 65), 'F': (65, 80)}
    low, high = limits[profile['code']]
    check(low <= profile['span_m'] < high, 'Wrong wingspan code')
    clearance = {'A': 3, 'B': 3, 'C': 4.5, 'D': 7.5, 'E': 7.5, 'F': 7.5}[profile['code']]
    check(r['clearance_m'] == clearance and r['stop_datum'].startswith('separate'), 'Wrong clearance/stop assumptions')
    measured = {'priority': r['UiPriority'], 'layout': r['layout']}
    if 'aircraft_rect_m' in r:
        aircraft = r['aircraft_rect_m']
        check(aircraft[2:] == [profile['span_m'], profile['length_m']], 'Game aircraft dimensions changed')
        check(all(inside_convex(p, r['safety_polygon_m']) for p in rect_vertices(aircraft)), 'Aircraft outside safety boundary')
        distances = [separation(aircraft, r['safety_polygon_m'])]
        for rect in r['service_strips_m']:
            check(not overlap_convex(rect_vertices(aircraft), rect_vertices(rect)), 'Service area overlaps aircraft')
            distances.append(separation(aircraft, rect_vertices(rect)))
        for hatch in r['hatches']:
            check(not overlap_convex(rect_vertices(aircraft), hatch['vertices_m']), 'No-parking hatch overlaps aircraft')
            distances.append(separation(aircraft, hatch['vertices_m']))
        for bridge in r['bridges']:
            x, y = bridge['wheel_center_m']
            ax, ay, w, h = aircraft
            distance = math.hypot(max(ax - x, x - ax - w, 0), max(ay - y, y - ay - h, 0)) - bridge['wheel_outer_m'] / 2
            distances.append(distance)
            check(bridge['origin_m'][1] < ay - clearance + .05, 'PBB sweep starts inside aircraft envelope')
        check(min(distances) >= clearance + 0.04, f"{r['path']}: clearances {distances}")
        measured['min_parked_clearance_m'] = round(min(distances) - .05, 5)
        if r['layout'] != 'through':
            check(aircraft[1] - .35 >= 12, 'Less than 12m nose/head setback')
        else:
            check(r['open_ends'] and r['painted_safety_edges'] == [1, 3] and 'path_m' not in r,
                  'Through stand includes a curved taxilane or end wall')
    else:
        polygon = r['movement_polygon_m']
        disk = math.hypot(profile['length_m'], profile['span_m'] / 2)
        check(all(inside_convex(p, polygon) for p in r['path_m']), 'Guidance outside movement envelope')
        minimum = min(point_segment(p, a, b) for p in r['path_m'] for a, b in segments(polygon)) - disk - .05
        check(minimum >= clearance, f"Curve swept disk clearance {minimum}")
        measured['conservative_movement_clearance_m'] = round(minimum, 5)
        check(not r['painted_movement_boundary'] and r['clearway_rect_m'] is None, 'Open loop has a perimeter/clearway')
    folder = ASSETS / r['path']
    config = read(folder / 'decal.json')
    mesh = config['Vector']['colossal_MeshSize']
    check(np.allclose([mesh['x'], mesh['z']], r['mesh_m'], rtol=0, atol=1e-6), 'Wrong projected dimensions')
    check(config['UiPriority'] == r['UiPriority'] and config['Float']['_DrawOrder'] == 41, 'Wrong menu/layer')
    data = np.asarray(Image.open(folder / '_BaseColorMap.png').convert('RGBA'))
    height, width = data.shape[:2]
    check(width == height == r['texture_px'], 'Wrong resolution')
    check(not np.any(data[0, :, 3]) and not np.any(data[-1, :, 3]) and not np.any(data[:, 0, 3]) and not np.any(data[:, -1, 3]), 'Paint clips the texture edge')
    px, py = r['mesh_m'][0] / width, r['mesh_m'][1] / height
    if 'aircraft_rect_m' in r:
        row = int((r['aircraft_rect_m'][1] + profile['length_m'] / 2) / py)
        rr = runs(color(data[row], 'Yellow', palette))
        check(len(rr) == 1, 'Unexpected guidance count')
        actual = (rr[0][1] - rr[0][0]) * px
        for y in np.linspace(*r['id_gap_y_m'], 11)[1:-1]:
            check(not color(data[int(y / py), int(r['axis_x_m'] / px)], 'Yellow', palette), 'ID gap filled')
    else:
        a, b = r['path_m'][:2]
        if abs(a[0] - b[0]) < 1e-6:
            row = int((a[1] + b[1]) / 2 / py)
            rr = runs(color(data[row], 'Yellow', palette))
            rr = min(rr, key=lambda pair: abs((pair[0] + pair[1]) / 2 * px - a[0]))
            actual = (rr[1] - rr[0]) * px
        else:
            col = int((a[0] + b[0]) / 2 / px)
            rr = runs(color(data[:, col], 'Yellow', palette))
            rr = min(rr, key=lambda pair: abs((pair[0] + pair[1]) / 2 * py - a[1]))
            actual = (rr[1] - rr[0]) * py
    check(abs(actual - r['lead_width_m']) < max(px, py) * 1.6, f"Wrong painted guidance width: {actual}")
    measured['guidance_width_m'] = round(actual, 5)
    for bridge in r['bridges']:
        x, y = bridge['wheel_center_m']
        check(list(data[int(y / py), int(x / px), :3]) == [177, 177, 177], 'PBB white changed')
    hatch_results = []
    for hatch in r['hatches']:
        vertices = hatch['vertices_m']
        x0, y0 = min(x for x, y in vertices), min(y for x, y in vertices)
        extent = max(x for x, y in vertices) - x0
        y = y0 + extent * .2
        intersections = [a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0])
                         for a, b in segments(vertices) if a[1] != b[1] and min(a[1], b[1]) <= y <= max(a[1], b[1])]
        xs = np.arange(min(intersections) + .25, max(intersections) - .25, px)
        mask = color(data[int(y / py), (xs / px).astype(int)], 'Red', palette)
        rr = [pair for pair in runs(mask) if pair[0] > 0 and pair[1] < len(mask)]
        check(len(rr) > 0 and np.any(~mask), 'Hatching empty/opaque')
        ink = float(np.median([(b - a) * px / math.sqrt(2) for a, b in rr]))
        check(abs(ink - .1) < 2 * math.hypot(px, py), f"Bad diagonal width {ink}")
        item = {'stroke_m': round(ink, 5)}
        if len(rr) >= 2:
            period = float(np.median([(rr[i+1][0] - rr[i][0]) * px / math.sqrt(2) for i in range(len(rr)-1)]))
            gap = period - ink
            check(abs(gap - .75) < 2 * math.hypot(px, py), f"{r['path']}: Bad transparent gap {gap}; runs={rr}; extent={extent}; x={x0}; y={y}")
            item['clear_gap_m'] = round(gap, 5)
        hatch_results.append(item)
    measured['hatches'] = hatch_results
    check(not r['equipment_rects_m'] and not r['bridges'] and r['facilities'] == 'independent components',
          'Base includes fixed bridge/equipment placement')
    if r['layout'] == 'loop':
        # Black/yellow antialias blends can be nearer to red/grey in RGB distance.
        # Detect actual red/white ink, rather than assigning every blend a label.
        rgb = data[..., :3].astype(np.int32)
        for name in ('Red', 'White'):
            core_ink = (data[..., 3] >= 128) & (np.sum((rgb - palette[name]) ** 2, axis=-1) < 20 ** 2)
            check(not np.any(core_ink), 'Loop contains painted boundary/facility markings')
    return measured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    old = read(args.baseline / 'asset-catalog.json')
    rows = read(ROOT / 'docs/asset-catalog.json')
    check(len(old) == 500 and len(rows) == 504, 'Wrong counts')
    current = {r['path']: r for r in rows}
    changed = {r['path'] for r in old if 7700 <= r['UiPriority'] <= 7770}
    check(len(changed) == 8, 'Unexpected changed set')
    check(all(current[r['path']] == r for r in old if r['path'] not in changed), 'Existing asset record changed')
    check(all(current[r['path']]['prefab_name'] == r['prefab_name'] for r in old), 'Existing prefab identity changed')
    check(Counter(r['type'] for r in rows) == {'StaticObjectPrefab': 461, 'NetLaneGeometryPrefab': 34, 'SurfacePrefab': 9}, 'Wrong types')
    check(len({r['UiPriority'] for r in rows}) == len(rows) == len({r['prefab_name'] for r in rows}), 'Duplicate identity/priority')
    check({str(Path(r['path']).parent).replace('\\', '/') for r in rows} == {'CustomDecals/Alphabet', 'CustomDecals/RoadMarkings', 'CustomNetlanes/RoadMarking', 'Surfaces/Pavement'}, 'New menu category')
    skip_locale = {f'Assets.{field}[{r["prefab_name"]}]' for r in old if r['path'] in changed for field in ('NAME', 'DESCRIPTION')}
    preserved_files = 0
    for rel, expected in read(args.baseline / 'source-sha256.json').items():
        if rel.startswith('Localization/'):
            before, after = read(args.baseline / 'LocalMod' / rel), read(ASSETS / rel)
            check(len(after) == 1008 and all(after.get(k) == v for k, v in before.items() if k not in skip_locale), 'Unrelated locale value changed')
        elif str(Path(rel).parent).replace('\\', '/') not in changed:
            check(hashlib.sha256((ASSETS / rel).read_bytes()).hexdigest() == expected, f'Unrelated file changed: {rel}')
            preserved_files += 1
    records = read(ROOT / 'docs/stand-presets.json')['assets']
    layouts = [r for r in records if r['kind'] == 'stand']
    check(len(layouts) == 10 and len(set(current) - {r['path'] for r in old}) == 4, 'Wrong layouts')
    palette = read(ROOT / 'asset-specs.json')['palette']
    measurements = [inspect(r, palette) for r in layouts]
    optional_shapes = [r for r in records if r['kind'] == 'no_parking_shape']
    check(len(optional_shapes) == 2, 'Missing optional non-starburst shapes')
    for r in optional_shapes:
        folder = ASSETS / r['path']
        cfg = read(folder / 'decal.json')
        check(cfg['Float']['_DrawOrder'] == 40 and cfg['UiPriority'] == r['UiPriority'], 'Wrong optional hatch layer/priority')
        data = np.asarray(Image.open(folder / '_BaseColorMap.png').convert('RGBA'))
        check(data.shape[:2] == (2048, 2048), 'Wrong optional hatch resolution')
        check(not np.any(data[0, :, 3]) and not np.any(data[-1, :, 3]) and not np.any(data[:, 0, 3]) and not np.any(data[:, -1, 3]), 'Optional hatch clips edge')
        px, py = r['mesh_m'][0] / 2048, r['mesh_m'][1] / 2048
        mask = color(data, 'Red', palette)
        # Interior scan independently measures diagonal bands, excluding outline.
        hatch_results = []
        for part in r['hatches']:
            polygon = part['vertices_m']
            y = min(y for x, y in polygon) + .8
            intersections = [a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0])
                             for a, b in segments(polygon) if a[1] != b[1] and min(a[1], b[1]) <= y <= max(a[1], b[1])]
            left, right = int((min(intersections) + .3) / px), int((max(intersections) - .3) / px)
            rr = [pair for pair in runs(mask[int(y / py), left:right]) if pair[0] > 0 and pair[1] < right - left]
            check(len(rr) >= 2, 'Optional shape has no repeated hatching')
            stroke = float(np.median([(b - a) * px / math.sqrt(2) for a, b in rr]))
            period = float(np.median([(rr[i+1][0] - rr[i][0]) * px / math.sqrt(2) for i in range(len(rr)-1)]))
            check(abs(stroke - .1) < 2 * math.hypot(px, py) and abs(period - stroke - .75) < 2 * math.hypot(px, py), 'Optional hatch width/gap wrong')
            hatch_results.append({'stroke_m': round(stroke, 5), 'clear_gap_m': round(period - stroke, 5)})
        check(data[int(4.4 / py), int(.5 / px), 3] == 0 if r['UiPriority'] == 7832 else
              data[int(4.4 / py), int(8.4 / px), 3] == 0, 'Unpainted outside/notch filled')
        measurements.append({'priority': r['UiPriority'], 'kind': 'optional_hatch', 'hatches': hatch_results})
    report = {'version': '0.6.7', 'status': 'passed', 'assets': 504, 'revised': 8, 'added': 4,
              'unchanged_assets': 492, 'unchanged_asset_files': preserved_files, 'all_old_identities_preserved': True,
              'measurements': measurements, 'game_validation': 'pending; docs/test-round-8.md'}
    (ROOT / 'artifacts/qa-0.6.7.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: 504 assets, 10 flexible bases / 2 optional hatch shapes, 492 unchanged assets / {preserved_files} files, all old identities preserved.')


if __name__ == '__main__':
    main()
