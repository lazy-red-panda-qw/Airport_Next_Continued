"""Draw scale-matched previews from the generated NetLane PNGs and manifest."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'Airport Decal Pack Countinue/CustomAssets'


def main():
    rows = {r['UiPriority']: r for r in json.loads((ROOT / 'docs/asset-catalog.json').read_text('utf-8'))}
    groups = [(7540, 7541), (7550, 7551), (7560, 7561), (7570, 7571)]
    scale, length = 20, 24
    cell_w, cell_h, top = 420, 640, 90
    for lang in ('zh-CN', 'en-US'):
        font_path = 'C:/Windows/Fonts/simhei.ttf' if lang == 'zh-CN' else 'C:/Windows/Fonts/arial.ttf'
        title_font = ImageFont.truetype(font_path, 30)
        font = ImageFont.truetype(font_path, 26)
        small = ImageFont.truetype(font_path, 21)
        canvas = Image.new('RGB', (cell_w * len(groups), top + cell_h * 2), '#eef1f3')
        d = ImageDraw.Draw(canvas)
        zh = lang == 'zh-CN'
        d.text((24, 20), '服务车辆道路：成套预设与独立组件并存' if zh else 'Vehicle roads: presets and separate components', fill='#182b3b', font=title_font)
        for column, pair in enumerate(groups):
            for line, priority in enumerate(pair):
                row = rows[priority]
                x, y = column * cell_w, top + line * cell_h
                style = [('普通道路', 'Normal road'), ('CAAM 穿越段', 'CAAM crossing'), ('FAA 白色拉链', 'FAA white zipper'), ('FAA 黑底棋盘', 'FAA black contrast')][column][0 if zh else 1]
                lane = ('单车道' if line == 0 else '双车道') if zh else ('Single lane' if line == 0 else 'Two lanes')
                road_width = 4 if line == 0 else 7.5
                d.text((x + 20, y + 4), f'{priority}  {style}', fill='#182b3b', font=font)
                d.text((x + 20, y + 40), f'{lane} · {road_width:g} m', fill='#536574', font=font)
                raw = np.asarray(Image.open(ASSETS / row['path'] / '_BaseColorMap.png').convert('RGBA'))
                width_px = round(row['mesh_x_m'] * scale)
                height_px = round(length * scale)
                # Sample physical world z modulo the exact configured UV period.
                ix = np.clip(((np.arange(width_px) + .5) / width_px * raw.shape[1]).astype(int), 0, raw.shape[1]-1)
                iz = (((np.arange(height_px) + .5) / scale % row['tile_period_m']) / row['tile_period_m'] * raw.shape[0]).astype(int)
                texture = Image.fromarray(raw[iz[:, None], ix[None, :]])
                px, py = x + (cell_w - width_px) // 2, y + 94
                d.rectangle((px, py, px + width_px - 1, py + height_px - 1), fill='#727672')
                canvas.paste(texture, (px, py), texture)
                caption = ('白色外缘宽；24 m直线' if zh else 'White outer span; 24 m sample')
                d.text((x + 20, y + 588), caption, fill='#536574', font=small)
                period = f"周期 {row['tile_period_m']:g} m" if zh else f"Repeat {row['tile_period_m']:g} m"
                d.text((x + 20, y + 615), period, fill='#536574', font=small)
        name = 'service-road-preview.png' if zh else 'service-road-preview-en.png'
        canvas.save(ROOT / 'docs' / name)
        print(name)


if __name__ == '__main__':
    main()
