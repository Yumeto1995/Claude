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


def make_grass(rng):
    base = (74, 112, 58)
    s = make_surface(base, 12, rng)
    for _ in range(40):  # 草の葉のちらつき
        x, y = rng.randint(1, S - 2), rng.randint(1, S - 3)
        c = rng.choice([(96, 140, 70), (60, 96, 48)])
        s.set_at((x, y), (*c, 255)); s.set_at((x, y + 1), (*c, 255))
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


def generate():
    vrng = random.Random(20240601)
    extras = {
        "grass": make_grass(vrng), "tree": make_tree(vrng),
        "wood_wall": make_wood_wall(vrng), "wood_floor": make_wood_floor(vrng),
        "door": make_door(vrng),
        "stairs_up": make_stairs(vrng, up=True),
        "stairs_down": make_stairs(vrng, up=False),
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
