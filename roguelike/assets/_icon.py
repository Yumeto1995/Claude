"""生成した単体アイコンPNGを 背景透過＋トリム＋64×64 に整える（バッチ処理）。

DALL-E/ChatGPT 等が出した「単色（白）背景の1アイコン画像」を、ゲームで使える
透明な 64×64 スプライトに変換する。フォルダ内をまとめて処理できる。依存は
pygame + numpy のみ（_slice_dir.py と同じ）。

使い方:
  IN=<入力フォルダ> OUT=<出力フォルダ> python3 _icon.py
  例) IN=/tmp/icons OUT=/tmp/icons_out python3 _icon.py

各PNGを処理し、同じファイル名で OUT に保存する。背景は四隅の色から自動判定し、
縁からつながる背景だけ透過する（内部の同色＝卵やミルクの白などは残る）。
目視確認後、assets/ の適切なサブフォルダ（items/ structures/ backgrounds/…）へコピーする。
"""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
from collections import deque

import numpy as np
import pygame

pygame.init()
pygame.display.set_mode((1, 1))

IN = os.environ.get("IN", "/tmp/icons")
OUT = os.environ.get("OUT", "/tmp/icons_out")
TILE = 64
MAXIN = 256   # 処理前にこのサイズへ縮小（高速化＋ノイズ低減）
BG_T = float(os.environ.get("BG_T", "38"))   # 背景とみなす色距離（白背景なら大きめでOK）
os.makedirs(OUT, exist_ok=True)


def process(path):
    img = pygame.image.load(path).convert_alpha()
    w0, h0 = img.get_size()
    if max(w0, h0) > MAXIN:                       # 先に縮小して高速化
        s = MAXIN / max(w0, h0)
        img = pygame.transform.smoothscale(img, (max(1, round(w0 * s)), max(1, round(h0 * s))))
    W, H = img.get_size()
    rgb = pygame.surfarray.array3d(img).astype(int)
    # 四隅の色を背景トーンとして採取し、近い色を背景候補に
    bg = np.zeros((W, H), bool)
    for c in (rgb[0, 0], rgb[W - 1, 0], rgb[0, H - 1], rgb[W - 1, H - 1]):
        bg |= np.sqrt(((rgb - np.array(c)) ** 2).sum(2)) < BG_T
    # 縁からの flood-fill：外側につながる背景だけ透過（内部の同色は残す）
    vis = np.zeros((W, H), bool)
    dq = deque()
    for x in range(W):
        for y in (0, H - 1):
            if bg[x, y] and not vis[x, y]:
                vis[x, y] = True; dq.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if bg[x, y] and not vis[x, y]:
                vis[x, y] = True; dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and bg[nx, ny] and not vis[nx, ny]:
                vis[nx, ny] = True; dq.append((nx, ny))
    out = img.copy()
    a = pygame.surfarray.pixels_alpha(out)
    a[vis] = 0
    del a
    # 不透明部分でトリム → 64×64 の中央に等比配置
    al = pygame.surfarray.array_alpha(out)
    xs, ys = np.where(al > 40)
    if len(xs) == 0:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    sub = out.subsurface((x0, y0, x1 - x0 + 1, y1 - y0 + 1)).copy()
    w, h = sub.get_size()
    sc = min((TILE - 4) / w, (TILE - 4) / h)
    nw, nh = max(1, round(w * sc)), max(1, round(h * sc))
    sub = pygame.transform.smoothscale(sub, (nw, nh))
    o = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    o.blit(sub, ((TILE - nw) // 2, (TILE - nh) // 2))
    return o


if not os.path.isdir(IN):
    raise SystemExit(f"入力フォルダが無い: {IN}（IN= で指定）")
n = 0
for f in sorted(os.listdir(IN)):
    if not f.lower().endswith(".png"):
        continue
    s = process(os.path.join(IN, f))
    if s is None:
        print("  空(中身なし):", f)
        continue
    pygame.image.save(s, os.path.join(OUT, f))
    n += 1
    print("  ok:", f)
print(f"{n} 枚を {OUT} に出力。目視後 assets/ の該当フォルダへコピー。")
