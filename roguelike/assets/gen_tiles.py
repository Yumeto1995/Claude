"""ダンジョンの床・壁ベーステクスチャを pygame だけで生成する（依存追加なし）。

テーマ別に floor/wall/safe_floor の「下地」を作る。壁の向き別の縁取り
（上下左右）や床に落ちる影は graphics.py がこの下地に重ねて描く（オートタイル）。
そのため下地はムラの少ないシームレスな面にしておく。

`python3 gen_tiles.py` で assets 直下に
cave_floor / cave_wall / cave_safe_floor / stone_floor / stone_wall / stone_safe_floor.png
を再生成する。色を変えたいときは PALETTES を編集する。
"""
import os
import random

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

pygame.init()

S = 64
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))

# テーマごとの色。床は壁より明るく＝境界が一目で分かるようにする。
PALETTES = {
    "cave": {
        "floor": (96, 80, 62), "floor_spec": 12,
        "wall": (58, 49, 42), "wall_spec": 9,
        "safe": (74, 100, 90), "safe_spec": 10,
        "pebble_dark": (78, 64, 50), "pebble_light": (116, 99, 78),
    },
    "stone": {
        "floor": (78, 80, 98), "floor_spec": 10,
        "wall": (52, 54, 70), "wall_spec": 8,
        "safe": (72, 102, 96), "safe_spec": 9,
        "pebble_dark": (62, 64, 82), "pebble_light": (98, 100, 120),
    },
}


def _clamp(v):
    return max(0, min(255, v))


def make_surface(base, spec, rng, pebbles=0, peb_colors=None):
    """ベタ色＋微妙なスペックル（±spec）。pebbles 個の小石/欠けを散らす。"""
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    for y in range(S):
        for x in range(S):
            n = rng.randint(-spec, spec)
            s.set_at((x, y), (_clamp(base[0] + n), _clamp(base[1] + n), _clamp(base[2] + n), 255))
    if pebbles and peb_colors:
        for _ in range(pebbles):
            cx, cy = rng.randint(3, S - 4), rng.randint(3, S - 4)
            r = rng.randint(1, 3)
            col = rng.choice(peb_colors)
            for yy in range(cy - r, cy + r + 1):
                for xx in range(cx - r, cx + r + 1):
                    if 0 <= xx < S and 0 <= yy < S and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                        s.set_at((xx, yy), (*col, 255))
    return s


def _blob(s, cx, cy, r, col, density=1.0, rng=None):
    """(cx,cy) 半径 r の塊を density の確率で塗る（小石・土・葉の塊用）。"""
    for yy in range(int(cy - r), int(cy + r + 1)):
        for xx in range(int(cx - r), int(cx + r + 1)):
            if 0 <= xx < S and 0 <= yy < S and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                if rng is None or rng.random() < density:
                    s.set_at((xx, yy), (*col, 255))


