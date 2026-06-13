"""セーブ/ロード。Engine オブジェクトをまるごと pickle で保存・復元する。

Engine は pygame 由来のオブジェクトを持たない（描画は Renderer 側）ので、
そのまま pickle 可能。マップ(numpy)・エンティティ・持ち物・畑・倉庫なども含めて保存される。
"""
from __future__ import annotations

import os
import pickle

SAVE_PATH = os.path.join(os.path.dirname(__file__), "savegame.dat")


def has_save(path: str = SAVE_PATH) -> bool:
    return os.path.exists(path)


def save_game(engine, path: str = SAVE_PATH) -> None:
    with open(path, "wb") as f:
        pickle.dump(engine, f)


def load_game(path: str = SAVE_PATH):
    with open(path, "rb") as f:
        engine = pickle.load(f)
    # 後方互換：新しい属性が無い古いセーブを補完する
    defaults = {
        "in_village": False, "dialogue": None,
        "ranch_pens": [None] * 3, "fishery_tanks": [None] * 3,
        "unlocked_zones": set(), "storage": [],
        "camp_menu": None, "cook_pot": [], "pending_moves": [],
        "inventory_cursor": 0, "pending_fx": [],
    }
    for attr, default in defaults.items():
        if not hasattr(engine, attr):
            setattr(engine, attr, default)
    return engine
