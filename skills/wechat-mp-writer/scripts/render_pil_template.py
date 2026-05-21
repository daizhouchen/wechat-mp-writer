#!/usr/bin/env python3
"""
PIL 图片渲染模板 · wechat-mp-writer 的图片 fallback 路径

当 playwright MCP 不可用时（断连 / cron 环境 / 远程 agent），
用这个模板直接画 PNG，零依赖只用 PIL + WenQuanYi 中文字体。

==== 使用方法 ====
1. 复制这个文件到 ./articles/<slug>/render_images.py
2. 改 OUT_DIR / 颜色 / 文案 / 布局
3. python3 render_images.py
4. images/cover.png / images/section.png 就生成了

==== 风格预设速查（accent_color 一改，整张图换风） ====
- tech_deep:  ORANGE = (122, 85, 0)   · CREAM = (255, 247, 232)
- cultural:   ORANGE = (139, 58, 58)  · CREAM = (253, 248, 237)  # 朱砂
- cultural2:  ORANGE = (45, 90, 74)   · CREAM = (250, 247, 240)  # 墨绿
- finance:    ORANGE = (30, 77, 139)  · CREAM = (247, 247, 248)
- tutorial:   ORANGE = (92, 74, 58)   · CREAM = (255, 255, 255)
- retrospect: ORANGE = (198, 40, 40)  · CREAM = (253, 248, 237)

==== 字体路径 ====
- /home/zcdai/.local/share/fonts/wqy-microhei/wqy-microhei.ttc  ← 主用
- /usr/share/fonts/dejavu/*.ttf  ← 英文 fallback

==== 实战参考 ====
- /home/zcdai/kn/ms/articles/ai-agent-4-paths/render_images.py  ← 完整 logo_collage + 决策矩阵
"""
from PIL import Image, ImageDraw, ImageFont
import os

# ---- 配置（每篇要改） ----
SLUG = 'demo-slug'
OUT_DIR = f'/home/zcdai/kn/ms/articles/{SLUG}/images'
ACCENT = (122, 85, 0)        # 主色
CREAM = (255, 247, 232)      # 浅色卡片底
CREAM_DEEP = (254, 240, 208) # 加深的卡片底
BG = (255, 255, 255)         # 整页底
INK = (26, 26, 26)
GRAY = (102, 102, 102)
LGRAY = (153, 153, 153)
LINE = (217, 217, 217)
FONT_PATH = '/home/zcdai/.local/share/fonts/wqy-microhei/wqy-microhei.ttc'


def F(size):
    """字体助手。WQY MicroHei TTC 单一 index=0 即可，中英文混排都 OK。"""
    return ImageFont.truetype(FONT_PATH, size, index=0)


def measure(draw, text, font):
    """量字宽（cover 中右对齐 / 居中常用）。"""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


# ---- cover_template 速查 ----
# data_contrast: 大数字反差（4 个数字横排 + 公司行）
# slogan_large:  巨大字标语（1 句话占 60% 屏）
# logo_collage:  4-7 个公司名 + 各家关键数字横排卡
# timeline:      横向时间线（多个圆点 + 节点说明）
# quote_lead:    引语开篇（"..."+ 作者）


