"""64×64 キャラスプライトを pygame だけで生成する（依存追加なし）。

向き（下/上/左）×ポーズ（静止/歩行2コマ/攻撃）を生成する。右向きは描画側で
左向きを水平反転して使う（graphics.load_sprites）。全身（脚＋腕）を振って歩き、
攻撃は向いた方向へ武器を突き出す。

出力例： player_down.png / player_down_walk1.png / player_left_attack.png …
静止の下向き（例 player_down.png）と、後方互換の素キー（player.png＝下向き静止）も出す。

色や形を変えたいときは PALETTES と draw_humanoid を編集する。
"""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

pygame.init()

S = 64
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
DIRS = ("down", "up", "left")
POSES = ("idle", "walk1", "walk2", "attack")


def surf():
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
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


def _mix(a, b, t):
    """色 a→b を t で線形補間。"""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ball(s, cx, cy, r, base, light, shadow, ol):
    """光源=左上の球。輪郭→最暗→影→ベース→ハイライト→鏡面の5階調＋鏡面で立体に。"""
    deep = _mix(shadow, ol, 0.5)
    disc(s, cx, cy, r + 1, ol)                                  # 輪郭
    disc(s, cx, cy, r, deep)                                    # 右下＝最暗
    disc(s, cx - r * 0.18, cy - r * 0.18, r * 0.94, shadow)     # 影
    disc(s, cx - r * 0.36, cy - r * 0.36, r * 0.80, base)       # ベース
    disc(s, cx - r * 0.50, cy - r * 0.50, r * 0.46, light)      # ハイライト
    disc(s, cx - r * 0.58, cy - r * 0.58, r * 0.20,
         _mix(light, (255, 255, 255), 0.55))                    # 鏡面


def outline_pass(s, ol):
    src = s.copy()
    for y in range(S):
        for x in range(S):
            if src.get_at((x, y))[3] != 0:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < S and 0 <= ny < S and src.get_at((nx, ny))[3] > 200:
                    px(s, x, y, ol)
                    break


# ============================================================ 共通の人型描画
def _limb(s, cx, top, bot, w, col, shade):
    """縦の手足（円筒）。光源=左上：左端に光、右端に影。"""
    rect(s, cx - w, top, cx + w, bot, col)
    rect(s, cx - w, top, cx - w, bot, _mix(col, (255, 255, 255), 0.22))  # 左＝光
    rect(s, cx + w, top, cx + w, bot, shade)                            # 右＝影


