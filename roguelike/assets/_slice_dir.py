"""1方向＝1枚の単一方向シートから player_<dir> 系を切り出す（向き取り違えゼロ）。

使い方: SHEET=<path> DIR=down python3 _slice_dir.py   （DIR: down/up/left/right）
背景色は四隅から自動判定（明/暗どちらでも）。コンテンツ行を検出し、その中の列を
検出して横一列を分割。各セルは背景を縁から塗りつぶして透過→最大連結成分→トリム→64×64。
NAME 環境変数でキャラ名（既定 player）。OUT_DIR 出力（既定 /tmp/dir）。COPY=1 で assets へ。
"""
import os
from collections import deque

os.environ["SDL_VIDEODRIVER"] = "dummy"
import numpy as np
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.environ["SHEET"] if os.path.isabs(os.environ.get("SHEET", "")) else os.path.join(HERE, os.environ["SHEET"])
DIR = os.environ.get("DIR", "down")
NAME = os.environ.get("NAME", "player")
OUT_DIR = os.environ.get("OUT_DIR", "/tmp/dir")
os.makedirs(OUT_DIR, exist_ok=True)
TILE = 64
img = pygame.image.load(SHEET).convert_alpha()
W, H = img.get_size()

rgb_full = pygame.surfarray.array3d(img).astype(int)
MX, MN, VAL = rgb_full.max(2), rgb_full.min(2), rgb_full.mean(2)
# 背景判定（四隅の明るさで明/暗を決める）
# 背景の性質を縁(4px枠)のピクセルから判定する。
R_full, B_full = rgb_full[:, :, 0], rgb_full[:, :, 2]
edge = np.zeros((W, H), bool); edge[:4] = edge[-4:] = True; edge[:, :4] = edge[:, -4:] = True
e_br = float(np.mean((B_full - R_full)[edge]))       # 縁の青み(b-r)平均
e_val = float(np.mean(VAL[edge]))
BLUISH = e_br > 8                                      # 青み市松か


def bg_mask(mx, mn, val, r, b):
    """背景マスク。青み市松は青み(b>r)で判定（暖色/緑/赤の本体は除外。鋼剣は同色だが
    輪郭で囲まれ縁塗りつぶしでは残る）。白背景は純白帯、暗背景は暗い無彩色。"""
    if BLUISH:
        # 背景は強い青み(b-r≈25)。クリーム白ズボン(b-r≈6)は本体なので b>r+11 で守る。
        return (b > r + 11) & (mx - mn < 46) & (val >= 60) & (val <= 222)
    if e_val >= 200:                                  # 白背景
        return (mx - mn < 40) & (val >= 196)
    return (mx - mn < 26) & (val <= e_val + 35) & (val >= 40)  # 暗背景


BG = bg_mask(MX, MN, VAL, R_full, B_full)


def bands(prof, thr, minlen=10):
    out = []; s = None
    for i, v in enumerate(prof):
        if v > thr and s is None:
            s = i
        elif v <= thr and s is not None:
            if i - s >= minlen:
                out.append((s, i))
            s = None
    if s is not None:
        out.append((s, len(prof)))
    return out


op = (~BG)
# コンテンツ行（最初の大きな帯＝スプライト行）
rb = bands(op.sum(0), W * 0.04, 16)
y0, y1 = rb[0]
# 足先まで含める（青み判定の修正でズボン/脚が残る）。ラベルは下の別成分なので
# keep_largest が除去する→下を詰めず、念のため少し余白を足す。
y0 = max(0, y0 - 4)
y1 = min(H, y1 + 8)
# 列検出
cb = bands(op[:, y0:y1].sum(1), (y1 - y0) * 0.06, 16)
print(f"DIR={DIR} content row y {y0}-{y1}, {len(cb)} columns: {[(a+b)//2 for a,b in cb]}")


def remove_bg(cell):
    rgb = pygame.surfarray.array3d(cell).astype(int)
    mx, mn, val = rgb.max(2), rgb.min(2), rgb.mean(2)
    bgm = bg_mask(mx, mn, val, rgb[:, :, 0], rgb[:, :, 2])
    w, h = cell.get_size()
    vis = np.zeros((w, h), bool); dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if bgm[x, y]:
                vis[x, y] = True; dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if bgm[x, y] and not vis[x, y]:
                vis[x, y] = True; dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and bgm[nx, ny] and not vis[nx, ny]:
                vis[nx, ny] = True; dq.append((nx, ny))
    out = cell.copy(); a = pygame.surfarray.pixels_alpha(out); a[vis] = 0; del a
    return out


def keep_largest(cell):
    op2 = pygame.surfarray.array_alpha(cell) > 60
    w, h = cell.get_size(); lab = np.zeros((w, h), np.int32)
    best, bid, cur = 0, 0, 0
    for sx in range(w):
        for sy in range(h):
            if op2[sx, sy] and lab[sx, sy] == 0:
                cur += 1; sz = 0; dq = deque([(sx, sy)]); lab[sx, sy] = cur
                while dq:
                    x, y = dq.popleft(); sz += 1
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and op2[nx, ny] and lab[nx, ny] == 0:
                            lab[nx, ny] = cur; dq.append((nx, ny))
                if sz > best:
                    best, bid = sz, cur
    if bid:
        a = pygame.surfarray.pixels_alpha(cell); a[lab != bid] = 0; del a
    return cell


def trim_center(cell, target=60):
    al = pygame.surfarray.array_alpha(cell); xs, ys = np.where(al > 80)
    if len(xs) == 0:
        return None
    x0, x1, y0_, y1_ = xs.min(), xs.max(), ys.min(), ys.max()
    sub = cell.subsurface((int(x0), int(y0_), int(x1 - x0 + 1), int(y1_ - y0_ + 1))).copy()
    w, h = sub.get_size(); sc = min(target / w, target / h)
    nw, nh = max(1, round(w * sc)), max(1, round(h * sc))
    sub = pygame.transform.smoothscale(sub, (nw, nh))
    o = pygame.Surface((TILE, TILE), pygame.SRCALPHA); o.blit(sub, ((TILE - nw) // 2, (TILE - nh) // 2))
    return o


POSES = ["", "_walk1", "_walk2", "_attack"]
saved = []
for (a, b), p in zip(cb, POSES):
    pad = 6
    cell = img.subsurface((max(0, a - pad), y0, min(W, b + pad) - max(0, a - pad), y1 - y0)).copy()
    s = trim_center(keep_largest(remove_bg(cell)))
    key = f"{NAME}_{DIR}{p}"
    if s is None:
        print("  !! empty", key); continue
    pygame.image.save(s, os.path.join(OUT_DIR, key + ".png"))
    saved.append(key)
if DIR == "down" and f"{NAME}_down" in saved:
    import shutil
    shutil.copy(os.path.join(OUT_DIR, f"{NAME}_down.png"), os.path.join(OUT_DIR, f"{NAME}.png"))
    saved.append(NAME)
print(f"sliced {len(saved)}: {saved}")

if os.environ.get("COPY") == "1":
    import shutil
    for k in saved:
        shutil.copy(os.path.join(OUT_DIR, k + ".png"), os.path.join(HERE, k + ".png"))
    print("copied into", HERE)
