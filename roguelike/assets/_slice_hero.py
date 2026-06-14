"""主人公シート(ud6ip1, 4x4・白系市松背景)から player_* を切り出す。

白背景は縁からの塗りつぶしで透過（盾の白十字・白ズボンは内部なので残る）→最大連結成分
→トリム→64×64。OUT_DIR（既定 /tmp/hero）に出力、COPY=1 で assets/ へ反映。
"""
import os
from collections import deque

os.environ["SDL_VIDEODRIVER"] = "dummy"
import numpy as np
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "Gemini_Generated_Image_ud6ip1ud6ip1ud6i.png")
OUT_DIR = os.environ.get("OUT_DIR", "/tmp/hero")
os.makedirs(OUT_DIR, exist_ok=True)
TILE = 64
img = pygame.image.load(SHEET).convert_alpha()
W, H = img.get_size()


def remove_bg(cell):
    """明るい無彩色の背景を四辺からBFSで透過（内部の白＝盾の十字/白ズボンは残す）。"""
    rgb = pygame.surfarray.array3d(cell).astype(int)
    mx, mn, val = rgb.max(2), rgb.min(2), rgb.mean(2)
    w, h = cell.get_size()
    bgm = ((mx - mn) < 30) & (val >= 196)
    vis = np.zeros((w, h), bool)
    dq = deque()
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
    out = cell.copy()
    a = pygame.surfarray.pixels_alpha(out)
    a[vis] = 0
    del a
    return out


def keep_largest(cell):
    op = pygame.surfarray.array_alpha(cell) > 60
    w, h = cell.get_size()
    lab = np.zeros((w, h), np.int32)
    best, bid, cur = 0, 0, 0
    for sx in range(w):
        for sy in range(h):
            if op[sx, sy] and lab[sx, sy] == 0:
                cur += 1; sz = 0; dq = deque([(sx, sy)]); lab[sx, sy] = cur
                while dq:
                    x, y = dq.popleft(); sz += 1
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and op[nx, ny] and lab[nx, ny] == 0:
                            lab[nx, ny] = cur; dq.append((nx, ny))
                if sz > best:
                    best, bid = sz, cur
    if bid:
        a = pygame.surfarray.pixels_alpha(cell)
        a[lab != bid] = 0
        del a
    return cell


def trim_center(cell, target=60):
    al = pygame.surfarray.array_alpha(cell)
    xs, ys = np.where(al > 80)
    if len(xs) == 0:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    sub = cell.subsurface((int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1))).copy()
    w, h = sub.get_size()
    sc = min(target / w, target / h)
    nw, nh = max(1, round(w * sc)), max(1, round(h * sc))
    sub = pygame.transform.smoothscale(sub, (nw, nh))
    o = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    o.blit(sub, ((TILE - nw) // 2, (TILE - nh) // 2))
    return o


# 4x4 グリッド。列中心(352幅) / 行はスプライト上部(ラベルを除外)
COL_CX = [176, 528, 880, 1232]
ROW_Y = {"down": (6, 162), "up": (198, 354), "left": (390, 546), "right": (582, 738)}
POSES = ["", "_walk1", "_walk2", "_attack"]

saved = []
for d, (y0, y1) in ROW_Y.items():
    for cx, p in zip(COL_CX, POSES):
        cell = img.subsurface((cx - 172, y0, 344, y1 - y0)).copy()
        s = trim_center(keep_largest(remove_bg(cell)))
        key = f"player_{d}{p}"
        if s is None:
            print("  !! empty", key); continue
        pygame.image.save(s, os.path.join(OUT_DIR, key + ".png"))
        saved.append(key)
# base = down idle
import shutil
if "player_down" in saved:
    shutil.copy(os.path.join(OUT_DIR, "player_down.png"), os.path.join(OUT_DIR, "player.png"))
    saved.append("player")

print(f"sliced {len(saved)} hero frames into {OUT_DIR}")

if os.environ.get("COPY") == "1":
    for k in saved:
        shutil.copy(os.path.join(OUT_DIR, k + ".png"), os.path.join(HERE, k + ".png"))
    print("copied", len(saved), "into", HERE)
