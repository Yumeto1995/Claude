from __future__ import annotations

from typing import Optional

import pygame

from actions import Action, BumpAction, EscapeAction


def dispatch_event(event: pygame.event.Event) -> Optional[Action]:
    """pygame のイベントを Action に変換する。該当しなければ None。"""
    if event.type == pygame.QUIT:
        raise SystemExit()

    if event.type == pygame.KEYDOWN:
        key = event.key
        if key in (pygame.K_UP, pygame.K_w, pygame.K_k):
            return BumpAction(dx=0, dy=-1)
        elif key in (pygame.K_DOWN, pygame.K_s, pygame.K_j):
            return BumpAction(dx=0, dy=1)
        elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_h):
            return BumpAction(dx=-1, dy=0)
        elif key in (pygame.K_RIGHT, pygame.K_d, pygame.K_l):
            return BumpAction(dx=1, dy=0)
        elif key == pygame.K_ESCAPE:
            return EscapeAction()

    return None
