"""Round-10 checks: real raster dimensions, UV repeats and baseline preservation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'Airport Decal Pack Countinue/CustomAssets'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def runs(mask):
    changes = np.diff(np.r_[False, mask, False].astype(int))
    return list(zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads((args.baseline / 'baseline.json').read_text('utf-8-sig'))
    old_rows = json.loads((args.baseline / 'asset-catalog.json').read_text('utf-8'))
    rows = json.loads((ROOT / 'docs/asset-catalog.json').read_text('utf-8'))
    manifest = json.loads((ROOT / 'docs/service-roads.json').read_text('utf-8'))
    cfg = json.loads((ROOT / 'asset-specs.json').read_text('utf-8'))
    by_id = {r['UiPriority']: r for r in rows}
    expected = {7500, 7510, 7520, 7521, 7522, 7530, 7540, 7541, 7550, 7551, 7560, 7561, 7570, 7571}
    assert len(rows) == 520 and len(by_id) == 520
    assert Counter(r['type'] for r in rows) == {
        'StaticObjectPrefab': 460, 'NetLaneGeometryPrefab': 53, 'SurfacePrefab': 7}
    assert {r['UiPriority'] for r in manifest['assets']} == expected
    assert {r['UiPriority'] for r in rows} - {r['UiPriority'] for r in old_rows} == expected
    for old in old_rows:
        assert by_id[old['UiPriority']] == old, f"Old catalog row changed: {old['UiPriority']}"
    unchanged = 0
    for relative, sha in baseline['SourceHashes'].items():
        if relative.replace('\\', '/').startswith('Localization/'):
            continue
        assert digest(ASSETS / relative) == sha, f'Old runtime asset changed: {relative}'
        unchanged += 1
    for relative, sha in baseline['ProtectedUserHashes'].items():
        assert digest(ROOT / relative) == sha, f'User file changed: {relative}'
    locale_counts = {}
    for locale in ('zh-HANS', 'zh-HANT', 'en-US'):
        old = json.loads((args.baseline / 'CustomAssets/Localization' / (locale+'.json')).read_text('utf-8'))
        new = json.loads((ASSETS / 'Localization' / (locale+'.json')).read_text('utf-8'))
        assert len(new) == 1040 and all(new[k] == v for k, v in old.items())
        for asset_id in expected:
            row = by_id[asset_id]
            text = new[f"Assets.DESCRIPTION[{row['prefab_name']}]"]
            fields = ('Description:', 'Specifications:', 'Use:') if locale == 'en-US' else ('描述：', '規格：', '作用：') if locale == 'zh-HANT' else ('描述：', '规格：', '作用：')
            assert all(field in text for field in fields), (locale, asset_id, text)
        locale_counts[locale] = len(new)
    # Test builds retain the author's whole publication configuration byte for byte.
    assert (args.baseline / 'PublishConfiguration.xml').read_bytes() == (
        ROOT / 'Airport Decal Pack Countinue/Properties/PublishConfiguration.xml').read_bytes()
    project = ET.parse(ROOT / 'Airport Decal Pack Countinue/Airport Details Pack Countinue.csproj').getroot()
    assert project.find('PropertyGroup/AssemblyVersion').text == '0.7.1.0'
    assert cfg['palette']['White'] == [177, 177, 177]
    measurements = []
    for item in manifest['assets']:
        row = by_id[item['UiPriority']]
        folder = ASSETS / item['path']
        decal = json.loads((folder / 'decal.json').read_text('utf-8'))
        lane = json.loads((folder / 'netlane.json').read_text('utf-8'))
        mesh = decal['Vector']['colossal_MeshSize']
        assert mesh['z'] == lane['curveProperties']['OverrideLength'] == item['tile_period_m']
        assert lane['UiPriority'] == item['UiPriority'] and 'UiPriority' not in decal
        assert decal['Float']['_DrawOrder'] == 42
        pixels = np.asarray(Image.open(folder / '_BaseColorMap.png').convert('RGBA'))
        alpha = pixels[:, :, 3] >= 128
        # White paint is distinct from black contrast even when both are opaque.
        white = alpha & (pixels[:, :, :3].mean(axis=2) >= 88.5)
        for mask, rgb in ((white, 177), (alpha & ~white, 0)):
            if rgb == 0 and not item['contrast']:
                continue
            interior = mask & (pixels[:, :, 3] == 255)
            for axis in (0, 1):
                for offset in (-3, -2, -1, 1, 2, 3):
                    interior &= np.roll(mask, offset, axis=axis)
            assert interior.any() and np.all(pixels[interior, :3] == rgb), (item['UiPriority'], rgb)
        px = mesh['x'] / alpha.shape[1]
        pz = mesh['z'] / alpha.shape[0]
        report = {'UiPriority': item['UiPriority'], 'period_m': mesh['z']}
        for phase in (.25, .75):
            bands = runs(white[min(int(phase * alpha.shape[0]), alpha.shape[0]-1)])
            widths = [(b-a)*px for a, b in bands]
            role = item['role']
            if role == 'divider':
                target, count = .15, 1 if phase == .25 else 0
            elif role == 'stop':
                target, count = .6, 1
            elif role == 'edge':
                target, count = .15, 1
            elif role == 'normal_preset':
                target = .15
                count = 3 if item['lanes'] == 2 and phase == .25 else 2
            else:
                target = .1 if item['pattern'] == 'CAAM' else .3
                count = 1 if role == 'crossing_edge' else 2
                if item['centre_line'] and phase == .25:
                    count += 1
            assert len(widths) == count, (item['UiPriority'], phase, widths)
            targets = [target] * count
            if role == 'crossing_preset' and item['centre_line'] and phase == .25:
                targets[1] = .15
            assert all(abs(w-t) <= 2.1*px for w, t in zip(widths, targets)), (item['UiPriority'], widths, targets)
            report[str(phase)] = widths
        if item['centre_line']:
            mid = white[:, white.shape[1]//2]
            paint = runs(mid)
            assert len(paint) == 1 and abs((paint[0][1]-paint[0][0])*pz - 4.5) <= 2.1*pz
            report['dash_m'] = (paint[0][1]-paint[0][0])*pz
            report['gap_m'] = mesh['z'] - report['dash_m']
        if item['role'] == 'crossing_edge':
            a = runs(white[white.shape[0]//4])[0]
            b = runs(white[3*white.shape[0]//4])[0]
            shift = abs((sum(a)-sum(b))/2*px)
            target = .1 if item['pattern'] == 'CAAM' else .3
            assert abs(shift-target) <= 2.1*px
        if item['role'].startswith('crossing'):
            length = 1.0 if item['pattern'] == 'CAAM' else 1.2
            edge_period = 2 * length
            # Check actual white blocks along an edge, including five repeats in
            # the 12 m FAA two-lane texture, independently of its centre divider.
            sample_row = round(length / 2 / mesh['z'] * white.shape[0])
            a, b = runs(white[sample_row])[0]
            blocks = runs(white[:, (a+b)//2])
            assert len(blocks) == round(mesh['z']/edge_period), (item['UiPriority'], blocks)
            assert all(abs((end-start)*pz-length) <= 2.1*pz for start, end in blocks)
            report['edge_repeat_m'] = edge_period
            report['block_length_m'] = (blocks[0][1]-blocks[0][0])*pz
            if item['contrast'] and item['role'] == 'crossing_edge':
                x = np.flatnonzero(alpha.any(axis=0))
                span = (x[-1]-x[0]+1)*px
                assert abs(span-.9) <= 2.1*px
                report['black_band_width_m'] = span
        if item['role'] == 'crossing_preset' and not item['centre_line']:
            assert not alpha[:, alpha.shape[1]//2].any()
        if item['road_width_m']:
            x = np.flatnonzero(white.any(axis=0))
            span = (x[-1]-x[0]+1)*px
            assert abs(span-item['road_width_m']) <= 2.1*px
            report['outer_edge_span_m'] = span
            if item['contrast']:
                x = np.flatnonzero(alpha.any(axis=0))
                black_span = (x[-1]-x[0]+1)*px
                assert abs(black_span-item['road_width_m']-.3) <= 2.1*px
                report['black_outer_span_m'] = black_span
            # Both outer edges remain mirrored in phase through the UV boundary.
            assert np.count_nonzero(alpha ^ np.fliplr(alpha)) / alpha.shape[0] <= 8, item['UiPriority']
        measurements.append(report)
    output = {'version': '0.7.1.0', 'assets': len(rows), 'added': len(expected),
              'retained_identities': len(old_rows), 'unchanged_old_runtime_files': unchanged,
              'locale_counts': locale_counts, 'measurements': measurements,
              'game_validation': 'pending round 10; inherited round 9 remains pending'}
    (ROOT / 'artifacts/qa-0.7.1.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', 'utf-8')
    print(json.dumps({k: v for k, v in output.items() if k != 'measurements'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
