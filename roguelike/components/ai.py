from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import numpy as np

from actions import MeleeAction, MovementAction
from pathfinding import find_path

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity


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
        target = engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y

        # 上下左右に隣接していれば攻撃
        if abs(dx) + abs(dy) == 1:
            MeleeAction(dx, dy).perform(engine, self.entity)
            return

        # 経路を計算して1歩だけ進む
        self.path = self.get_path_to(engine, target.x, target.y)
        if self.path:
            next_x, next_y = self.path.pop(0)
            MovementAction(
                next_x - self.entity.x, next_y - self.entity.y
            ).perform(engine, self.entity)
