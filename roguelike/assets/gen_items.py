"""アイテム・武具・設備・畑タイルを pygame だけで生成する（依存追加なし）。

64×64・光源=左上・複数階調＋黒縁で、キャラ(gen_sprites)と画風を揃える。
描画プリミティブ（surf/rect/disc/ball/outline_pass/_mix）は gen_sprites から再利用する。

    cd assets && python3 gen_items.py   # 全アイテム/武具/設備/畑PNGを再生成

手描きPNGに差し替えたい場合はそのまま上書きすればよい（再実行しなければ消えない）。
"""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame  # noqa: E402

pygame.init()

from gen_sprites import (  # noqa: E402  プリミティブを共有して画風を統一
    S, ASSETS_DIR, surf, px, rect, disc, ball, outline_pass, _mix, pixelate,
)

OL = (26, 22, 30)


def vbox(s, x0, y0, x1, y1, base):
    """上＝明・下＝影の縦グラデ箱（木箱・石材など）。"""
    rect(s, x0, y0, x1, y1, base)
    rect(s, x0, y0, x1, y0 + 1, _mix(base, (255, 255, 255), 0.30))
    rect(s, x0, y0, x0, y1, _mix(base, (255, 255, 255), 0.18))
    rect(s, x0, y1 - 1, x1, y1, _mix(base, (0, 0, 0), 0.34))
    rect(s, x1, y0, x1, y1, _mix(base, (0, 0, 0), 0.22))


def streak(s, x, y0, y1, col):
    """縦のハイライト線（ガラス・刃の照り）。"""
    rect(s, x, y0, x, y1, col)


# ============================================================ 消費アイテム
def make_potion(liquid):
    s = surf()
    glass = (206, 226, 232)
    cork = (150, 110, 66)
    ll = _mix(liquid, (255, 255, 255), 0.45)
    ls = _mix(liquid, (0, 0, 0), 0.40)
    # 中身（丸フラスコ）
    ball(s, 32, 42, 15, liquid, ll, ls, OL)
    # 液面の上は空のガラス
    for y in range(27, 34):
        for x in range(24, 41):
            if (x - 32) ** 2 + (y - 42) ** 2 <= 15 * 15:
                px(s, x, y, glass)
    # 首・口
    vbox(s, 28, 20, 36, 30, glass)
    rect(s, 26, 12, 38, 20, cork)
    rect(s, 26, 12, 38, 13, _mix(cork, (255, 255, 255), 0.3))
    streak(s, 26, 35, 48, _mix(glass, (255, 255, 255), 0.5))  # ガラスの照り
    px(s, 27, 32, (255, 255, 255))
    outline_pass(s, OL)
    return s


def make_scroll(symbol):
    s = surf()
    parch = (226, 206, 150)
    rod = (150, 110, 66)
    vbox(s, 14, 18, 50, 46, parch)
    rect(s, 12, 15, 52, 20, rod)             # 上の巻軸
    rect(s, 12, 44, 52, 49, rod)             # 下の巻軸
    rect(s, 12, 15, 52, 16, _mix(rod, (255, 255, 255), 0.3))
    rect(s, 12, 48, 52, 49, _mix(rod, (0, 0, 0), 0.3))
    # 中央のシンボル（雷=黄／混乱=紫）
    if symbol == "bolt":
        pygame.draw.polygon(s, (250, 220, 90),
                            [(34, 22), (26, 34), (32, 34), (28, 44),
                             (40, 30), (33, 30), (38, 22)])
    else:
        disc(s, 32, 32, 7, (170, 120, 230))
        disc(s, 32, 32, 4, (214, 178, 248))
        disc(s, 32, 32, 1.5, (120, 70, 180))
    outline_pass(s, OL)
    return s


def make_food():
    """木の実（赤い実＋葉）。食材アイコン。"""
    s = surf()
    ball(s, 27, 38, 12, (210, 70, 64), (244, 140, 120), (150, 40, 44), OL)
    ball(s, 41, 42, 9, (200, 60, 58), (236, 130, 110), (140, 36, 40), OL)
    # 葉と茎
    rect(s, 31, 18, 33, 28, (120, 86, 50))
    pygame.draw.polygon(s, (96, 160, 78), [(33, 22), (50, 16), (40, 28)])
    pygame.draw.polygon(s, (72, 130, 60), [(33, 24), (46, 24), (40, 30)])
    px(s, 24, 33, (255, 230, 220))
    outline_pass(s, OL)
    return s


