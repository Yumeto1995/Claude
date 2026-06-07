from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

from actions import (
    Action,
    BumpAction,
    EscapeAction,
    MeleeAction,
    ToggleAttackModeAction,
    WaitAction,
)

if TYPE_CHECKING:
    from engine import Engine

# キー → 方向 (dx, dy)。矢印・WASD・vi(hjkl) に対応。
_DIRECTIONS = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_k: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_j: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_h: (-1, 0),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0), pygame.K_l: (1, 0),
}


def dispatch_event(event: pygame.event.Event, engine: "Engine") -> Optional[Action]:
    """pygame のイベントを Action に変換する。該当しなければ None。"""
    if event.type == pygame.QUIT:
        raise SystemExit()

    if event.type == pygame.KEYDOWN:
        key = event.key

        if key in _DIRECTIONS:
            dx, dy = _DIRECTIONS[key]
            # 攻撃モードなら踏み込まずに攻撃、通常は移動（敵がいればぶつかって攻撃）
            if engine.attack_mode:
                return MeleeAction(dx, dy)
            return BumpAction(dx, dy)

        if key == pygame.K_z:
            return WaitAction()                 # 足踏み
        if key == pygame.K_SPACE:
            return ToggleAttackModeAction()      # 攻撃/移動モード切替
        if key == pygame.K_ESCAPE:
            return EscapeAction()

    return None
