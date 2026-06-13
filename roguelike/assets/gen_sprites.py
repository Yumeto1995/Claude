"""64×64 キャラスプライトを pygame だけで生成する（依存追加なし）。

市販ドット絵風を狙い、各色を 3〜4 階調にして光源=左上で陰影を付ける。
背景は完全透過。`python3 gen_sprites.py` で assets 直下に
player/npc/goblin/slime/corpse（＋歩行2フレーム *_walk1/_walk2）を再生成する。
色や形を変えたいときはここを編集する。

歩行フレーム：step=0 が静止（idle＝<name>.png）、step=1/2 が左右の踏み出し。
graphics.py が移動アニメ中に walk1/walk2 を交互表示して「歩く」動きになる。
"""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

pygame.init()

S = 64
TRANSPARENT = (0, 0, 0, 0)
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))


def surf():
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    s.fill(TRANSPARENT)
    return s


def px(s, x, y, c):
    if 0 <= x < S and 0 <= y < S:
        s.set_at((int(x), int(y)), c)


def rect(s, x0, y0, x1, y1, c):
    for y in range(int(y0), int(y1) + 1):
        for x in range(int(x0), int(x1) + 1):
            px(s, x, y, c)


def disc(s, cx, cy, r, c):
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + 0.3:
                px(s, x, y, c)


def ball(s, cx, cy, r, base, light, shadow, outline):
    """左上光源の陰影付きの球。outline→shadow→base(上左ずらし)→light。"""
    disc(s, cx, cy, r + 1, outline)
    disc(s, cx, cy, r, shadow)
    disc(s, cx - 1.4, cy - 1.4, r, base)
    disc(s, cx - r * 0.34, cy - r * 0.34, r * 0.52, light)


def outline_pass(s, outline):
    """不透明ピクセルの外側に1pxアウトラインを足して縁を締める。"""
    src = s.copy()
    for y in range(S):
        for x in range(S):
            if src.get_at((x, y))[3] != 0:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < S and 0 <= ny < S and src.get_at((nx, ny))[3] > 200:
                    px(s, x, y, outline)
                    break


def legs(s, step, lx, rx, top, bot, leg, leg_s, boot, boot_s):
    """2本脚を描く。前後に大きくずらして「右足・左足」の踏み出しを表現する。

    step=0：両足そろえ（静止/足をそろえる passing）
    step=1：左足を前（下へ伸ばす）・右足を後ろ（縮める）
    step=2：その逆。1/2 を交互に出すと歩いて見える。
    """
    FWD, BACK = 2, 4   # 前足は下へ+2、後ろ足は上へ-4 ＝大きなストライド
    if step == 1:
        lb, rb = bot + FWD, bot - BACK
    elif step == 2:
        lb, rb = bot - BACK, bot + FWD
    else:
        lb, rb = bot, bot
    for cx, b in ((lx, lb), (rx, rb)):
        rect(s, cx - 1, top, cx + 1, b, leg)
        rect(s, cx - 1, top, cx - 1, b, leg_s)      # 脚の右影
        rect(s, cx - 1, b - 1, cx + 2, b, boot)     # 靴（前向き）
        rect(s, cx - 1, b, cx + 2, b, boot_s)


# ============================================================ プレイヤー（剣士）
def make_player(step):
    s = surf()
    OL = (28, 24, 44)
    skin = (236, 200, 158); skin_l = (250, 226, 192); skin_s = (198, 158, 120)
    hair = (138, 88, 48); hair_l = (178, 124, 70); hair_s = (96, 56, 32)
    tun = (58, 112, 202); tun_l = (100, 158, 236); tun_s = (40, 76, 152)
    pant = (92, 72, 56); pant_s = (60, 46, 36); boot = (66, 48, 38); boot_s = (44, 32, 26)
    steel = (208, 216, 232); steel_l = (246, 250, 255); gold = (226, 186, 78)

    legs(s, step, 27, 37, 49, 57, pant, pant_s, boot, boot_s)
    # 胴（青チュニック）
    ball(s, 32, 41, 11, tun, tun_l, tun_s, OL)
    rect(s, 22, 34, 42, 47, tun)
    rect(s, 22, 34, 24, 47, tun_l); rect(s, 40, 35, 42, 48, tun_s)
    # ベルト＋バックル
    rect(s, 22, 46, 42, 48, pant_s); rect(s, 30, 46, 33, 48, gold)
    # 腕＋手
    rect(s, 18, 35, 21, 46, tun); rect(s, 43, 35, 46, 45, tun)
    rect(s, 18, 44, 21, 47, skin); rect(s, 43, 43, 46, 46, skin)
    # 剣（右手・縦。刃に光のエッジ）
    rect(s, 48, 18, 50, 45, steel); rect(s, 48, 18, 48, 45, steel_l)
    rect(s, 46, 43, 52, 45, gold); rect(s, 48, 45, 50, 49, hair_s)
    px(s, 49, 16, steel_l)
    # 頭
    ball(s, 32, 20, 12, skin, skin_l, skin_s, OL)
    # 髪（上半分＋もみあげ）
    disc(s, 32, 16, 12.5, hair)
    disc(s, 32, 11, 11, hair_l)
    disc(s, 32, 23, 11, skin)            # 顔を出す
    rect(s, 20, 24, 44, 32, skin)
    rect(s, 20, 15, 21, 26, hair); rect(s, 43, 15, 44, 26, hair)  # もみあげ
    px(s, 24, 17, hair_l); px(s, 40, 17, hair_l)
    # 顔
    for ex in (27, 38):
        rect(s, ex - 1, 21, ex + 1, 23, (248, 248, 255))
        rect(s, ex, 22, ex + 1, 23, (44, 46, 78))
        px(s, ex - 1, 21, skin_l)
    px(s, 32, 25, skin_s); px(s, 33, 25, skin_s)        # 鼻
    rect(s, 30, 28, 34, 28, skin_s)                      # 口
    px(s, 23, 25, skin_s); px(s, 41, 25, skin_s)         # 頬
    outline_pass(s, OL)
    return s