def make_grass(rng, variant: int = 0):
    """ふさふさの草地タイル。複数バリアントを敷き分けて密度・彩りを出す。

    variant: 0=基本 / 1=花 / 2=クローバー(濃い草) / 3=小石 / 4=土の擦れ。
    芝の塊ムラ＋短い縦ストロークの葉＋先端ハイライトで、見下ろしの草原に見せる。
    """
    base = (80, 120, 62)
    s = make_surface(base, 9, rng)
    # 下地の明暗ムラ（芝が塊で生えている感じ）
    for _ in range(8):
        cx, cy = rng.randint(4, S - 4), rng.randint(4, S - 4)
        tone = rng.choice([(70, 104, 52), (90, 132, 70)])
        _blob(s, cx, cy, rng.randint(6, 12), tone, density=0.55, rng=rng)
    # 草の葉（短い縦ストローク＋先端の明るい点）
    blade_cols = [(98, 142, 72), (114, 162, 84), (64, 98, 48)]
    for _ in range(95):
        x, y = rng.randint(1, S - 2), rng.randint(4, S - 2)
        h = rng.randint(2, 4)
        c = rng.choice(blade_cols)
        for k in range(h):
            if 0 <= y - k < S:
                s.set_at((x, y - k), (*c, 255))
        if y - h >= 0:
            s.set_at((x, y - h), (152, 198, 112, 255))  # 先端ハイライト

    if variant == 1:        # 小さな花（赤・黄・白・紫）
        for _ in range(rng.randint(2, 4)):
            fx, fy = rng.randint(7, S - 7), rng.randint(7, S - 7)
            petal = rng.choice([(240, 230, 120), (236, 116, 128),
                                (242, 242, 250), (186, 142, 238)])
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                s.set_at((fx + dx, fy + dy), (*petal, 255))
            s.set_at((fx, fy), (250, 208, 86, 255))  # 花芯
    elif variant == 2:      # クローバー風の濃い草の塊
        for _ in range(rng.randint(2, 3)):
            cx, cy = rng.randint(7, S - 7), rng.randint(7, S - 7)
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                           (-1, -1), (1, 1), (1, -1), (-1, 1)):
                if 0 <= cx + dx < S and 0 <= cy + dy < S:
                    s.set_at((cx + dx, cy + dy), (54, 108, 50, 255))
            s.set_at((cx, cy), (44, 92, 44, 255))
    elif variant == 3:      # 小石（明暗2階調で立体感）
        for _ in range(rng.randint(3, 5)):
            sx, sy = rng.randint(5, S - 5), rng.randint(5, S - 5)
            r = rng.randint(1, 3)
            stone = rng.choice([(150, 150, 158), (122, 120, 128)])
            _blob(s, sx, sy, r, stone)
            s.set_at((sx - 1, sy - 1), (196, 196, 204, 255))  # 光
    elif variant == 4:      # 土の擦れ（地面が見える）
        cx, cy = rng.randint(16, S - 16), rng.randint(16, S - 16)
        r = rng.randint(8, 12)
        for yy in range(cy - r, cy + r):
            for xx in range(cx - r, cx + r):
                if 0 <= xx < S and 0 <= yy < S and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    if rng.random() < 0.82:
                        s.set_at((xx, yy), (*rng.choice([(150, 120, 82), (132, 104, 70)]), 255))
    return s


def make_tree(rng):
    """見下ろしの木（丸い樹冠）。塊で配置して森に見せる。"""
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    cx, cy, r = 32, 30, 28
    for y in range(S):
        for x in range(S):
            d = (x - cx) ** 2 + (y - cy) ** 2
            if d <= r * r:
                n = rng.randint(-12, 12)
                base = (44, 84, 44)
                # 左上が明るい
                if (x - cx) + (y - cy) < -8:
                    base = (66, 116, 60)
                elif (x - cx) + (y - cy) > 14:
                    base = (30, 60, 32)
                s.set_at((x, y), (_clamp(base[0] + n), _clamp(base[1] + n), _clamp(base[2] + n), 255))
    return s


def make_wood_wall(rng):
    base = (104, 72, 44)
    s = make_surface(base, 7, rng)
    for y in (0, 21, 42, 63):  # 板の横目地
        for x in range(S):
            s.set_at((x, min(y, S - 1)), (66, 44, 26, 255))
    for x in (0, S - 1):
        for y in range(S):
            s.set_at((x, y), (70, 48, 28, 255))
    return s


def make_wood_floor(rng):
    base = (150, 112, 70)
    s = make_surface(base, 8, rng)
    for y in (0, 32):           # 板目
        for x in range(S):
            s.set_at((x, y), (118, 86, 52, 255))
    for x in (0, S - 1):
        for y in range(S):
            s.set_at((x, y), (122, 90, 56, 255))
    return s


