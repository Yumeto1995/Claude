from __future__ import annotations

import tcod.event

from actions import Action, BumpAction, EscapeAction


class EventHandler(tcod.event.EventDispatch[Action]):
    """tcod のイベントを Action に変換する。描画と入力をここに集約する。"""

    def ev_quit(self, event: tcod.event.Quit) -> Action | None:
        raise SystemExit()

    def ev_keydown(self, event: tcod.event.KeyDown) -> Action | None:
        action: Action | None = None
        key = event.sym

        if key == tcod.event.KeySym.UP:
            action = BumpAction(dx=0, dy=-1)
        elif key == tcod.event.KeySym.DOWN:
            action = BumpAction(dx=0, dy=1)
        elif key == tcod.event.KeySym.LEFT:
            action = BumpAction(dx=-1, dy=0)
        elif key == tcod.event.KeySym.RIGHT:
            action = BumpAction(dx=1, dy=0)
        elif key == tcod.event.KeySym.ESCAPE:
            action = EscapeAction()

        # 該当キーがなければ None（何もしない）
        return action
