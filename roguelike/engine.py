from __future__ import annotations

from typing import Iterable

import colors
import entity_factories
import farming
import item_category
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
        self.inventory_category = 0  # 持ち物メニューで選択中の分類タブ
        # 拠点（魔法のテント）の状態
        self.in_camp = False
        self.camp_screen = "main"    # main/cooking/cook/alchemy/farm/farm_plant
        self.camp_cursor = 0
        self.cook_first = None       # 料理で1つ目に選んだ食材名
        self.farm_plots = [None] * 4  # 畑（None=空き / dict=栽培中）
        self.discovered_dishes = set()  # 発見済みの料理名
        # 攻撃モーションの予約 [(entity, dx, dy), ...]。Renderer が取り出して再生する。
        self.pending_animations = []
        self.message_log = MessageLog()
        self.message_log.add_message("ダンジョンへようこそ。", colors.WELCOME)
        # プレイヤーはテンプレートから複製して用意（位置は生成時に決まる）
        self.player = entity_factories.player.spawn(0, 0)
        self._give_starting_equipment()
        self.current_floor = 0
        self.generate_floor()  # 1階を生成

    def generate_floor(self) -> None:
        """次のフロアを生成する（プレイヤーのステータス・持ち物は引き継ぐ）。"""
        self.current_floor += 1
        # 深いほど敵が増える（上限あり）
        max_monsters = min(2 + (self.current_floor - 1) // 2, 6)
        self.game_map = generate_dungeon(
            max_rooms=30,
            room_min_size=6,
            room_max_size=10,
            map_width=self.width,
            map_height=self.height,
            max_monsters_per_room=max_monsters,
            max_items_per_room=1,
            player=self.player,
        )
        farming.grow(self)  # 1階潜るごとに畑の作物が育つ
        self.update_fov()   # 視界を計算

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
            # 満腹度を消費。空腹になった瞬間は警告を出す。
            was_hungry = self.player.fighter.is_hungry
            self.player.fighter.drain_satiety()
            if not was_hungry and self.player.fighter.is_hungry:
                self.message_log.add_message(
                    "おなかが空いた！ 攻撃が重くなり、被ダメージも増える…", colors.PLAYER_DIE
                )
            self._tick_status_effects()
            self.update_fov()          # プレイヤーが動いたので視界更新
            self.handle_enemy_turns()  # 敵は視界内のものだけ動く

    def _give_starting_equipment(self) -> None:
        """短剣と革の鎧を持たせて装備させる（開始時）。"""
        dagger = entity_factories.dagger.spawn(0, 0)
        armor = entity_factories.leather_armor.spawn(0, 0)
        proof = entity_factories.adventurers_proof.spawn(0, 0)  # 大切なもの
        tent = entity_factories.magic_tent.spawn(0, 0)          # 大切なもの（拠点へ）
        self.player.inventory.items.extend([dagger, armor, proof, tent])
        self.player.equipment.weapon = dagger
        self.player.equipment.armor = armor
        # 合成・栽培を試せるよう、素材と種を少し持たせておく
        for _ in range(3):
            self.player.inventory.items.append(
                entity_factories.slime_shard.spawn(0, 0)
            )
        self.player.inventory.items.append(entity_factories.nut_seed.spawn(0, 0))
        self.player.inventory.items.append(entity_factories.herb_seed.spawn(0, 0))

    def _tick_status_effects(self) -> None:
        """料理バフなどの一時効果を1ターン分減らし、切れたら外す。"""
        for eff in list(self.player.status_effects):
            eff.turns -= 1
            if eff.turns <= 0:
                self.player.status_effects.remove(eff)
                self.message_log.add_message(
                    f"{eff.name} の効果が切れた。", colors.NO_EFFECT
                )

    def item_under_player(self):
        """プレイヤーが乗っている床のアイテムを返す。なければ None。"""
        for ent in self.game_map.entities:
            if (
                item_category.is_item(ent)
                and ent.x == self.player.x
                and ent.y == self.player.y
            ):
                return ent
        return None

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