def make_dish():
    """湯気の立つ料理（器＋具＋湯気）。"""
    s = surf()
    bowl = (210, 214, 224)
    # 器（下半分の楕円）
    for y in range(38, 54):
        for x in range(12, 53):
            if (x - 32) ** 2 / 420 + (y - 40) ** 2 / 200 <= 1 and y >= 39:
                px(s, x, y, bowl)
    rect(s, 12, 38, 52, 40, _mix(bowl, (255, 255, 255), 0.3))
    rect(s, 14, 51, 50, 54, _mix(bowl, (0, 0, 0), 0.3))
    # 具（スープ＋具材）
    for y in range(35, 41):
        for x in range(16, 49):
            if (x - 32) ** 2 / 320 + (y - 39) ** 2 / 40 <= 1:
                px(s, x, y, (228, 150, 70))
    disc(s, 26, 37, 3, (210, 90, 70)); disc(s, 38, 38, 3, (120, 170, 90))
    # 湯気
    for hx, off in ((24, 0), (32, -3), (40, 0)):
        for k in range(6):
            px(s, hx + (1 if k % 2 else -1), 30 - k * 2 + off, (235, 235, 240))
    outline_pass(s, OL)
    return s


# ============================================================ 武器・防具
def _blade(s, x0, y0, x1, y1):
    steel, light, dark = (208, 216, 232), (248, 250, 255), (120, 132, 156)
    rect(s, x0, y0, x1, y1, steel)
    rect(s, x0, y0, x0, y1, light)
    rect(s, x1, y0, x1, y1, dark)
    # 切っ先
    px(s, (x0 + x1) // 2, y0 - 1, light)


def make_dagger():
    s = surf()
    _blade(s, 28, 16, 34, 40)
    rect(s, 22, 40, 40, 44, (226, 186, 78))      # 鍔
    rect(s, 22, 40, 40, 41, (250, 224, 140))
    vbox(s, 29, 44, 33, 54, (120, 84, 50))       # 柄
    disc(s, 31, 55, 2.4, (226, 186, 78))         # 柄頭
    outline_pass(s, OL)
    return s


def make_sword():
    s = surf()
    _blade(s, 29, 6, 35, 42)
    rect(s, 20, 42, 44, 46, (226, 186, 78))      # 十字鍔
    rect(s, 20, 42, 44, 43, (250, 224, 140))
    vbox(s, 30, 46, 34, 56, (110, 78, 48))       # 握り
    disc(s, 32, 57, 3, (226, 186, 78)); px(s, 31, 56, (250, 224, 140))
    outline_pass(s, OL)
    return s


def make_leather_armor():
    s = surf()
    base, light, dark = (146, 100, 56), (180, 132, 80), (104, 68, 38)
    # 胴（台形の革鎧）
    pygame.draw.polygon(s, base, [(20, 24), (44, 24), (48, 52), (16, 52)])
    pygame.draw.polygon(s, light, [(20, 24), (44, 24), (44, 28), (20, 28)])
    pygame.draw.polygon(s, dark, [(16, 48), (48, 48), (48, 52), (16, 52)])
    rect(s, 30, 24, 34, 52, dark)                 # 前合わせ
    rect(s, 16, 40, 48, 44, (92, 60, 34))         # ベルト
    rect(s, 30, 40, 34, 44, (226, 186, 78))       # バックル
    # 肩
    disc(s, 22, 26, 5, light); disc(s, 42, 26, 5, base)
    outline_pass(s, OL)
    return s


def make_chain_mail():
    s = surf()
    base, light, dark = (150, 158, 176), (190, 198, 214), (96, 104, 124)
    pygame.draw.polygon(s, base, [(20, 22), (44, 22), (48, 52), (16, 52)])
    pygame.draw.polygon(s, light, [(20, 22), (44, 22), (44, 26), (20, 26)])
    pygame.draw.polygon(s, dark, [(16, 48), (48, 48), (48, 52), (16, 52)])
    disc(s, 22, 24, 5, light); disc(s, 42, 24, 5, base)
    # 鎖の網目（点描）
    for y in range(28, 50, 3):
        for x in range(18, 47, 3):
            if x > 16 + (52 - y) * 0.1:
                px(s, x + (1 if (y // 3) % 2 else 0), y, dark)
                px(s, x + (1 if (y // 3) % 2 else 0), y - 1, light)
    outline_pass(s, OL)
    return s


def make_spear():
    """細い菱形の穂先＋長い木の柄。"""
    s = surf()
    steel, light, dark = (208, 216, 232), (248, 250, 255), (120, 132, 156)
    wood, wl, wd = (120, 84, 50), (156, 116, 74), (86, 58, 34)
    rect(s, 30, 22, 33, 58, wood)                 # 柄
    rect(s, 30, 22, 30, 58, wl); rect(s, 33, 22, 33, 58, wd)
    pygame.draw.polygon(s, steel, [(31, 4), (37, 19), (31, 26), (25, 19)])  # 穂先(菱)
    pygame.draw.polygon(s, light, [(31, 4), (31, 26), (25, 19)])
    pygame.draw.polygon(s, dark, [(31, 4), (37, 19), (31, 26)])
    rect(s, 27, 21, 36, 23, (226, 186, 78))       # 付け根の金具
    outline_pass(s, OL)
    return s


def make_katana():
    """反りのある細身の刀身＋丸鍔＋黒い柄巻き。"""
    s = surf()
    steel, light, dark = (214, 222, 236), (250, 252, 255), (128, 140, 164)
    for i, y in enumerate(range(10, 45)):
        x = int(35 - i * 0.26)                    # 上ほど右＝ゆるい反り
        rect(s, x, y, x + 3, y, steel)
        px(s, x, y, light)                        # 峰の照り
        px(s, x + 3, y, dark)                     # 刃の影
    px(s, 35, 9, light)                           # 切っ先
    disc(s, 25, 47, 4, (58, 62, 72)); disc(s, 25, 47, 3, (150, 120, 60))  # 丸鍔
    rect(s, 18, 48, 25, 58, (40, 44, 52))         # 柄（黒い握り）
    for k in range(49, 58, 2):
        px(s, 21, k, (150, 120, 60))              # 柄巻きの菱
    outline_pass(s, OL)
    return s


def make_axe():
    """縦の木の柄＋右側の大きな三日月の斧頭。"""
    s = surf()
    wood, wl, wd = (120, 84, 50), (156, 116, 74), (86, 58, 34)
    steel, light, dark = (196, 204, 220), (238, 242, 250), (120, 130, 152)
    rect(s, 30, 10, 33, 58, wood)                 # 柄
    rect(s, 30, 10, 30, 58, wl); rect(s, 33, 10, 33, 58, wd)
    head = [(33, 11), (49, 14), (55, 22), (49, 31), (33, 29)]  # 大きな三日月の刃
    pygame.draw.polygon(s, steel, head)
    pygame.draw.polygon(s, light, [(33, 11), (49, 14), (44, 18), (33, 17)])  # 受光
    pygame.draw.polygon(s, dark, [(33, 24), (49, 31), (44, 26), (33, 28)])   # 影
    pygame.draw.polygon(s, (232, 236, 244), [(49, 14), (55, 22), (49, 31)])  # 刃先の照り
    disc(s, 31, 34, 2, (60, 64, 74))              # 柄頭の金具
    outline_pass(s, OL)
    return s


def make_shield():
    """木の五角盾＋金属の縁＋中央のボス（鋲）。"""
    s = surf()
    wood, wl, wd = (138, 96, 54), (176, 130, 78), (96, 64, 36)
    rim = (150, 158, 176)
    pts = [(20, 15), (44, 15), (46, 37), (32, 53), (18, 37)]
    pygame.draw.polygon(s, wood, pts)
    pygame.draw.polygon(s, wl, [(20, 15), (44, 15), (44, 20), (20, 20)])  # 上の受光
    pygame.draw.polygon(s, wd, [(18, 37), (46, 37), (32, 53)])            # 下の影
    for x in range(24, 42, 5):
        rect(s, x, 18, x, 48, wd)                 # 板の縦目
    pygame.draw.polygon(s, rim, pts, 2)           # 金属縁
    disc(s, 32, 33, 4, rim); disc(s, 32, 33, 2, (214, 220, 234))  # ボス
    outline_pass(s, OL)
    return s


def make_plate_armor():
    """明るい鋼の胴鎧＋中央リッジ＋肩当て（球）。"""
    s = surf()
    base, light, dark = (178, 186, 202), (222, 228, 240), (110, 118, 138)
    pygame.draw.polygon(s, base, [(20, 22), (44, 22), (48, 52), (16, 52)])
    pygame.draw.polygon(s, light, [(20, 22), (44, 22), (44, 27), (20, 27)])
    pygame.draw.polygon(s, dark, [(16, 47), (48, 47), (48, 52), (16, 52)])
    rect(s, 31, 22, 33, 52, light)                # 中央リッジ
    rect(s, 22, 36, 42, 37, dark)                 # 胴の分割線
    ball(s, 21, 24, 6, base, light, dark, OL)     # 肩当て
    ball(s, 43, 24, 6, base, light, dark, OL)
    outline_pass(s, OL)
    return s


def make_crossbow():
    """横向きの太い弓（プロド）＋弦＋短い木の銃床＋装填した矢。"""
    s = surf()
    wood, wl, wd = (120, 84, 50), (156, 116, 74), (86, 58, 34)
    steel, hi, dark = (150, 158, 176), (206, 212, 226), (96, 104, 124)
    # 横向きの弓：中央が上・両端が下の浅い ∩（太め）
    for x in range(9, 56):
        y = 22 + int(abs(x - 32) * 0.30)
        rect(s, x, y, x, y + 3, steel)
        px(s, x, y, hi); px(s, x, y + 3, dark)
    pygame.draw.line(s, (232, 232, 238), (10, 22), (54, 22))   # 弦
    rect(s, 30, 22, 34, 54, wood)                 # 銃床（縦・短め）
    rect(s, 30, 22, 30, 54, wl); rect(s, 34, 22, 34, 54, wd)
    rect(s, 28, 46, 36, 50, wd)                   # 握り
    rect(s, 31, 14, 33, 24, (206, 206, 210))      # 装填した矢
    pygame.draw.polygon(s, steel, [(32, 9), (35, 15), (29, 15)])
    outline_pass(s, OL)
    return s


# ============================================================ 素材・種・大切なもの
def make_material():
    """青い鉱石のかけら（多面の結晶）。"""
    s = surf()
    base, light, dark = (96, 150, 220), (170, 210, 250), (54, 96, 168)
    pygame.draw.polygon(s, base, [(32, 12), (48, 34), (38, 54), (22, 54), (14, 32)])
    pygame.draw.polygon(s, light, [(32, 12), (40, 30), (26, 34), (22, 22)])  # 受光面
    pygame.draw.polygon(s, dark, [(38, 54), (22, 54), (28, 36), (40, 32)])   # 影面
    px(s, 30, 18, (240, 250, 255))
    outline_pass(s, OL)
    return s


def make_seed():
    s = surf()
    ball(s, 32, 38, 12, (150, 110, 64), (192, 152, 96), (104, 74, 42), OL)
    rect(s, 30, 22, 33, 30, (120, 150, 80))    # 芽
    px(s, 27, 33, (224, 200, 160))
    outline_pass(s, OL)
    return s


def make_key_item():
    """金の鍵（環＋軸＋歯）。冒険者の証/各種の鍵に共用。"""
    s = surf()
    gold, gl, gs = (226, 186, 78), (252, 226, 140), (160, 122, 44)
    ball(s, 24, 24, 9, gold, gl, gs, OL)         # 持ち手の環
    disc(s, 24, 24, 4, (0, 0, 0, 0))             # 環の穴
    for y in range(20, 28):                       # 穴を背景に
        for x in range(20, 28):
            if (x - 24) ** 2 + (y - 24) ** 2 <= 16:
                s.set_at((x, y), (0, 0, 0, 0))
    rect(s, 27, 30, 31, 52, gold)                 # 軸
    rect(s, 27, 30, 27, 52, gl)
    rect(s, 31, 44, 37, 47, gold)                 # 歯
    rect(s, 31, 49, 35, 52, gold)
    outline_pass(s, OL)
    return s


def make_tent():
    """魔法のテント（三角＋入口＋星）。"""
    s = surf()
    cloth, cl, cs = (180, 70, 70), (220, 120, 110), (130, 44, 50)
    pygame.draw.polygon(s, cloth, [(32, 12), (54, 54), (10, 54)])
    pygame.draw.polygon(s, cl, [(32, 12), (40, 54), (26, 54)])   # 中央の受光帯
    pygame.draw.polygon(s, cs, [(32, 12), (54, 54), (44, 54)])   # 右の影
    pygame.draw.polygon(s, (60, 30, 36), [(32, 30), (38, 54), (26, 54)])  # 入口
    rect(s, 31, 12, 33, 16, (120, 84, 50))        # 先端の棒
    # 魔法の星
    for dx, dy in ((0, -3), (0, 3), (-3, 0), (3, 0)):
        px(s, 46 + dx, 20 + dy, (250, 240, 150))
    px(s, 46, 20, (255, 255, 220))
    outline_pass(s, OL)
    return s


# ============================================================ 拠点の設備
def make_st_cooking():
    s = surf()
    vbox(s, 12, 30, 52, 54, (110, 110, 120))      # 石のかまど
    rect(s, 18, 36, 46, 50, (40, 36, 40))         # 焚き口
    # 炎
    for cx, h, col in ((26, 14, (240, 120, 50)), (32, 18, (250, 180, 70)), (38, 13, (240, 120, 50))):
        pygame.draw.polygon(s, col, [(cx, 50 - h), (cx - 4, 50), (cx + 4, 50)])
    pygame.draw.polygon(s, (255, 232, 150), [(32, 40), (29, 50), (35, 50)])
    disc(s, 32, 26, 9, (60, 60, 66)); rect(s, 22, 24, 42, 26, (40, 40, 46))  # 鍋
    outline_pass(s, OL)
    return s


def make_st_storage():
    s = surf()
    base = (150, 110, 64)
    vbox(s, 12, 28, 52, 54, base)
    rect(s, 12, 28, 52, 36, _mix(base, (255, 255, 255), 0.18))   # 蓋
    rect(s, 12, 36, 52, 38, (92, 62, 36))
    for x in (20, 32, 44):                                       # 板の継ぎ目
        rect(s, x, 38, x, 54, (110, 76, 44))
    rect(s, 29, 34, 35, 42, (60, 44, 28)); rect(s, 30, 36, 34, 40, (226, 186, 78))  # 錠前
    outline_pass(s, OL)
    return s


def make_st_alchemy():
    s = surf()
    rect(s, 18, 50, 46, 54, (90, 70, 50))         # 台
    ball(s, 32, 40, 12, (170, 120, 230), (214, 178, 248), (110, 70, 170), OL)  # フラスコ球
    vbox(s, 28, 22, 36, 32, (200, 220, 228))      # 首
    rect(s, 26, 18, 38, 22, (150, 110, 66))       # 栓
    for bx, by in ((30, 40), (35, 36), (28, 44)):  # 泡
        px(s, bx, by, (235, 220, 255))
    outline_pass(s, OL)
    return s


def make_st_ranch():
    s = surf()
    for fx in (16, 30, 44):                        # 牧柵
        vbox(s, fx, 26, fx + 4, 52, (150, 112, 66))
    rect(s, 14, 32, 50, 35, (130, 94, 54))
    rect(s, 14, 42, 50, 45, (130, 94, 54))
    # 干し草
    disc(s, 40, 48, 8, (216, 188, 92)); disc(s, 40, 48, 5, (236, 212, 120))
    for a in range(0, 9):
        px(s, 33 + a, 46 + (a % 3), (190, 162, 78))
    outline_pass(s, OL)
    return s


def make_st_fishery():
    s = surf()
    for y in range(30, 54):                        # 水面
        for x in range(12, 53):
            t = (y - 30) / 24
            px(s, x, y, (_mix((90, 160, 220), (40, 96, 168), t)))
    for wy in (34, 40, 46):                         # さざ波
        for x in range(16, 48, 4):
            px(s, x, wy, (180, 220, 245)); px(s, x + 1, wy, (180, 220, 245))
    disc(s, 30, 42, 5, (230, 140, 60)); disc(s, 30, 42, 2, (250, 190, 110))  # 魚
    pygame.draw.polygon(s, (230, 140, 60), [(35, 42), (40, 38), (40, 46)])    # 尾
    px(s, 28, 40, (20, 20, 24))                                               # 目
    outline_pass(s, OL)
    return s


def make_st_exit():
    s = surf()
    vbox(s, 14, 16, 50, 54, (150, 112, 66))        # 木枠
    rect(s, 20, 22, 44, 54, (54, 40, 28))          # 暗い出口
    pygame.draw.polygon(s, (240, 230, 170),        # 上向き矢印（外へ）
                        [(32, 26), (24, 36), (29, 36), (29, 46), (35, 46), (35, 36), (40, 36)])
    outline_pass(s, OL)
    return s


# ============================================================ 畑タイル
def _soil(s):
    base = (120, 88, 56)
    rect(s, 4, 8, 60, 58, base)
    rect(s, 4, 8, 60, 10, _mix(base, (255, 255, 255), 0.2))
    rect(s, 4, 56, 60, 58, _mix(base, (0, 0, 0), 0.3))
    for fy in (20, 34, 48):                          # 畝
        rect(s, 8, fy, 56, fy + 1, (96, 68, 42))
        rect(s, 8, fy + 2, 56, fy + 2, (146, 110, 70))


def make_farm_empty():
    s = surf()
    _soil(s)
    outline_pass(s, OL)
    return s


def make_farm_grow():
    s = surf()
    _soil(s)
    for cx in (18, 32, 46):                          # 双葉の芽
        rect(s, cx, 30, cx, 44, (90, 140, 70))
        disc(s, cx - 3, 30, 3, (120, 178, 86)); disc(s, cx + 3, 30, 3, (120, 178, 86))
    outline_pass(s, OL)
    return s


def make_farm_ready():
    s = surf()
    _soil(s)
    for cx in (18, 32, 46):                          # 茎＋実
        rect(s, cx, 22, cx, 46, (76, 128, 60))
        ball(s, cx, 22, 5, (220, 80, 70), (244, 140, 120), (150, 44, 46), OL)
    outline_pass(s, OL)
    return s


# ============================================================ 出力
def _save(s, name):
    pygame.image.save(pixelate(s), os.path.join(ASSETS_DIR, f"{name}.png"))


def generate():
    items = {
        "potion": make_potion((220, 70, 150)),
        "scroll": make_scroll("bolt"),
        "scroll_confuse": make_scroll("confuse"),
        "food": make_food(),
        "dish": make_dish(),
        "dagger": make_dagger(),
        "sword": make_sword(),
        "spear": make_spear(),
        "katana": make_katana(),
        "axe": make_axe(),
        "leather_armor": make_leather_armor(),
        "chain_mail": make_chain_mail(),
        "shield": make_shield(),
        "plate_armor": make_plate_armor(),
        "crossbow": make_crossbow(),
        "material": make_material(),
        "seed": make_seed(),
        "key_item": make_key_item(),
        "tent": make_tent(),
        "st_cooking": make_st_cooking(),
        "st_storage": make_st_storage(),
        "st_alchemy": make_st_alchemy(),
        "st_ranch": make_st_ranch(),
        "st_fishery": make_st_fishery(),
        "st_exit": make_st_exit(),
        "farm_empty": make_farm_empty(),
        "farm_grow": make_farm_grow(),
        "farm_ready": make_farm_ready(),
    }
    for name, s in items.items():
        _save(s, name)
    print(f"regenerated {len(items)} item/station sprites into", ASSETS_DIR)


if __name__ == "__main__":
    generate()
