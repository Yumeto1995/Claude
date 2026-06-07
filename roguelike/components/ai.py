from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

import colors
from actions import BumpAction, MeleeAction, MovementAction
from pathfinding import find_path

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

INFIGHT_CHANCE = 0.25  # 隣接する別の敵を攻撃してしまう確率（同士討ち）


class BaseAI:
    """敵AIの基底クラス。

    perform() が「このエンティティの1ターン分の行動」を決めて実行する。
    ★将来の最終目標：この perform() の中身を強化学習エージェントの
      出力（方策ネットワークが選んだ行動）に差し替える。
    """

    def __init__(self, entity: "Entity"):
        self.entity = entity  # このAIが操作する対象エンティティ

    def perform(self, engine: "Engine") -> None:
        raise NotImplementedError()

    def get_path_to(
        self, engine: "Engine", dest_x: int, dest_y: int
    ) -> List[Tuple[int, int]]:
        """自分から (dest_x, dest_y) までの、壁を避ける経路を返す。"""
        # 歩けるマス=1, 壁=0 のコスト配列を作る
        cost = np.array(engine.game_map.tiles["walkable"], dtype=np.int8)

        # 他の敵が立っているマスは通行コストを上げて回り込ませる
        for entity in engine.game_map.entities:
            if entity.blocks_movement and cost[entity.x, entity.y]:
                cost[entity.x, entity.y] += 10

        # A* で経路（始点を除く）を [(x, y), ...] で求める
        return find_path(cost, (self.entity.x, self.entity.y), (dest_x, dest_y))


class HostileEnemy(BaseAI):
    """プレイヤーに近づき、隣接したら攻撃するルールベースAI。"""

    def __init__(self, entity: "Entity"):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []

    def perform(self, engine: "Engine") -> None:
        # プレイヤーから見えていない敵は動かない（暗闇では眠っている）
        if not engine.game_map.visible[self.entity.x, self.entity.y]:
            return

        target = engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y

        # プレイヤーが上下左右に隣接していれば攻撃（最優先）
        if abs(dx) + abs(dy) == 1:
            MeleeAction(dx, dy).perform(engine, self.entity)
            return

        # 隣接する別の敵に一定確率で同士討ち
        foe = self._adjacent_enemy(engine)
        if foe is not None and random.random() < INFIGHT_CHANCE:
            MeleeAction(
                foe.x - self.entity.x, foe.y - self.entity.y
            ).perform(engine, self.entity)
            return

        # 経路を計算して1歩だけ進む
        self.path = self.get_path_to(engine, target.x, target.y)
        if self.path:
            next_x, next_y = self.path.pop(0)
            MovementAction(
                next_x - self.entity.x, next_y - self.entity.y
            ).perform(engine, self.entity)

    def _adjacent_enemy(self, engine: "Engine") -> Optional["Entity"]:
        """上下左右に隣接する『別の生きた敵』を返す。なければ None。"""
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            other = engine.game_map.get_blocking_entity_at(
                self.entity.x + dx, self.entity.y + dy
            )
            if other is not None and other is not engine.player and other.ai is not None:
                return other
        return None


class ConfusedEnemy(BaseAI):
    """混乱状態。一定ターン、ランダムな方向へよろめく（誰かにぶつかれば攻撃）。

    混乱が解けると元の AI に戻る。混乱の巻物で付与される。
    """

    def __init__(self, entity: "Entity", previous_ai: Optional[BaseAI], turns: int):
        super().__init__(entity)
        self.previous_ai = previous_ai
        self.turns_remaining = turns

    def perform(self, engine: "Engine") -> None:
        if self.turns_remaining <= 0:
            engine.message_log.add_message(
                f"{self.entity.name} の混乱が解けた。", colors.NO_EFFECT
            )
            self.entity.ai = self.previous_ai  # 元の行動に戻す
            return

        self.turns_remaining -= 1
        dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        # ランダム方向へ。誰か（プレイヤーや他の敵）にぶつかれば攻撃になる。
        BumpAction(dx, dy).perform(engine, self.entity)