def draw_cover_logo_collage():
    """logo_collage 范本：4 公司 + 4 个数字 + bottom 署名。
    适用：横评类（4 路 / 4 种活法 / 4 家公司对比）"""
    img = Image.new('RGB', (1175, 500), BG)
    d = ImageDraw.Draw(img)

    # 顶部色条 + 小标
    d.rectangle([60, 50, 66, 84], fill=ACCENT)
    d.text((80, 55), 'CATEGORY · TOPIC · 2026', font=F(18), fill=ACCENT)

    # 主标题 + 副标题
    d.text((60, 110), '主标题（最多 14 字）', font=F(46), fill=INK)
    d.text((60, 178), '副标题一句话（30 字内）', font=F(28), fill=ACCENT)

    # 4 卡横排（核心）
    y0, h, gap = 250, 130, 14
    box_w = (1175 - 60 * 2 - gap * 3) // 4
    cards = [('公司一', '$XX', '维度一'), ('公司二', '$XX', '维度二'),
             ('公司三', '$XX', '维度三'), ('公司四', '$XX', '维度四')]
    for i, (name, num, sub) in enumerate(cards):
        x = 60 + i * (box_w + gap)
        d.rectangle([x, y0, x + box_w, y0 + h], fill=CREAM, outline=CREAM_DEEP, width=1)
        d.rectangle([x, y0, x + box_w, y0 + 4], fill=ACCENT)
        d.text((x + 18, y0 + 18), name, font=F(20), fill=INK)
        d.text((x + 18, y0 + 52), num, font=F(38), fill=ACCENT)
        d.text((x + 18, y0 + 100), sub, font=F(13), fill=GRAY)

    # 底部分隔 + 署名
    d.line([60, 440, 1115, 440], fill=LINE, width=1)
    d.text((60, 462), '副标识或副定位', font=F(13), fill=GRAY)
    sig = 'A what I'
    fnt = F(14)
    tw, _ = measure(d, sig, fnt)
    d.text((1115 - tw, 462), sig, font=fnt, fill=LGRAY)

    out = os.path.join(OUT_DIR, 'cover.png')
    img.save(out, 'PNG', optimize=True)
    print(f'[cover] {out}')


def draw_2x2_matrix():
    """2x2 矩阵图范本：横纵轴 + 4 象限 + 高亮一个推荐象限。
    适用：分类 / 决策树 / 横纵两维度对比"""
    img = Image.new('RGB', (1080, 680), BG)
    d = ImageDraw.Draw(img)

    # 章节标号（chapter_number）
    d.text((60, 30), '03', font=F(54), fill=CREAM_DEEP)
    d.text((60, 100), '— — — — — — —', font=F(13), fill=ACCENT)
    d.text((60, 125), '标题', font=F(22), fill=INK)
    d.text((60, 158), '横轴 = … 纵轴 = …', font=F(13), fill=GRAY)

    # 坐标轴
    d.line([540, 200, 540, 615], fill=ACCENT, width=1)
    d.line([80, 410, 1000, 410], fill=ACCENT, width=1)
    fnt = F(12)
    d.text((92, 405), '左', font=fnt, fill=LGRAY)
    tw, _ = measure(d, '右', fnt)
    d.text((990 - tw, 405), '右', font=fnt, fill=LGRAY)

    # 4 象限
    cells = [(100, 220, '① 左上', '描述行 1', '描述行 2', '描述行 3', GRAY),
             (580, 220, '② 右上 · 推荐', '描述行 1', '描述行 2', '描述行 3', ACCENT),
             (100, 425, '③ 左下', '描述行 1', '描述行 2', '描述行 3', GRAY),
             (580, 425, '④ 右下', '描述行 1', '描述行 2', '描述行 3', GRAY)]
    for x, y, title, s1, s2, s3, accent in cells:
        d.rectangle([x, y, x + 400, y + 175], fill=BG, outline=accent,
                    width=2 if accent == ACCENT else 1)
        d.rectangle([x, y, x + 400, y + 38], fill=accent)
        d.text((x + 18, y + 8), title, font=F(15), fill=BG)
        d.text((x + 18, y + 58), s1, font=F(13), fill=INK)
        d.text((x + 18, y + 85), s2, font=F(13), fill=INK)
        d.text((x + 18, y + 112), s3, font=F(13), fill=accent)

    # 底部注脚
    d.line([60, 640, 1020, 640], fill=LINE, width=1)
    d.text((60, 655), '核心判断', font=F(13), fill=GRAY)

    out = os.path.join(OUT_DIR, 'matrix.png')
    img.save(out, 'PNG', optimize=True)
    print(f'[matrix] {out}')


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    draw_cover_logo_collage()
    draw_2x2_matrix()