def draw_humanoid(P, direction, pose):
    """人型キャラ（プレイヤー/村人/ゴブリン）を向き・ポーズ付きで描く。"""
    s = surf()
    OL = P["OL"]
    bob = -1 if pose in ("walk1", "walk2") else 0   # 歩行中は全身が1px浮く
    lean = 0
    if pose == "attack":
        lean = {"down": (0, 1), "up": (0, -1), "left": (-2, 0)}[direction][0]

    # ---- マント（体の後ろ＝最初に描く。歩行で少し揺れる）----
    if P.get("cape"):
        _cape(s, P, direction, pose, bob, lean)

    # ---- 脚（全身歩行：左右交互に踏み出す）----
    lx, rx = 27, 37
    ltop, lbot = 49 + bob, 57
    if direction == "left":
        lx, rx = 29, 35  # 前足・後ろ足
    if pose == "walk1":
        loff, roff = (2, -3)      # 左/前を踏み出し
    elif pose == "walk2":
        loff, roff = (-3, 2)
    else:
        loff, roff = (0, 0)
    for cx, off in ((lx + lean, loff), (rx + lean, roff)):
        b = lbot + off
        _limb(s, cx, ltop, b, 2, P["leg"], P["leg_s"])
        rect(s, cx - 2, b - 1, cx + 2, b, P["boot"])
        rect(s, cx - 2, b, cx + 2, b, P["boot_s"])

    # ---- 胴 ----
    bx0, bx1 = 22 + lean, 42 + lean
    by0, by1 = 31 + bob, 48 + bob
    if direction == "left":
        bx0, bx1 = 25 + lean, 39 + lean
    ball(s, (bx0 + bx1) // 2, by1 - 4, (bx1 - bx0) // 2 + 1, P["top"], P["top_l"], P["top_s"], OL)
    rect(s, bx0, by0, bx1, by1, P["top"])
    rect(s, bx0, by0, bx0 + 1, by1, P["top_l"])
    rect(s, bx1 - 1, by0 + 1, bx1, by1, P["top_s"])
    if P.get("belt"):
        rect(s, bx0, by1 - 2, bx1, by1, P["belt"])
        if P.get("buckle"):
            rect(s, (bx0 + bx1) // 2 - 1, by1 - 2, (bx0 + bx1) // 2 + 1, by1, P["buckle"])
    if P.get("loincloth"):  # 腰布（ゴブリン等）：胴の下に台形で垂らす
        lc, lc_s = P["loincloth"], P["loincloth_s"]
        cxm = (bx0 + bx1) // 2
        rect(s, bx0 + 1, by1 - 1, bx1 - 1, by1 + 4, lc)
        rect(s, cxm - 3, by1 + 4, cxm + 3, by1 + 7, lc)
        rect(s, bx0 + 1, by1 + 3, bx1 - 1, by1 + 4, lc_s)
    if P.get("strap"):      # 斜め掛けの革ベルト
        st = P["strap"]
        for i in range(0, 18):
            px(s, bx0 + 2 + i, by0 + 1 + i, st)
            px(s, bx0 + 3 + i, by0 + 1 + i, st)

    # ---- 腕（歩行で前後にスイング。攻撃は武器側を前へ）----
    arm_y0, arm_y1 = 34 + bob, 45 + bob
    swing = {"walk1": (2, -2), "walk2": (-2, 2), "idle": (0, 0), "attack": (0, 0)}[pose]
    if direction == "left":
        # 横向き：手前の腕だけ見せる（前後にスイング）
        fa = 19 + lean + (swing[0])
        _limb(s, fa, arm_y0 + max(0, -swing[0]), arm_y1, 2, P["top"], P["top_s"])
        rect(s, fa - 2, arm_y1, fa + 1, arm_y1 + 2, P["skin"])
    else:
        la, ra = bx0 - 1, bx1 + 1
        _limb(s, la, arm_y0 + swing[0], arm_y1 + swing[0], 1, P["top"], P["top_s"])
        _limb(s, ra, arm_y0 + swing[1], arm_y1 + swing[1], 1, P["top"], P["top_s"])
        rect(s, la - 1, arm_y1 + swing[0], la + 1, arm_y1 + 2 + swing[0], P["skin"])
        rect(s, ra - 1, arm_y1 + swing[1], ra + 1, arm_y1 + 2 + swing[1], P["skin"])

    # ---- 盾（腕の上に構える丸盾。武器と反対側）----
    if P.get("shield"):
        _shield(s, P, direction, pose, bob, lean)

    # ---- 頭 ----
    hcx, hcy, hr = 32 + lean, 20 + bob, 12
    ball(s, hcx, hcy, hr, P["skin"], P["skin_l"], P["skin_s"], OL)
    _head_features(s, P, direction, hcx, hcy, hr)
    if P.get("spiky"):
        _hair_spikes(s, P, direction, hcx, hcy, hr)

    # ---- 耳（ゴブリン）----
    if P.get("ears"):
        _ears(s, P, direction, hcx, hcy)

    # ---- 武器 ----
    if P.get("weapon"):
        _weapon(s, P, direction, pose, bob, lean)

    outline_pass(s, OL)
    return s


def _head_features(s, P, direction, hcx, hcy, hr):
    OL = P["OL"]
    skin, skin_s = P["skin"], P["skin_s"]
    hair, hair_l = P["hair"], P["hair_l"]
    if direction == "up":
        # 後頭部：髪で覆う、顔は無し
        disc(s, hcx, hcy - 1, hr, hair)
        disc(s, hcx, hcy - 4, hr - 1, hair_l)
        rect(s, hcx - hr, hcy + 4, hcx + hr, hcy + hr, skin_s)  # うなじ
        return
    # 髪（上半分）
    disc(s, hcx, hcy - 4, hr + 0.5, hair)
    disc(s, hcx, hcy - 8, hr - 1, hair_l)
    disc(s, hcx, hcy + 3, hr - 1, skin)        # 顔を出す
    if direction == "down":
        eye = P.get("eye")
        for ex in (hcx - 5, hcx + 4):
            if eye:  # ゴブリン等の色付き目
                rect(s, ex - 1, hcy + 1, ex + 1, hcy + 2, eye)
                px(s, ex, hcy + 1, OL)
            else:
                rect(s, ex - 1, hcy, ex + 1, hcy + 2, (248, 248, 255))
                rect(s, ex, hcy + 1, ex + 1, hcy + 2, (44, 46, 78))
        px(s, hcx, hcy + 4, skin_s)
        if P.get("mouth") == "fang":
            rect(s, hcx - 4, hcy + 6, hcx + 4, hcy + 7, OL)
            for tx in range(hcx - 3, hcx + 4, 2):
                px(s, tx, hcy + 6, (240, 245, 235))
        else:
            rect(s, hcx - 2, hcy + 6, hcx + 2, hcy + 6, skin_s)
    else:  # left（横顔）：手前(左)に目1つ＋鼻
        eye = P.get("eye")
        ex = hcx - 5
        if eye:
            rect(s, ex - 1, hcy + 1, ex, hcy + 2, eye); px(s, ex, hcy + 1, OL)
        else:
            rect(s, ex - 1, hcy, ex, hcy + 2, (248, 248, 255)); px(s, ex - 1, hcy + 1, (44, 46, 78))
        px(s, hcx - hr + 1, hcy + 3, skin_s)   # 鼻先
        rect(s, hcx - 5, hcy + 6, hcx - 1, hcy + 6, skin_s)
        # 後頭部側を髪で厚く
        rect(s, hcx + 2, hcy - hr + 4, hcx + hr, hcy + 4, hair)


def _ears(s, P, direction, hcx, hcy):
    skin, skin_l = P["skin"], P["skin_l"]
    if direction == "left":
        pygame.draw.polygon(s, skin, [(hcx + 8, hcy - 4), (hcx + 18, hcy - 9), (hcx + 8, hcy + 2)])
        px(s, hcx + 13, hcy - 5, skin_l)
    else:
        pygame.draw.polygon(s, skin, [(hcx - 9, hcy - 3), (hcx - 19, hcy - 8), (hcx - 8, hcy + 3)])
        pygame.draw.polygon(s, skin, [(hcx + 9, hcy - 3), (hcx + 19, hcy - 8), (hcx + 8, hcy + 3)])
        px(s, hcx - 14, hcy - 4, skin_l); px(s, hcx + 14, hcy - 4, skin_l)


def _cape(s, P, direction, pose, bob, lean):
    """背中の赤マント（体の後ろに先に描く）。歩行で裾が少し揺れる。"""
    cape, cs = P["cape"], P["cape_s"]
    sway = {"walk1": 2, "walk2": -2}.get(pose, 0)
    if direction == "up":   # 後ろ姿＝マントが背中を覆う
        pygame.draw.polygon(s, cape, [(19 + lean, 30 + bob), (45 + lean, 30 + bob),
                                      (47 + lean + sway, 61), (17 + lean + sway, 61)])
        rect(s, 31 + lean, 32 + bob, 33 + lean, 59, cs)             # 中央の縦の合わせ
    elif direction == "left":  # 横向き＝後ろ（右）へ流れる
        pygame.draw.polygon(s, cape, [(33 + lean, 32 + bob), (41 + lean, 33 + bob),
                                      (45 + lean + sway, 57), (33 + lean + sway, 57)])
        rect(s, 41 + lean, 36 + bob, 43 + lean, 55, cs)
    else:                   # 正面＝肩の両脇と脚の裏から覗く
        pygame.draw.polygon(s, cape, [(22 + lean, 33 + bob), (42 + lean, 33 + bob),
                                      (48 + lean + sway, 60), (16 + lean + sway, 60)])
        pygame.draw.polygon(s, cs, [(32 + lean, 33 + bob), (42 + lean, 33 + bob),
                                    (48 + lean + sway, 60), (32 + lean + sway, 60)])


def _shield(s, P, direction, pose, bob, lean):
    """十字紋の丸盾（武器と反対＝左側に構える）。"""
    face, rim, em = P["shield_face"], P["shield_rim"], P["shield_emblem"]
    cx, cy, r = 17 + lean, 40 + bob, 8
    if direction == "up":   # 後ろ向きは左肩越しに少しだけ
        cx, cy, r = 18 + lean, 37 + bob, 6
    disc(s, cx, cy, r + 1, rim)
    disc(s, cx, cy, r, face)
    disc(s, cx - 2, cy - 2, max(2, r * 0.4), _mix(face, (255, 255, 255), 0.30))  # 受光
    rect(s, cx - 1, cy - 5, cx + 1, cy + 5, em)     # 十字（縦）
    rect(s, cx - 4, cy - 1, cx + 4, cy + 1, em)     # 十字（横）


def _hair_spikes(s, P, direction, hcx, hcy, hr):
    """逆立った髪（トゲ）。頭頂のまわりに三角を並べる。"""
    hair, hl = P["hair"], P["hair_l"]
    base_y = hcy - hr + 3
    for sx, tip in ((-9, 1), (-4, -2), (1, -3), (6, -2), (10, 1)):
        x = hcx + sx
        pygame.draw.polygon(s, hair, [(x - 3, base_y + 3), (x, base_y - 6 + tip), (x + 3, base_y + 3)])
    pygame.draw.polygon(s, hl, [(hcx - 7, base_y + 2), (hcx - 4, base_y - 7), (hcx - 2, base_y + 2)])


def _weapon(s, P, direction, pose, bob, lean):
    kind = P["weapon"]
    if kind == "sword":
        blade, light, hilt = P["steel"], P["steel_l"], P["gold"]
        if pose == "attack":
            if direction == "down":
                rect(s, 30, 49, 33, 60, blade); rect(s, 30, 49, 30, 60, light)
                rect(s, 28, 48, 35, 49, hilt)
            elif direction == "up":
                rect(s, 30, 4, 33, 18, blade); rect(s, 30, 4, 30, 18, light)
                rect(s, 28, 18, 35, 19, hilt)
            else:  # left
                rect(s, 2, 33, 16, 36, blade); rect(s, 2, 33, 16, 33, light)
                rect(s, 16, 31, 17, 38, hilt)
        else:
            x = 47 + lean
            rect(s, x, 22 + bob, x + 2, 46 + bob, blade)
            rect(s, x, 22 + bob, x, 46 + bob, light)
            rect(s, x - 2, 45 + bob, x + 4, 46 + bob, hilt)
            px(s, x + 1, 20 + bob, light)
    elif kind == "club":
        wood, wl = P["wood"], P["wood_l"]
        if pose == "attack":
            head = {"down": (32, 56), "up": (32, 8), "left": (8, 34)}[direction]
            for r, (cx, cy) in zip((3, 4, 5), [(32, 46), head, head]):
                disc(s, cx, cy, r, wood)
            disc(s, head[0], head[1], 2, wl)
        else:
            for r, (cx, cy) in zip((3, 4, 5, 5), [(16, 36 + bob), (14, 31 + bob), (12, 26 + bob), (12, 22 + bob)]):
                disc(s, cx, cy, r, wood)
            disc(s, 11, 22 + bob, 2.4, wl)


# ============================================================ パレット
PALETTES = {
    "player": {   # 添付の冒険者デザイン：茶のトゲ髪・緑チュニック・赤マント・十字の丸盾・白ズボン・茶ブーツ
        "OL": (30, 26, 40),
        "skin": (238, 198, 152), "skin_l": (252, 224, 186), "skin_s": (198, 154, 112),
        "hair": (120, 78, 42), "hair_l": (166, 114, 64), "hair_s": (84, 52, 28),
        "top": (74, 130, 64), "top_l": (106, 166, 92), "top_s": (50, 96, 46),   # 緑チュニック
        "belt": (96, 64, 40), "buckle": (226, 186, 78),
        "leg": (224, 216, 198), "leg_s": (178, 170, 150),                       # 白ズボン
        "boot": (104, 68, 40), "boot_s": (72, 46, 28),
        "weapon": "sword", "steel": (212, 220, 236), "steel_l": (248, 250, 255), "gold": (226, 186, 78),
        "cape": (190, 44, 46), "cape_s": (132, 28, 36),                         # 赤マント
        "shield": True, "shield_face": (150, 110, 66),                          # 十字の丸盾
        "shield_rim": (104, 74, 46), "shield_emblem": (236, 236, 228),
        "spiky": True,
        "mouth": "normal",
    },
    "npc": {
        "OL": (40, 34, 28),
        "skin": (232, 196, 156), "skin_l": (248, 222, 188), "skin_s": (196, 156, 118),
        "hair": (180, 174, 166), "hair_l": (210, 206, 200), "hair_s": (132, 126, 120),
        "top": (120, 138, 86), "top_l": (152, 170, 112), "top_s": (84, 100, 58),
        "belt": (150, 116, 74),
        "leg": (96, 74, 50), "leg_s": (70, 54, 36), "boot": (96, 74, 50), "boot_s": (70, 54, 36),
        "mouth": "normal",
    },
    "goblin": {
        "OL": (24, 44, 22),
        "skin": (120, 184, 84), "skin_l": (168, 218, 122), "skin_s": (74, 128, 52),
        "hair": (86, 134, 60), "hair_l": (118, 166, 84), "hair_s": (56, 96, 42),
        "top": (120, 88, 56), "top_l": (148, 114, 76), "top_s": (84, 60, 40),
        "leg": (102, 158, 74), "leg_s": (66, 112, 48), "boot": (70, 52, 36), "boot_s": (48, 36, 26),
        "loincloth": (158, 122, 70), "loincloth_s": (112, 84, 48),
        "strap": (70, 50, 34),
        "weapon": "club", "wood": (128, 96, 58), "wood_l": (160, 124, 78),
        "ears": True, "eye": (252, 208, 70), "mouth": "fang",
    },
}


# ============================================================ スライム・死体（無方向）
def make_slime(step):
    s = surf()
    OL = (26, 52, 96)
    base = (74, 152, 222); light = (150, 206, 246); shadow = (44, 102, 172)
    deep = (28, 70, 132); hi = (236, 250, 255); eye = (22, 34, 58)
    rx = {0: 21, 1: 24, 2: 19}[step]; ry = {0: 18, 1: 14, 2: 21}[step]
    cy = 58 - ry; flat = 58
    for y in range(int(cy - ry), flat + 1):
        for x in range(64):
            if y <= cy:
                if (x - 32) ** 2 / (rx * rx) + (y - cy) ** 2 / (ry * ry) <= 1:
                    px(s, x, y, base)
            elif abs(x - 32) <= rx:
                px(s, x, y, base)
    rect(s, 32 - rx + 1, flat - 1, 32 + rx - 1, flat, deep)
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
    disc(s, 40, cy + 4, 3, shadow); disc(s, 40, cy + 4, 1.5, light)
    disc(s, 24, cy - 4, 4, hi); px(s, 30, cy - 7, hi); px(s, 19, cy + 2, hi)
    ey = cy + 2
    rect(s, 25, ey, 27, ey + 3, eye); rect(s, 37, ey, 39, ey + 3, eye)
    px(s, 25, ey, hi); px(s, 37, ey, hi)
    rect(s, 30, ey + 5, 34, ey + 5, eye); px(s, 29, ey + 4, eye); px(s, 35, ey + 4, eye)
    outline_pass(s, OL)
    return s


def make_corpse():
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
    disc(s, 21, 46, 6, bone)
    rect(s, 18, 45, 19, 47, OL); rect(s, 22, 45, 23, 47, OL)
    px(s, 21, 49, bone_s); px(s, 20, 50, OL); px(s, 22, 50, OL)
    for bx in (32, 36, 40):
        rect(s, bx, 48, bx, 54, bone); px(s, bx, 48, bone_s)
    rect(s, 30, 50, 42, 50, bone_s)
    outline_pass(s, OL)
    return s


# ============================================================ 量子化（太いドット化）
# 2000年代初頭（GBA期）風の太いドットにするため、描いた絵を粗いグリッドへ
# スナップする。PIX_BLOCK=2 なら 32×32 相当（ドット2倍）。64 を割り切る値にすると
# タイルの継ぎ目が保たれる（2 や 4）。1 で無効（従来の細かいドット）。
PIX_BLOCK = 2


def pixelate(s, block=PIX_BLOCK):
    """各 block×block をブロック中心の色で塗りつぶし、太いドットに量子化する。"""
    if block <= 1:
        return s
    out = pygame.Surface((S, S), pygame.SRCALPHA)
    for by in range(0, S, block):
        for bx in range(0, S, block):
            col = s.get_at((min(S - 1, bx + block // 2), min(S - 1, by + block // 2)))
            out.fill(col, (bx, by, block, block))
    return out


# ============================================================ 出力
def _save(s, name):
    pygame.image.save(pixelate(s), os.path.join(ASSETS_DIR, f"{name}.png"))


def generate():
    POSE_SUFFIX = {"idle": "", "walk1": "_walk1", "walk2": "_walk2", "attack": "_attack"}
    for name, P in PALETTES.items():
        for d in DIRS:
            for pose in POSES:
                _save(draw_humanoid(P, d, pose), f"{name}_{d}{POSE_SUFFIX[pose]}")
        _save(draw_humanoid(P, "down", "idle"), name)  # 後方互換＆アイコン用
    # スライム（無方向・squashで弾む）
    _save(make_slime(0), "slime")
    _save(make_slime(1), "slime_walk1")
    _save(make_slime(2), "slime_walk2")
    # 死体
    _save(make_corpse(), "corpse")
    print("regenerated directional character sprites into", ASSETS_DIR)


if __name__ == "__main__":
    generate()
