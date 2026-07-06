"""BGM（背景音楽）の管理。ゲームの状態に応じて musics/ の MIDI を切り替えて流す。

play(name) は「今と同じ曲なら何もしない」ので毎フレーム呼んでよい（切替時だけ再生し直す）。
音声デバイスが無い等で mixer が使えない環境でも、静かに無効化してゲーム自体は動く。
"""
from __future__ import annotations

import os

import pygame

_DIR = os.path.join(os.path.dirname(__file__), "musics")

# BGM名 → ファイル。menu=タイトル/メニュー、dungeon=ダンジョン探索、village=村・拠点。
TRACKS = {
    "menu": "title_menu.mid",
    "dungeon": "exploration_dungeon.mid",
    "village": "village_ruined.mid",
}
VOLUME = 0.5

_ok = False          # mixer が使えるか
_current = None       # 今流している BGM名


def init() -> None:
    """mixer を初期化（pygame.init() の後に呼ぶ）。失敗しても例外は投げない。"""
    global _ok
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
        pygame.mixer.music.set_volume(VOLUME)
        _ok = True
    except Exception:
        _ok = False


def play(name: str) -> None:
    """name の BGM をループ再生する。既に同じ曲なら何もしない。"""
    global _current
    if not _ok or name == _current:
        return
    fname = TRACKS.get(name)
    if not fname:
        return
    path = os.path.join(_DIR, fname)
    if not os.path.exists(path):
        return
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(VOLUME)
        pygame.mixer.music.play(loops=-1)   # -1 で無限ループ
        _current = name
    except Exception:
        _current = None


def stop() -> None:
    global _current
    if _ok:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
    _current = None


def state_for(engine) -> str:
    """Engine の状態から BGM名を決める。村・拠点は村曲、その他（ダンジョン）は探索曲。"""
    if getattr(engine, "in_camp", False) or getattr(engine, "in_village", False):
        return "village"
    return "dungeon"
