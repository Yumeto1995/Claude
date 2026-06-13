"""画面解像度の設定。標準的な 16:9 解像度から選び、JSON に保存する。

タイルは常に 64px。論理解像度 = 横タイル数×64 ×（縦タイル数×64 ＋ 下部パネル高）。
横は 64 の倍数なのでタイルがぴったり並ぶ。縦は「(高さ−最低パネル高) を 64 で割った
タイル数」を取り、余りをパネル高に回すので、合計はちょうど選んだ w×h になる
（= どの解像度でもドット等倍で隙間なく埋まる）。選んだ番号は settings.json に保存する。
"""
from __future__ import annotations

import json
import os

TILE_SIZE = 64
PANEL_MIN = 184  # 下部パネルの最低高さ（HP/ST/満腹ゲージ＋ログ4行が収まる）

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

# 選べる解像度（すべて 16:9・横は 64 の倍数）。先頭から順にメニューへ並ぶ。
RESOLUTIONS = [
    (1280, 720),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
]
DEFAULT_INDEX = 2  # 既定は 1920×1080


def layout_for(w: int, h: int):
    """解像度 (w, h) を埋めるタイル数とパネル高 (view_w, view_h, panel) を返す。

    横 = w//64 タイル。縦は (h − 最低パネル高) を 64 で割ったタイル数を取り、
    余りをパネル高に充てるので view_w*64 ×（view_h*64 + panel）はちょうど w×h。
    """
    view_w = w // TILE_SIZE
    view_h = (h - PANEL_MIN) // TILE_SIZE
    panel = h - view_h * TILE_SIZE
    return view_w, view_h, panel


def label(w: int, h: int) -> str:
    return f"{w}×{h}"


def load_index() -> int:
    """保存された解像度番号を読む。無効/未保存なら既定値。"""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            i = int(json.load(f).get("resolution", DEFAULT_INDEX))
        if 0 <= i < len(RESOLUTIONS):
            return i
    except Exception:
        pass
    return DEFAULT_INDEX


def save_index(i: int) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump({"resolution": i}, f)
    except Exception:
        pass