# ============================================================ 村人（NPC）
def make_npc(step):
    s = surf()
    OL = (40, 34, 28)
    skin = (232, 196, 156); skin_l = (248, 222, 188); skin_s = (196, 156, 118)
    hair = (180, 174, 166); hair_l = (210, 206, 200); hair_s = (132, 126, 120)
    robe = (120, 138, 86); robe_l = (152, 170, 112); robe_s = (84, 100, 58)
    apron = (150, 116, 74); apron_s = (110, 82, 52)

    legs(s, step, 28, 36, 50, 57, robe_s, (70, 84, 48), (96, 74, 50), (70, 54, 36))
    rect(s, 24, 48, 40, 54, robe_s)      # ローブ裾
    # 胴（ローブ）
    ball(s, 32, 42, 12, robe, robe_l, robe_s, OL)
    rect(s, 20, 34, 44, 50, robe)
    rect(s, 20, 34, 22, 50, robe_l); rect(s, 42, 35, 44, 50, robe_s)
    # 前掛け
    rect(s, 26, 38, 38, 52, apron); rect(s, 26, 38, 27, 52, apron_s)
    rect(s, 26, 52, 38, 52, apron_s)
    # 腕＋手
    rect(s, 16, 36, 19, 48, robe); rect(s, 45, 36, 48, 48, robe)
    rect(s, 16, 46, 19, 49, skin); rect(s, 45, 46, 48, 49, skin)
    # 頭
    ball(s, 32, 20, 12, skin, skin_l, skin_s, OL)
    disc(s, 32, 16, 12.5, hair); disc(s, 32, 11, 11, hair_l)
    disc(s, 32, 24, 11, skin); rect(s, 20, 25, 44, 32, skin)
    rect(s, 19, 16, 20, 28, hair); rect(s, 44, 16, 45, 28, hair)  # もみあげ
    # 顔（穏やか）
    rect(s, 26, 23, 28, 23, OL); rect(s, 37, 23, 39, 23, OL)
    px(s, 32, 26, skin_s)
    rect(s, 29, 29, 35, 29, skin_s); rect(s, 30, 30, 34, 30, skin_s)  # 口ひげ陰
    px(s, 23, 26, skin_s); px(s, 41, 26, skin_s)
    outline_pass(s, OL)
    return s


# ============================================================ ゴブリン
def make_goblin(step):
    s = surf()
    OL = (30, 50, 28)
    skin = (112, 172, 80); skin_l = (154, 204, 114); skin_s = (72, 122, 50)
    loin = (124, 92, 60); loin_s = (88, 64, 42)
    wood = (128, 96, 58); wood_l = (160, 124, 78)
    eye = (250, 226, 90); pupil = (40, 30, 20); tooth = (240, 245, 235)

    legs(s, step, 27, 37, 50, 58, skin, skin_s, skin_s, (52, 92, 36))
    # 胴
    ball(s, 32, 42, 9, skin, skin_l, skin_s, OL)
    rect(s, 24, 38, 40, 50, skin)
    rect(s, 24, 38, 25, 50, skin_l); rect(s, 38, 39, 40, 50, skin_s)
    rect(s, 24, 48, 40, 52, loin); rect(s, 24, 52, 40, 52, loin_s)  # 腰布
    # 腕
    rect(s, 18, 38, 22, 42, skin); rect(s, 42, 40, 46, 46, skin)
    rect(s, 18, 38, 19, 42, skin_s)
    # 棍棒（左手・斜め上）
    for r, (cx, cy) in zip((3, 4, 5, 5), [(16, 36), (14, 31), (12, 26), (12, 22)]):
        disc(s, cx, cy, r, wood)
    disc(s, 11, 22, 2.4, wood_l)
    # 耳（大きくとがる）
    pygame.draw.polygon(s, skin, [(16, 18), (6, 12), (18, 24)])
    pygame.draw.polygon(s, skin, [(48, 18), (58, 12), (46, 24)])
    px(s, 11, 16, skin_l); px(s, 53, 16, skin_l)
    # 頭（横長）
    ball(s, 32, 24, 13, skin, skin_l, skin_s, OL)
    # 顔（つり目・ずる賢い）
    rect(s, 22, 22, 26, 25, eye); rect(s, 38, 22, 42, 25, eye)
    rect(s, 24, 23, 26, 25, pupil); rect(s, 38, 23, 40, 25, pupil)
    rect(s, 21, 20, 25, 21, OL); rect(s, 39, 20, 43, 21, OL)   # つり眉
    # 口（歯をむく）
    rect(s, 25, 30, 39, 32, OL)
    for tx in (27, 30, 33, 36):
        px(s, tx, 30, tooth); px(s, tx, 31, tooth)
    px(s, 22, 28, skin_s); px(s, 42, 28, skin_s)
    px(s, 32, 27, skin_s)                                       # 鼻
    outline_pass(s, OL)
    return s


