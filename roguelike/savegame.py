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
        "camp_objects": {}, "camp_active_pos": None, "camp_build_kind": None,
        "unlocked_zones": set(), "storage": [],
        "camp_menu": None, "cook_pot": [], "pending_moves": [],
        "inventory_cursor": 0, "pending_fx": [],
        "building_key": None, "building_exit": None, "building_return": (0, 0),
        "shop_kind": None, "shop_cursor": 0, "village_outdoor_map": None,
        "skill_open": False, "skill_branch": 0, "skill_tier": 0,
        "floors": {},
    }
    # 旧セーブのプレイヤーにスキルツリーが無ければ付与
    pl = getattr(engine, "player", None)
    if pl is not None and getattr(pl, "skills", None) is None:
        from skills import Skills
        sk = Skills()
        pl.skills = sk
        sk.entity = pl
        if pl.level is not None:
            sk.snapshots = {1: (frozenset(), 0)}
            pl.level.skills = sk
    for attr, default in defaults.items():
        if not hasattr(engine, attr):
            setattr(engine, attr, default)
    return engine
