"""Validate 0.6.8 concrete and runway NetLanes against the game-tested old package."""
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
ASSETS = ROOT / 'Airport Decal Pack Countinue/CustomAssets'


def read(path):
    return json.loads(path.read_text('utf-8-sig'))


def runs(mask):
    changes = np.diff(np.r_[False, mask, False].astype(int))
    return list(zip(np.where(changes == 1)[0], np.where(changes == -1)[0]))


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def luminance(rgb):
    s = rgb.astype(float) / 255
    linear = np.where(s <= .04045, s / 12.92, ((s + .055) / 1.055) ** 2.4)
    return linear @ np.array([.2126, .7152, .0722])


def previews(baseline, rows):
    font = lambda size: ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', size)
    sheet = Image.new('RGB', (1500, 1400), (28, 32, 38))
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 15), '0.6.8 · 跑道端部可拉取标线', font=font(34), fill='white')
    draw.text((24, 64), '黄色V形：四个30m周期；白色横条：沿跑道横向拉取的独立NetLane', font=font(22), fill=(207, 214, 224))
    for i, priority in enumerate((5601, 5602, 5603)):
        r = next(r for r in rows if r['UiPriority'] == priority)
        width = {5601: 30, 5602: 45, 5603: 60}[priority]
        scale = 6
        x = 250 + i * 500 - width * scale / 2
        draw.text((i * 500 + 24, 108), f'{priority} · {width}m道面／漆宽{width - 3}m', font=font(23), fill='white')
        draw.rectangle((x, 155, x + width * scale, 890), fill=(65, 69, 71))
        tile = Image.open(ASSETS / r['path'] / '_BaseColorMap.png').convert('RGBA')
        tile = tile.resize((width * scale, 30 * scale), Image.Resampling.LANCZOS)
        for repeat in range(4):
            sheet.paste(tile, (round(x), 166 + repeat * 30 * scale), tile)
        bar = next(r for r in rows if r['UiPriority'] == 5501)
        im = Image.open(ASSETS / bar['path'] / '_BaseColorMap.png').convert('RGBA')
        im = im.resize((round(2.1 * scale), 9 * scale), Image.Resampling.LANCZOS).transpose(Image.Transpose.ROTATE_90)
        for offset in range(0, width * scale, 9 * scale):
            cropped = im.crop((0, 0, min(im.width, width * scale - offset), im.height))
            sheet.paste(cropped, (round(x + offset), 151), cropped)
    draw.text((24, 934), '尖端朝向跑道；横条与黄色V形分别选择，示意灰底不进入资产。', font=font(22), fill=(212, 220, 228))
    draw.text((24, 967), '端部片段与纹理起点需游戏摆放检查；宽长比真实，首次／重载周期待测。', font=font(20), fill=(190, 201, 213))
    draw.line((24, 1010, 1476, 1010), fill=(85, 95, 109), width=2)
    draw.text((24, 1030), '5604 · 独立黄色0.9m单线', font=font(28), fill='white')
    draw.text((24, 1090), '每条斜臂独立拉取；任意选择长度与跨度。', font=font(23), fill=(210, 220, 230))
    draw.text((24, 1135), '右侧为玩家用两条单线拼装的示意，', font=font(23), fill=(210, 220, 230))
    draw.text((24, 1170), '并非资产自带的整对V形。', font=font(23), fill=(210, 220, 230))
    r = next(r for r in rows if r['UiPriority'] == 5604)
    line = Image.open(ASSETS / r['path'] / '_BaseColorMap.png').convert('RGBA')
    tip = (1000, 1065)
    for end in ((775, 1290), (1225, 1290)):
        dx, dy = end[0] - tip[0], end[1] - tip[1]
        arm = line.resize((round(1.2 * scale), round(math.hypot(dx, dy))), Image.Resampling.LANCZOS)
        arm = arm.rotate(math.degrees(math.atan2(dx, dy)), Image.Resampling.BICUBIC, expand=True)
        centre = ((tip[0] + end[0]) / 2, (tip[1] + end[1]) / 2)
        sheet.paste(arm, (round(centre[0] - arm.width / 2), round(centre[1] - arm.height / 2)), arm)
    draw.text((710, 1335), '自选跨度示例：两臂各与轴线成45°；尖角接缝需游戏复核。', font=font(20), fill=(190, 201, 213))
    sheet.save(ROOT / 'docs/runway-netlane-preview.png')

    r = next(r for r in rows if r['UiPriority'] == 8160)
    sheet = Image.new('RGB', (1000, 640), (28, 32, 38))
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 15), '8160 · 强日照对比度调整：仅改基色', font=font(32), fill='white')
    for i, (label, folder) in enumerate((('0.6.7 · RGB155/153/145', baseline / 'LocalMod' / r['path']),
                                       ('0.6.8 · RGB128/126/118', ASSETS / r['path']))):
        x = 20 + i * 500
        draw.text((x, 66), label, font=font(24), fill=(216, 224, 232))
        im = Image.open(folder / '_BaseColorMap.png').convert('RGB').resize((460, 460), Image.Resampling.LANCZOS)
        sheet.paste(im, (x, 109))
        draw.rectangle((x + 35, 198, x + 425, 210), fill=(177, 177, 177))
        draw.rectangle((x + 35, 280, x + 425, 292), fill=(255, 239, 73))
        draw.text((x + 35, 334), '颗粒、法线、材质参数不变', font=font(23), fill=(177, 177, 177))
    draw.text((24, 589), '基色与标线叠放预览，未模拟游戏照明；白色保持RGB177。', font=font(21), fill=(210, 220, 230))
    sheet.save(ROOT / 'docs/concrete-contrast-preview.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    rows = read(ROOT / 'docs/asset-catalog.json')
    old = read(args.baseline / 'asset-catalog.json')
    by_path = {r['path']: r for r in rows}
    by_priority = {r['UiPriority']: r for r in rows}
    assert len(old) == 504 and len(rows) == len(by_path) == len(by_priority) == 508
    assert Counter(r['type'] for r in rows) == {'StaticObjectPrefab': 460, 'NetLaneGeometryPrefab': 39, 'SurfacePrefab': 9}
    assert {str(Path(r['path']).parent).replace('\\', '/') for r in rows} == {
        'CustomDecals/Alphabet', 'CustomDecals/RoadMarkings', 'CustomNetlanes/RoadMarking', 'Surfaces/Pavement'}
    concrete = by_priority[8160]
    retired = next(r for r in old if r['UiPriority'] == 5600)
    assert retired['path'] not in by_path and 5600 not in by_priority
    assert 5600 in read(ROOT / 'asset-specs.json')['reserved_removed_priorities']
    assert all(by_path[r['path']] == r for r in old if r['UiPriority'] not in (8160, 5600))
    for r in old:
        if r['UiPriority'] == 5600:
            continue
        current = by_path[r['path']]
        assert {k: v for k, v in current.items() if k not in ('notes', 'reference')} == {
            k: v for k, v in r.items() if k not in ('notes', 'reference')}
    assert len({r['prefab_name'] for r in rows}) == 508
    expected_new = {by_priority[p]['path'] for p in (5501, 5601, 5602, 5603, 5604)}
    assert set(by_path) - {r['path'] for r in old} == expected_new
    assert {r['path'] for r in old} - set(by_path) == {retired['path']}
    hashes_before = read(args.baseline / 'source-sha256.json')
    removed = [k for k in hashes_before if not (ASSETS / k).exists()]
    assert set(removed) == {k for k in hashes_before if k.startswith(retired['path'] + '/')}
    assert len(removed) == 3
    changed = [k for k, v in hashes_before.items() if k not in removed and file_hash(ASSETS / k) != v]
    expected_changed = {concrete['path'] + '/' + name for name in ('_BaseColorMap.png', 'icon.png')} | {
        'Localization/' + lang + '.json' for lang in ('en-US', 'zh-HANS', 'zh-HANT')}
    assert set(changed) == expected_changed, changed
    for lang in ('en-US', 'zh-HANS', 'zh-HANT'):
        before = read(args.baseline / 'LocalMod/Localization' / (lang + '.json'))
        after = read(ASSETS / 'Localization' / (lang + '.json'))
        assert len(before) == 1008 and len(after) == 1016
        retired_keys = {'Assets.' + kind + '[' + retired['prefab_name'] + ']' for kind in ('NAME', 'DESCRIPTION')}
        assert set(before) - set(after) == retired_keys
        assert {k for k in before if k in after and before[k] != after[k]} == {'Assets.DESCRIPTION[' + concrete['prefab_name'] + ']'}

    folder = ASSETS / concrete['path']
    before = np.asarray(Image.open(args.baseline / 'LocalMod' / concrete['path'] / '_BaseColorMap.png').convert('RGBA'))
    after = np.asarray(Image.open(folder / '_BaseColorMap.png').convert('RGBA'))
    assert before.shape == after.shape == (1024, 1024, 4)
    assert np.all(after[..., 3] == 255) and np.all(before[..., :3].astype(int) - after[..., :3].astype(int) == 27)
    assert np.max(np.abs(after[..., :3].mean(axis=(0, 1)) - [128, 126, 118])) < .02
    brightness_ratio = float(luminance(after[..., :3]).mean() / luminance(before[..., :3]).mean())
    assert .6 < brightness_ratio < .75
    assert read(ROOT / 'asset-specs.json')['palette']['White'] == [177, 177, 177]

    measurements = []
    for priority in (5501, 5601, 5602, 5603, 5604):
        r = by_priority[priority]
        folder = ASSETS / r['path']
        cfg, lane = read(folder / 'decal.json'), read(folder / 'netlane.json')
        assert lane['UiPriority'] == priority and cfg['Float']['_DrawOrder'] == 42
        assert not lane['curveProperties']['GeometryTiling'] and not lane['curveProperties']['StraightTiling']
        mesh = cfg['Vector']['colossal_MeshSize']
        data = np.asarray(Image.open(folder / '_BaseColorMap.png').convert('RGBA'))
        px, py = mesh['x'] / data.shape[1], mesh['z'] / data.shape[0]
        assert not np.any(data[:, 0, 3]) and not np.any(data[:, -1, 3])
        if priority in (5501, 5604):
            target = 1.8 if priority == 5501 else .9
            assert mesh['x'] == target + .3 and mesh['z'] == lane['curveProperties']['OverrideLength'] == 9
            rr = runs(data[data.shape[0] // 2, :, 3] >= 128)
            assert len(rr) == 1 and abs((rr[0][1] - rr[0][0]) * px - target) < 2 * px
            assert np.all(data[:, (rr[0][0] + rr[0][1]) // 2, 3] == 255)
            target_rgb = [177, 177, 177] if priority == 5501 else [255, 239, 73]
            # Measure the solid interior; RGBA resampling can overshoot RGB
            # at antialiased edges even where rounded alpha reaches 255.
            assert np.all(data[:, (rr[0][0] + rr[0][1]) // 2, :3] == target_rgb)
            measurements.append({'priority': priority, 'stroke_m': (rr[0][1] - rr[0][0]) * px})
        else:
            width = {5601: 30, 5602: 45, 5603: 60}[priority]
            assert data.shape[:2] == (2048, 2048)
            assert mesh['x'] == width and mesh['z'] == lane['curveProperties']['OverrideLength'] == 30
            strokes = []
            depth = width / 2 - 1.5 - .9 / (2 * math.sqrt(2))
            for fraction in (.25, .5, .75):
                y = 15 + depth * fraction
                row = int((y % 30) / py)
                rr = runs(data[row, :, 3] >= 128)
                # Use the two arms nearest the central chevron. Wrapped earlier
                # chevrons can also appear on very wide lanes near the tile end.
                centres = [(a + b) / 2 * px for a, b in rr]
                for x in (width / 2 - depth * fraction, width / 2 + depth * fraction):
                    nearest = min(range(len(rr)), key=lambda i: abs(centres[i] - x))
                    assert abs(centres[nearest] - x) < 2 * max(px, py)
                    a, b = rr[nearest]
                    stroke = (b - a) * px / math.sqrt(2)
                    assert abs(stroke - .9) < 2 * math.hypot(px, py)
                    strokes.append(stroke)
            opaque = data[..., 3] >= 128
            columns = np.where(opaque.any(axis=0))[0]
            assert abs(columns[0] * px - 1.5) < 2 * px
            assert abs((columns[-1] + 1) * px - (width - 1.5)) < 2 * px
            seam = float(np.abs(data[0, :, 3].astype(float) - data[-1, :, 3]).mean())
            nearby = np.abs(np.diff(data[..., 3].astype(float), axis=0)).mean(axis=1)
            assert seam <= max(nearby.max() * 1.5, 1), (priority, seam, nearby.max())
            measurements.append({'priority': priority, 'runway_width_m': width, 'painted_width_m': width - 3,
                                 'apex_period_m': 30, 'stroke_m': float(np.mean(strokes)), 'seam_mean_alpha_step': seam})

    report = {'version': '0.6.8', 'status': 'passed', 'assets': 508, 'revised': 1, 'added': 5, 'retired': 1,
              'unchanged_assets': 502, 'unchanged_source_files': len(hashes_before) - len(changed) - len(removed),
              'changed_old_source_files': changed, 'removed_old_source_files': removed,
              'all_retained_old_identities_preserved': True, 'retired_priority': 5600,
              'concrete_mean_rgb': after[..., :3].mean(axis=(0, 1)).tolist(),
              'albedo_linear_luminance_ratio': brightness_ratio, 'normal_and_material_unchanged': True,
              'entries_per_locale': 1016, 'preserved_old_entries_per_locale': 1005,
              'measurements': measurements, 'game_validation': 'pending; docs/test-round-9.md'}
    (ROOT / 'artifacts/qa-0.6.8.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    previews(args.baseline, rows)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
