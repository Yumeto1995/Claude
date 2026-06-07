from __future__ import annotations

from typing import Iterable

import colors
import entity_factories
from actions import EscapeAction
from input_handlers import dispatch_event
from message_log import MessageLog
from procgen import generate_dungeon


class Engine:
    """ゲーム状態を保持し、入力→更新の流れを束ねる。描画は graphics.Renderer。"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.game_over = False
        self.attack_mode = False  # True なら方向キーで攻撃、False なら移動
        self.message_log = MessageLog()
        self.message_log.add_message("ダンジョンへようこそ。", colors.WELCOME)
        # プレイヤーはテンプレートから複製して用意（位置は生成時に決まる）
        self.player = entity_factories.player.spawn(0, 0)
        # ランダムダンジョンを生成（プレイヤー位置・敵配置もこの中で行う）
        self.game_map = generate_dungeon(
            max_rooms=30,
            room_min_size=6,
            room_max_size=10,
            map_width=width,
            map_height=height,
            max_monsters_per_room=2,
            player=self.player,
        )

    def handle_events(self, events: Iterable) -> None:
        for event in events:
            action = dispatch_event(event, self)
            if action is None:
                continue
            # 死亡後は終了(ESC)以外の操作を受け付けない
            if self.game_over and not isinstance(action, EscapeAction):
                continue
            action.perform(self, self.player)  # プレイヤーの行動
            # ターンを消費する行動の後だけ敵が動く（モード切替などは消費しない）
            if action.consumes_turn and not self.game_over:
                if not action.is_attack:
                    self.player.fighter.regenerate_stamina()  # 攻撃以外で回復
                self.handle_enemy_turns()

    def handle_enemy_turns(self) -> None:
        # AI を持つエンティティ（＝敵）だけが行動する。プレイヤーは ai=None。
        for entity in list(self.game_map.entities):
            if self.game_over:
                break  # プレイヤーが倒れたら残りの敵は動かさない
            if entity.ai is not None:
                entity.ai.perform(self)
