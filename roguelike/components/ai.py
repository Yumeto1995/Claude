from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

import colors
from actions import BumpAction, MeleeAction, MovementAction
from pathfinding import find_path
from rl import obs as rl_obs

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

        # プレイヤーが隣接（斜め含む8方向）していれば攻撃（最優先）
        if max(abs(dx), abs(dy)) == 1:
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
        """隣接（斜め含む8方向）する『別の生きた敵』を返す。なければ None。"""
        for dx, dy in (
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        ):
            other = engine.game_map.get_blocking_entity_at(
                self.entity.x + dx, self.entity.y + dy
            )
            if other is not None and other is not engine.player and other.ai is not None:
                return other
        return None


class RLEnemy(HostileEnemy):
    """学習済みの方策（Qテーブル）で動く敵。★強化学習の本番側。

    rl/policy.npz（`python3 -m rl.train` で生成）をクラスで1回だけ読み込み、
    全個体で共有する。クラス属性なのでセーブデータ（pickle）には含まれない。

    フォールバック（HostileEnemy と同じ動き）になる場合：
    - 方策ファイルが無い・壊れている・観測設計が古い
    - プレイヤーが観測の丸め幅（±4マス）より遠い → A* で追跡
    """

    _qtable = None       # 全個体で共有するQテーブル（numpy配列）
    _load_tried = False  # 起動後1回だけ読み込みを試す

    @classmethod
    def _policy(cls):
        if not cls._load_tried:
            cls._load_tried = True
            try:
                from rl.qlearning import load_qtable  # 遅延import（起動を軽く）
                cls._qtable = load_qtable()
            except Exception:
                cls._qtable = None
        return cls._qtable

    def perform(self, engine: "Engine") -> None:
        # プレイヤーから見えていない敵は動かない（暗闇では眠っている）
        if not engine.game_map.visible[self.entity.x, self.entity.y]:
            return

        target = engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y

        q = self._policy()
        if q is None or max(abs(dx), abs(dy)) > rl_obs.CLAMP:
            # 方策なし／遠距離は従来のルールベース（A*追跡）
            return super().perform(engine)

        # 同士討ちの気まぐれは従来通り残す（プレイヤー非隣接時のみ）
        if max(abs(dx), abs(dy)) > 1:
            foe = self._adjacent_enemy(engine)
            if foe is not None and random.random() < INFIGHT_CHANCE:
                MeleeAction(
                    foe.x - self.entity.x, foe.y - self.entity.y
                ).perform(engine, self.entity)
                return

        # Q値の高い行動から順に、実行できるものを選ぶ
        # （壁・他の敵・セーフルームで動けない行動はスキップ）
        state = rl_obs.encode(self.entity, target)
        for action in np.argsort(q[state])[::-1]:
            adx, ady = rl_obs.ACTIONS[action]
            if (adx, ady) == (0, 0):
                return  # 待機が最善 → 何もしない
            blocking = engine.game_map.get_blocking_entity_at(
                self.entity.x + adx, self.entity.y + ady
            )
            if blocking is target:
                MeleeAction(adx, ady).perform(engine, self.entity)
                return
            if blocking is not None:
                continue  # 他の敵がいるマス
            move = MovementAction(adx, ady)
            move.perform(engine, self.entity)
            if move.consumes_turn:
                return  # 実際に動けたら終わり
        # どの行動もできなければ待機


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
        dx, dy = random.choice([
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        ])
        # ランダム方向（斜め含む）へ。誰かにぶつかれば攻撃になる。
        BumpAction(dx, dy).perform(engine, self.entity)