def make_stairs(rng, up: bool):
    """高精細な階段タイル（見下ろし・奥行きのある石段）。

    上り＝暖色の石が上奥へ向かって明るく狭まり、暖色シェブロンが上を指す。
    下り＝寒色の石が下奥へ暗く狭まり、寒色シェブロンが下を指す（穴に降りる感じ）。
    """
    if up:
        stone = (120, 100, 72); light = (168, 144, 100); dark = (74, 60, 42)
        far = (196, 172, 124)            # 奥（上）ほど明るい
        arrow = (250, 226, 150)
    else:
        stone = (72, 84, 110); light = (110, 124, 156); dark = (34, 42, 64)
        far = (20, 26, 44)               # 奥（下）ほど暗い（穴）
        arrow = (150, 220, 255)
    s = make_surface(stone, 6, rng)
    pygame.draw.rect(s, dark, (0, 0, S, S))            # 枠の下地
    n = 7
    top, bot = 4, 60
    sh = (bot - top) / n
    for i in range(n):
        # i=0 が手前、i=n-1 が奥。奥ほど横幅が狭まり（台形）色が far に寄る
        depth = i / (n - 1)
        if not up:
            depth = depth           # 下り：下が奥
        taper = int(2 + depth * 16)
        y0 = int(top + i * sh)
        y1 = int(top + (i + 1) * sh) - 1
        # 奥行きで色を補間
        col = tuple(int(stone[k] + (far[k] - stone[k]) * depth) for k in range(3))
        edge = tuple(int(c * 0.6) for c in col)
        # 段板（上面）と段差（前面の影）
        rect = (taper, y0, S - taper - 1, y1 - 1)
        for yy in range(y0, y1):
            for xx in range(taper, S - taper):
                s.set_at((xx, yy), col)
        # 段板の手前側ハイライト・奥側の段差影
        for xx in range(taper, S - taper):
            s.set_at((xx, y0), tuple(min(255, c + 40) for c in col))
            s.set_at((xx, max(y0, y1 - 1)), edge)
        # 側面の石壁
        for xx in (taper - 1, S - taper):
            for yy in range(y0, y1):
                if 0 <= xx < S:
                    s.set_at((xx, yy), dark)
    # 方向シェブロン（二段の矢印）。up=▲（先端が上）/ down=▼（先端が下）
    for j in (0, 1):
        tip = (28 + j * 9) if up else (44 - j * 9)
        for k in range(7):
            yy = (tip + k) if up else (tip - k)   # 先端から末広がり
            for xx in range(32 - k, 32 + k + 1):
                if 0 <= yy < S:
                    s.set_at((xx, yy), arrow)
    pygame.draw.rect(s, dark, (0, 0, S, S), 2)
    return s


def make_door(rng):
    """木のドア（枠＋取っ手）。建物の壁面にはめ込まれる。"""
    s = make_wood_wall(rng)
    pygame.draw.rect(s, (150, 110, 66, 255), (10, 6, 44, 58))     # 扉板
    pygame.draw.rect(s, (96, 66, 38, 255), (10, 6, 44, 58), 3)    # 枠
    for yy in range(10, 60):                                       # 縦の板目
        s.set_at((32, yy), (110, 78, 46, 255))
    pygame.draw.circle(s, (228, 196, 96, 255), (46, 36), 3)       # 取っ手
    return s


def make_meadow_floor(rng, safe: bool = False):
    """草原ダンジョンの床＝踏み固めた土。小石と、縁から覗く草でグラスランド感を出す。

    safe=True はセーフルーム用に少し緑がかった明るい土にして見分けやすくする。
    """
    base = (156, 126, 86) if not safe else (150, 150, 104)
    s = make_surface(base, 10, rng)
    tones = ([(138, 110, 74), (172, 142, 100)] if not safe
             else [(132, 142, 96), (168, 168, 120)])
    for _ in range(7):  # 土の明暗ムラ
        cx, cy = rng.randint(4, S - 4), rng.randint(4, S - 4)
        _blob(s, cx, cy, rng.randint(6, 11), rng.choice(tones), density=0.5, rng=rng)
    for _ in range(rng.randint(4, 7)):  # 小石
        sx, sy = rng.randint(4, S - 4), rng.randint(4, S - 4)
        _blob(s, sx, sy, rng.randint(1, 2), rng.choice([(120, 108, 92), (150, 140, 124)]))
    for _ in range(rng.randint(8, 16)):  # 縁から覗く草
        x, y = rng.randint(1, S - 2), rng.randint(4, S - 2)
        c = rng.choice([(96, 140, 70), (76, 116, 56)])
        for k in range(rng.randint(2, 3)):
            if 0 <= y - k < S:
                s.set_at((x, y - k), (*c, 255))
    return s


