from __future__ import annotations

import tcod

import entity_factories
from actions import EscapeAction
from input_handlers import EventHandler
from procgen import generate_dungeon


class Engine:
    """ゲーム状態を保持し、入力→更新→描画の流れを束ねる。"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.game_over = False
        self.event_handler = EventHandler()
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

    def handle_events(self, events) -> None:
        for event in events:
            action = self.event_handler.dispatch(event)
            if action is None:
                continue
            # 死亡後は終了(ESC)以外の操作を受け付けない
            if self.game_over and not isinstance(action, EscapeAction):
                continue
            action.perform(self, self.player)  # プレイヤーの行動
            if not self.game_over:
                self.handle_enemy_turns()      # その後に敵全員が行動

    def handle_enemy_turns(self) -> None:
        # AI を持つエンティティ（＝敵）だけが行動する。プレイヤーは ai=None。
        for entity in list(self.game_map.entities):
            if self.game_over:
                break  # プレイヤーが倒れたら残りの敵は動かさない
            if entity.ai is not None:
                entity.ai.perform(self)

    def render(self, console: tcod.Console, context) -> None:
        console.clear()
        self.game_map.render(console)  # タイルとエンティティをまとめて描画
        # プレイヤーのHPを左下に表示
        fighter = self.player.fighter
        console.print(
            1, self.height - 1, f"HP: {fighter.hp}/{fighter.max_hp}", fg=(255, 255, 255)
        )
        context.present(console)
