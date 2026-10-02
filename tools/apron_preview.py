"""Physical-aspect previews from final apron PNGs; aircraft only in the preview."""
from pathlib import Path
import argparse
import json
from xml.etree import ElementTree

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'Airport Decal Pack Countinue/CustomAssets'
LABELS = {'base': '基础布局', 'cargo': '货运基础', 'ga': '通航基础', 'loop': '开放回转', 'through': '开放贯通'}
EN_LABELS = {'base': 'Base layout', 'cargo': 'Cargo base', 'ga': 'GA base', 'loop': 'Open turnaround', 'through': 'Open through stand'}


def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', size)


def put_texture(sheet, record, rect):
    x, y, w, h = rect
    mw, mh = record['mesh_m']
    scale = min(w / mw, h / mh)
    im = Image.open(ASSETS / record['path'] / '_BaseColorMap.png').convert('RGBA')
    im = im.resize((round(mw * scale), round(mh * scale)), Image.Resampling.LANCZOS)
    origin = (round(x + (w - im.width) / 2), round(y + (h - im.height) / 2))
    sheet.paste(im, origin, im)
    return origin, scale


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=['zh-CN', 'en-US'], default='zh-CN')
    lang = parser.parse_args().language
    english = lang == 'en-US'
    labels = EN_LABELS if english else LABELS
    suffix = '-en' if english else ''
    def tr(zh, en):
        return en if english else zh
    version = ElementTree.parse(ROOT / 'Airport Decal Pack Countinue/Properties/PublishConfiguration.xml').getroot().find('ModVersion').get('Value')
    records = json.loads((ROOT / 'docs/stand-presets.json').read_text('utf-8'))['assets']
    stands = [r for r in records if r['kind'] == 'stand']
    stands.sort(key=lambda r: r['UiPriority'])
    sheet = Image.new('RGB', (1600, 1530), (28, 32, 38))
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 18), f"{version}  " + tr('机坪基础布局＋独立可选模块', 'Apron bases and separate optional modules'), font=font(36), fill='white')
    draw.text((24, 67), tr('基础模板保留服务留白；廊桥、轮位、设备框、编号和停止线另放。', 'Bases retain side reserves; add bridges, wheel marks, parking boxes, identifiers and stop datums separately.'), font=font(23), fill=(205, 211, 219))
    for i, r in enumerate(stands + [r for r in records if r['kind'] == 'no_parking_shape']):
        x, y = i % 4 * 400, 116 + i // 4 * 462
        draw.rounded_rectangle((x + 10, y, x + 390, y + 450), radius=12, fill=(67, 72, 78))
        if r['kind'] == 'stand':
            draw.text((x + 22, y + 10), f"{r['UiPriority']} · {labels[r['layout']]}", font=font(25), fill='white')
            draw.text((x + 22, y + 48), r['profile']['key'] if english else r['profile']['title'], font=font(20), fill=(208, 214, 222))
            draw.text((x + 22, y + 76), tr('参照 ', 'Reference ') + f"{r['profile']['length_m']:g} × {r['profile']['span_m']:g} m", font=font(19), fill=(193, 201, 211))
        else:
            draw.text((x + 22, y + 10), f"{r['UiPriority']} · " + tr('可选禁停模块', 'No-parking module'), font=font(25), fill='white')
            shape = tr('梯形 6／12 × 12 m', 'Trapezoid 6/12 × 12 m') if r['UiPriority'] == 7832 else tr('折角 10 × 14 m', 'L shape 10 × 14 m')
            draw.text((x + 22, y + 48), shape, font=font(20), fill=(208, 214, 222))
            draw.text((x + 22, y + 76), tr('可用于廊桥下方；轮位独立', 'Below bridges; wheel marks separate'), font=font(19), fill=(193, 201, 211))
        put_texture(sheet, r, (x + 22, y + 111, 356, 320))
    sheet.save(ROOT / f'docs/stand-preview{suffix}.png')

    r = next(r for r in stands if r['UiPriority'] == 7740)
    example = Image.new('RGB', (1700, 1100), (28, 32, 38))
    draw = ImageDraw.Draw(example)
    draw.text((24, 16), tr('原版干线客机 · 通用基础布局', 'Game passenger aircraft - Base layout'), font=font(34), fill='white')
    draw.text((24, 64), tr('左：基础贴图    右：玩家组合示意（飞机／编号／可选禁停模块／轮位／设备框）', 'Left: Base decal    Right: Player assembly (aircraft / identifier / no-parking area / wheel marks / parking boxes)'), font=font(22), fill=(205, 211, 219))
    for index in range(2):
        x = 15 + 850 * index
        draw.rounded_rectangle((x, 111, x + 820, 1030), radius=10, fill=(67, 72, 78))
        origin, scale = put_texture(example, r, (x + 24, 124, 770, 875))
        if index == 1:
            ax, ay, span, length = r['aircraft_rect_m']
            cx = ax + span / 2
            def optional(priority, position):
                detail = next(item for item in records if item['UiPriority'] == priority)
                im = Image.open(ASSETS / detail['path'] / '_BaseColorMap.png').convert('RGBA')
                im = im.resize(tuple(round(v * scale) for v in detail['mesh_m']), Image.Resampling.LANCZOS)
                example.paste(im, (round(origin[0] + position[0] * scale), round(origin[1] + position[1] * scale)), im)
            optional(7832, (cx - 17, 0))
            optional(7820, (cx - 9.6, ay - 13))
            optional(7840, (r['service_strips_m'][1][0] + 2, ay + 8))
            optional(7840, (r['service_strips_m'][1][0] + 2, ay + 31))
            # Generic silhouette stays within the measured length/span rectangle.
            points = [(cx, ay), (cx + length * .06, ay + length * .12),
                      (cx + length * .06, ay + length * .38), (cx + span / 2, ay + length * .51),
                      (cx + span / 2, ay + length * .59), (cx + length * .055, ay + length * .53),
                      (cx + length * .035, ay + length * .84), (cx + span * .18, ay + length * .94),
                      (cx + span * .18, ay + length), (cx, ay + length * .96),
                      (cx - span * .18, ay + length), (cx - span * .18, ay + length * .94),
                      (cx - length * .035, ay + length * .84), (cx - length * .055, ay + length * .53),
                      (cx - span / 2, ay + length * .59), (cx - span / 2, ay + length * .51),
                      (cx - length * .06, ay + length * .38), (cx - length * .06, ay + length * .12)]
            pixel = [(origin[0] + px * scale, origin[1] + py * scale) for px, py in points]
            draw.polygon(pixel, fill=(126, 135, 143), outline=(206, 214, 220), width=2)
            center = (origin[0] + cx * scale, origin[1] + (ay + length * .14) * scale)
            draw.text(center, tr('飞机示意', 'Illustrative aircraft'), font=font(19), fill='white', anchor='mm')
            gx = origin[0] + r['axis_x_m'] * scale
            gy = origin[1] + sum(r['id_gap_y_m']) / 2 * scale
            draw.text((gx, gy), '314', font=font(24), fill=(255, 239, 73), anchor='mm')
    draw.text((24, 1052), tr('基础：边界、角部禁停、引导与服务留白    可选模块位置由玩家决定；示意飞机、314编号及灰底不进入贴图', 'Base: boundaries, guidance, corner hatching and reserves. Add details separately; aircraft, 314 and grey paving are illustrative.'), font=font(21), fill=(220, 226, 232))
    example.save(ROOT / f'docs/apron-layout-example{suffix}.png')
    print(f'Wrote docs/stand-preview{suffix}.png and docs/apron-layout-example{suffix}.png')


if __name__ == '__main__':
    main()