def make_meadow_wall(rng):
    """草原ダンジョンの壁＝丈の高い茂み（暗緑の塊＋葉先ハイライト）に岩を少し混ぜる。"""
    base = (52, 92, 46)
    s = make_surface(base, 10, rng)
    for _ in range(10):  # 茂みの塊
        cx, cy = rng.randint(2, S - 2), rng.randint(2, S - 2)
        tone = rng.choice([(42, 78, 40), (66, 112, 56), (80, 130, 66)])
        _blob(s, cx, cy, rng.randint(5, 11), tone, density=0.6, rng=rng)
    for _ in range(120):  # 葉
        x, y = rng.randint(0, S - 1), rng.randint(3, S - 1)
        c = rng.choice([(80, 130, 62), (96, 150, 74), (40, 74, 38)])
        for k in range(rng.randint(2, 5)):
            if 0 <= y - k < S:
                s.set_at((x, y - k), (*c, 255))
        if rng.random() < 0.3 and y - 5 >= 0:
            s.set_at((x, y - 5), (142, 188, 102, 255))  # 葉先ハイライト
    for _ in range(rng.randint(1, 2)):  # 岩
        rx, ry = rng.randint(8, S - 8), rng.randint(8, S - 8)
        r = rng.randint(4, 6)
        _blob(s, rx, ry, r, (120, 118, 124))
        _blob(s, rx - 1, ry - 1, max(1, r - 2), (152, 150, 156))
    return s


def generate():
    vrng = random.Random(20240601)
    extras = {
        "grass": make_grass(vrng, 0),
        "grass_flower": make_grass(vrng, 1),
        "grass_clover": make_grass(vrng, 2),
        "grass_stone": make_grass(vrng, 3),
        "grass_dirt": make_grass(vrng, 4),
        "tree": make_tree(vrng),
        "wood_wall": make_wood_wall(vrng), "wood_floor": make_wood_floor(vrng),
        "door": make_door(vrng),
        "stairs_up": make_stairs(vrng, up=True),
        "stairs_down": make_stairs(vrng, up=False),
        # 草原ダンジョン（浅層テーマ）：床=土 / 壁=茂み
        "meadow_floor": make_meadow_floor(vrng),
        "meadow_safe_floor": make_meadow_floor(vrng, safe=True),
        "meadow_wall": make_meadow_wall(vrng),
    }
    for name, surf in extras.items():
        pygame.image.save(surf, os.path.join(ASSETS_DIR, f"{name}.png"))
    for theme, p in PALETTES.items():
        rng = random.Random(hash(theme) & 0xFFFF)  # テーマ固定シードで再現性
        peb = [p["pebble_dark"], p["pebble_light"]]
        floor = make_surface(p["floor"], p["floor_spec"], rng, pebbles=10, peb_colors=peb)
        wall = make_surface(p["wall"], p["wall_spec"], rng, pebbles=6, peb_colors=peb)
        safe = make_surface(p["safe"], p["safe_spec"], rng, pebbles=8,
                            peb_colors=[(60, 86, 78), (96, 122, 112)])
        pygame.image.save(floor, os.path.join(ASSETS_DIR, f"{theme}_floor.png"))
        pygame.image.save(wall, os.path.join(ASSETS_DIR, f"{theme}_wall.png"))
        pygame.image.save(safe, os.path.join(ASSETS_DIR, f"{theme}_safe_floor.png"))
    print("regenerated dungeon tiles into", ASSETS_DIR)


if __name__ == "__main__":
    generate()
