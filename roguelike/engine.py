from __future__ import annotations

from typing import Iterable

import colors
import entity_factories
from actions import EscapeAction
from fov import compute_fov
from input_handlers import dispatch_event
from message_log import MessageLog
from procgen import generate_dungeon


class Engine:
    """ゲーム状態を保持し、入力→更新の流れを束ねる。描画は graphics.Renderer。"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.game_over = False
        self.attack_mode = False     # True なら方向キーで攻撃、False なら移動
        self.inventory_open = False  # 持ち物メニューを開いているか
        # 攻撃モーションの予約 [(entity, dx, dy), ...]。Renderer が取り出して再生する。
        self.pending_animations = []
        self.message_log = MessageLog()
        self.message_log.add_message("ダンジョンへようこそ。", colors.WELCOME)
        # プレイヤーはテンプレートから複製して用意（位置は生成時に決まる）
        self.player = entity_factories.player.spawn(0, 0)
        self._give_starting_equipment()
        # ランダムダンジョンを生成（プレイヤー位置・敵配置もこの中で行う）
        self.game_map = generate_dungeon(
            max_rooms=30,
            room_min_size=6,
            room_max_size=10,
            map_width=width,
            map_height=height,
            max_monsters_per_room=2,
            max_items_per_room=1,
            player=self.player,
        )
        self.update_fov()  # 初期視界を計算

    def handle_events(self, events: Iterable) -> None:
        for event in events:
            action = dispatch_event(event, self)
            if action is not None:
                self.perform_player_action(action)

    def perform_player_action(self, action) -> None:
        """プレイヤーの1アクションを実行し、ターン経過処理を行う。

        単発キー（handle_events）と長押し移動（メインループ）の両方から呼ばれる。
        """
        # 死亡後は終了(ESC)以外の操作を受け付けない
        if self.game_over and not isinstance(action, EscapeAction):
            return
        action.perform(self, self.player)
        # ターンを消費する行動の後だけ敵が動く（モード切替・壁ぶつかりは消費しない）
        if action.consumes_turn and not self.game_over:
            if not action.is_attack:
                self.player.fighter.regenerate_stamina()  # 攻撃以外で回復
            self.update_fov()          # プレイヤーが動いたので視界更新
            self.handle_enemy_turns()  # 敵は視界内のものだけ動く

    def _give_starting_equipment(self) -> None:
        """短剣と革の鎧を持たせて装備させる（開始時）。"""
        dagger = entity_factories.dagger.spawn(0, 0)
        armor = entity_factories.leather_armor.spawn(0, 0)
        self.player.inventory.items.extend([dagger, armor])
        self.player.equipment.weapon = dagger
        self.player.equipment.armor = armor

    def update_fov(self) -> None:
        """プレイヤー位置から視界を再計算し、探索済みに反映する。"""
        gm = self.game_map
        gm.visible = compute_fov(
            gm.tiles["transparent"], gm.rooms, self.player.x, self.player.y
        )
        gm.explored |= gm.visible

    def drain_animations(self):
        """予約された攻撃モーションを取り出して空にする（Renderer が呼ぶ）。"""
        anims = self.pending_animations
        self.pending_animations = []
        return anims

    def handle_enemy_turns(self) -> None:
        # AI を持つエンティティ（＝敵）だけが行動する。プレイヤーは ai=None。
        for entity in list(self.game_map.entities):
            if self.game_over:
                break  # プレイヤーが倒れたら残りの敵は動かさない
            if entity.ai is not None:
                entity.ai.perform(self)
