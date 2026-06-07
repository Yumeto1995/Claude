from __future__ import annotations

from typing import List, Tuple

import colors


class Message:
    """1件のメッセージ。同じ文が連続したら count でまとめる。"""

    def __init__(self, text: str, fg: Tuple[int, int, int]):
        self.plain_text = text
        self.fg = fg
        self.count = 1

    @property
    def full_text(self) -> str:
        if self.count > 1:
            return f"{self.plain_text} (x{self.count})"
        return self.plain_text


class MessageLog:
    """戦闘などのメッセージを溜めて、画面下部に表示する。"""

    def __init__(self):
        self.messages: List[Message] = []

    def add_message(
        self, text: str, fg: Tuple[int, int, int] = colors.WHITE, *, stack: bool = True
    ) -> None:
        # 直前と同じ文ならまとめる
        if stack and self.messages and self.messages[-1].plain_text == text:
            self.messages[-1].count += 1
        else:
            self.messages.append(Message(text, fg))

    def render(self, surface, font, x: int, y: int, line_height: int, max_lines: int) -> None:
        """最新 max_lines 件を、古い→新しい順に上から描画する。"""
        recent = self.messages[-max_lines:]
        for i, message in enumerate(recent):
            text_surf = font.render(message.full_text, True, message.fg)
            surface.blit(text_surf, (x, y + i * line_height))