# ============================================================ スライム
def make_slime(step):
    s = surf()
    OL = (26, 52, 96)
    base = (74, 152, 222); light = (150, 206, 246); shadow = (44, 102, 172)
    deep = (28, 70, 132); hi = (236, 250, 255); eye = (22, 34, 58)

    # step で squash/stretch（弾むブロブ）
    rx = {0: 21, 1: 24, 2: 19}[step]
    ry = {0: 18, 1: 14, 2: 21}[step]
    cy = 58 - ry          # 底を 58 に揃える
    flat = 58

    # ドーム本体（下が平ら）
    for y in range(int(cy - ry), flat + 1):
        for x in range(64):
            if y <= cy:
                if (x - 32) ** 2 / (rx * rx) + (y - cy) ** 2 / (ry * ry) <= 1:
                    px(s, x, y, base)
            elif abs(x - 32) <= rx:
                px(s, x, y, base)
    rect(s, 32 - rx + 1, flat - 1, 32 + rx - 1, flat, deep)  # 底のフチ
    # 陰影（右下を暗く・左上を明るく）
    for y in range(64):
        for x in range(64):
            if s.get_at((x, y))[3] == 0:
                continue
            d = (x - (32 - rx * 0.3)) + (y - cy) * 1.1
            if d > rx * 0.9:
                px(s, x, y, shadow)
            if d > rx * 1.5:
                px(s, x, y, deep)
    disc(s, 32 - rx * 0.35, cy - ry * 0.1, rx * 0.42, light)
    # 内部の気泡
    disc(s, 40, cy + 4, 3, shadow); disc(s, 40, cy + 4, 1.5, light)
    # 大ハイライト
    disc(s, 24, cy - 4, 4, hi); px(s, 30, cy - 7, hi); px(s, 19, cy + 2, hi)
    # 目・口
    eye_y = cy + 2
    rect(s, 25, eye_y, 27, eye_y + 3, eye); rect(s, 37, eye_y, 39, eye_y + 3, eye)
    px(s, 25, eye_y, hi); px(s, 37, eye_y, hi)
    rect(s, 30, eye_y + 5, 34, eye_y + 5, eye)
    px(s, 29, eye_y + 4, eye); px(s, 35, eye_y + 4, eye)
    outline_pass(s, OL)
    return s


# ============================================================ 死体（亡骸＋骨）
def make_corpse(step):
    s = surf()
    OL = (40, 40, 50)
    body = (122, 122, 134); body_l = (152, 152, 164); body_s = (88, 88, 100)
    bone = (226, 220, 206); bone_s = (182, 176, 162)

    for y in range(44, 58):
        for x in range(12, 52):
            if (x - 32) ** 2 / 360 + (y - 53) ** 2 / 60 <= 1:
                px(s, x, y, body)
    for y in range(44, 58):
        for x in range(12, 52):
            if s.get_at((x, y))[3] == 0:
                continue
            if y >= 53:
                px(s, x, y, body_s)
            elif y <= 47:
                px(s, x, y, body_l)
    # 頭蓋骨
    disc(s, 21, 46, 6, bone)
    rect(s, 18, 45, 19, 47, OL); rect(s, 22, 45, 23, 47, OL)  # 眼窩
    px(s, 21, 49, bone_s); px(s, 20, 50, OL); px(s, 22, 50, OL)
    # あばら骨
    for bx in (32, 36, 40):
        rect(s, bx, 48, bx, 54, bone); px(s, bx, 48, bone_s)
    rect(s, 30, 50, 42, 50, bone_s)   # 背骨
    outline_pass(s, OL)
    return s


SPRITES = {
    "player": make_player, "npc": make_npc, "goblin": make_goblin,
    "slime": make_slime, "corpse": make_corpse,
}
WALKERS = {"player", "npc", "goblin", "slime"}  # 歩行フレームを出すもの

for name, fn in SPRITES.items():
    pygame.image.save(fn(0), os.path.join(ASSETS_DIR, f"{name}.png"))
    if name in WALKERS:
        pygame.image.save(fn(1), os.path.join(ASSETS_DIR, f"{name}_walk1.png"))
        pygame.image.save(fn(2), os.path.join(ASSETS_DIR, f"{name}_walk2.png"))

print("regenerated 64x64 character sprites (+walk frames) into", ASSETS_DIR)
