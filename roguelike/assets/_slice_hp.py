"""hp02qo シートから全アセットを切り出す（暗い無彩色背景）。

背景は暗い灰(val~95・無彩色)。色ベースで背景を消し、最大連結成分→トリム。
キャラ/アイテム/設備/オブジェクト＝透過トリム、地形タイル＝不透過充填。
このシートに無いタイル（cave_*/wood_*/log_floor/log_wall/meadow_wall/food）は出力しない
（既存を残す）。OUT_DIR（既定 /tmp/hp）に出力、COPY=1 で assets/ へ反映。
"""
import os
from collections import deque

os.environ["SDL_VIDEODRIVER"] = "dummy"
import numpy as np
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "Gemini_Generated_Image_hp02qohp02qohp02.png")
OUT_DIR = os.environ.get("OUT_DIR", "/tmp/hp")
os.makedirs(OUT_DIR, exist_ok=True)
TILE = 64
img = pygame.image.load(SHEET).convert_alpha()
W, H = img.get_size()


def remove_bg(cell):
    rgb = pygame.surfarray.array3d(cell).astype(int)
    mx, mn, val = rgb.max(2), rgb.min(2), rgb.mean(2)
    bg = ((mx - mn) < 24) & (val >= 48) & (val <= 122)   # 暗い無彩色背景
    out = cell.copy()
    a = pygame.surfarray.pixels_alpha(out)
    a[bg] = 0
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


def trim_center(cell, target=58):
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


saved = []


def emit(name, surf):
    if surf is None:
        print("  !! empty", name); return
    pygame.image.save(surf, os.path.join(OUT_DIR, name + ".png"))
    saved.append(name)


def obj_at(cx, cy, hw, hh, target=58):
    x0 = max(0, cx - hw); y0 = max(0, cy - hh)
    x1 = min(W, cx + hw); y1 = min(H, cy + hh)
    return trim_center(keep_largest(remove_bg(img.subsurface((x0, y0, x1 - x0, y1 - y0)).copy())), target)


def tile_at(cx, cy, half=29):
    sub = pygame.transform.smoothscale(img.subsurface((cx - half, cy - half, 2 * half, 2 * half)).copy(), (TILE, TILE))
    sub.set_alpha(None)
    o = pygame.Surface((TILE, TILE)); o.blit(sub, (0, 0))
    return o.convert_alpha()


# ===== キャラ =====
ROW_Y = {"down": 81, "up": 204, "left": 332, "right": 457}
HH = 48
def block(name, cxs, poses):
    for d, cy in ROW_Y.items():
        for cx, p in zip(cxs, poses):
            emit(f"{name}_{d}{p}", obj_at(cx, cy, 44, HH, 58))
    emit(name, obj_at(cxs[0], ROW_Y["down"], 44, HH, 58))
block("player", [64, 182, 295, 413], ["", "_walk1", "_walk2", "_attack"])
block("goblin", [541, 647, 764, 895], ["", "_walk1", "_walk2", "_attack"])
block("npc", [1114, 1230, 1347], ["", "_walk1", "_walk2"])

# ===== スライム・死体 =====
emit("slime", obj_at(520, 505, 36, 40, 56))
emit("slime_walk1", obj_at(590, 505, 36, 40, 56))
emit("slime_walk2", obj_at(655, 505, 36, 40, 56))
emit("corpse", obj_at(720, 505, 38, 40, 56))

# ===== オブジェクト =====
emit("tree", obj_at(838, 600, 40, 48, 62))
emit("door", obj_at(908, 605, 38, 44, 60))
emit("stairs_down", obj_at(997, 607, 42, 46, 60))
emit("stairs_up", obj_at(1078, 607, 40, 46, 60))
emit("material", obj_at(845, 704, 36, 36, 54))
emit("seed", obj_at(920, 704, 34, 36, 54))
emit("key_item", obj_at(996, 704, 38, 36, 54))
emit("tent", obj_at(1078, 704, 38, 36, 54))

# ===== アイテム =====
emit("dagger", obj_at(1111, 425, 34, 38, 54))
emit("sword", obj_at(1210, 425, 38, 38, 54))
emit("leather_armor", obj_at(1283, 425, 36, 38, 54))
emit("chain_mail", obj_at(1356, 425, 36, 38, 54))
emit("potion", obj_at(1113, 505, 32, 36, 54))
emit("scroll", obj_at(1196, 505, 34, 36, 54))
emit("scroll_confuse", obj_at(1273, 505, 34, 36, 54))
emit("dish", obj_at(1356, 505, 36, 36, 54))

# ===== 設備 =====
emit("st_cooking", obj_at(1133, 605, 38, 36, 54))
emit("st_storage", obj_at(1218, 605, 38, 36, 54))
emit("st_alchemy", obj_at(1303, 605, 36, 36, 54))
emit("st_ranch", obj_at(1385, 605, 36, 36, 54))
emit("st_fishery", obj_at(1133, 704, 38, 36, 54))
emit("st_exit", obj_at(1218, 704, 38, 36, 54))

# ===== タイル（不透過）。このシートに在るものだけ =====
TILE_R1 = [("grass", 50), ("grass_flower", 134), ("grass_clover", 219), ("grass_stone", 304),
           ("grass_dirt", 387), ("meadow_floor", 472), ("stone_floor", 558),
           ("stone_wall", 652), ("meadow_safe_floor", 757)]
TILE_R2 = [("farm_empty", 51), ("farm_grow", 134), ("farm_ready", 219), ("log_window", 304),
           ("log_rug", 387), ("floor", 473), ("wall", 562), ("safe_floor", 652)]
for nm, cx in TILE_R1:
    emit(nm, tile_at(cx, 605))
for nm, cx in TILE_R2:
    emit(nm, tile_at(cx, 704))

print(f"sliced {len(saved)} assets into {OUT_DIR}")

if os.environ.get("COPY") == "1":
    import shutil
    for k in saved:
        shutil.copy(os.path.join(OUT_DIR, k + ".png"), os.path.join(HERE, k + ".png"))
    print("copied", len(saved), "into", HERE)
