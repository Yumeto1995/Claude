from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

import colors
import combat
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
    """A*で接近し、隣接したら学習済み方策（Qテーブル）で駆け引きする敵。★強化学習の本番側。

    方策は Engine が持つ OnlineLearner（rl/online.py）＝基本方策 policy.npz の
    可変コピー。全ゴブリンで共有し、**プレイヤーの実戦から随時学習**して今の
    プレイヤーに適応する（ニューゲームで基本方策へリセット。詳細は rl/online.py）。

    設計（ハイブリッド）：
    - 観測は相対位置・HP等のみで『壁』を認識しないため、接近の経路探索は
      A*（HostileEnemy）に任せる＝ダンジョンの壁/通路でも確実に近づける。
    - 隣接した間合いでは方策で「攻撃／後退／待機」を決める＝HPやプレイヤーの
      スタミナを見て、削れるときに殴り不利なら引く、という駆け引きが出る。
    - 学習対象はこの隣接時の判断だけ（接近は方策外）。敵はグリーディに動くので
      挙動はブレず、実戦の遷移(s,a,r,s')でだけ Q をそっと更新する（off-policy）。
    - 学習器が無い／壊れている場合は純粋な A* 追跡（HostileEnemy）にフォールバック。
    """

    @staticmethod
    def _allies(engine: "Engine", target: "Entity") -> List["Entity"]:
        """観測に渡す『味方（他の生きた敵）』。encode 側で自分は除外される。"""
        return [
            e for e in engine.game_map.entities
            if e is not target and e.ai is not None
            and e.fighter is not None and e.fighter.hp > 0
        ]

    def _learn_prev(self, engine: "Engine", learner, target: "Entity",
                    extra: float = 0.0, done: bool = False) -> None:
        """前ターンに方策で下した判断 (_rl_prev) を、実戦の結果で1手遅れて学習する。

        与ダメは判断時に確定済み（_rl_prev に保持）。被ダメ・接近は前ターンからの
        HP/距離の変化で測る。extra は撃破(+R_KILL)や死亡(+R_DEATH)の終端報酬。"""
        from rl.online import R_APPROACH, R_DEALT, R_STEP, R_TAKEN
        prev = getattr(self, "_rl_prev", None)
        if prev is None or learner is None:
            return
        self._rl_prev = None
        taken = prev["hp"] - self.entity.fighter.hp
        dist_now = max(abs(target.x - self.entity.x), abs(target.y - self.entity.y))
        approach = (prev["dist"] - dist_now) * R_APPROACH
        r = prev["dealt"] * R_DEALT + taken * R_TAKEN + approach + R_STEP + extra
        s2 = prev["s"] if done else rl_obs.encode(
            self.entity, target, self._allies(engine, target))
        learner.learn(prev["s"], prev["a"], r, s2, done)

    def on_death(self, engine: "Engine") -> None:
        """自分が倒された時（combat._die から呼ぶ）。最後の判断を終端・死亡報酬で確定。"""
        from rl.online import R_DEATH
        learner = getattr(engine, "enemy_learner", None)
        self._learn_prev(engine, learner, engine.player, extra=R_DEATH, done=True)

    def perform(self, engine: "Engine") -> None:
        # プレイヤーから見えていない敵は動かない（暗闇では眠っている）
        if not engine.game_map.visible[self.entity.x, self.entity.y]:
            return

        learner = getattr(engine, "enemy_learner", None)
        if learner is None:
            return super().perform(engine)  # 学習器なし → A*追跡（学習もしない）

        target = engine.player
        # まず、前ターンの方策判断の結果を学習（1手遅れの報酬でQ更新）
        self._learn_prev(engine, learner, target)

        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        adjacent = max(abs(dx), abs(dy)) == 1

        # 隣接していない：A*で確実に接近（壁を回り込む）。同士討ちの気まぐれも従来通り。
        if not adjacent:
            return super().perform(engine)

        # 隣接：方策で「攻撃／後退／待機」を決める。味方位置も観測に渡す（群れ連携）。
        state = rl_obs.encode(self.entity, target, self._allies(engine, target))
        self_hp0 = self.entity.fighter.hp
        chosen_a = None
        dealt = 0.0
        for action in np.argsort(learner.q[state])[::-1]:
            adx, ady = rl_obs.ACTIONS[action]
            if (adx, ady) == (0, 0):
                chosen_a = action
                break  # 待機が最善（回復待ち等）
            # プレイヤー方向なら攻撃（与ダメを記録）
            if (adx, ady) == (self._sign(dx), self._sign(dy)):
                p_hp = target.fighter.hp
                MeleeAction(adx, ady).perform(engine, self.entity)
                dealt = p_hp - target.fighter.hp
                chosen_a = action
                break
            # それ以外は後退/回り込み。動ける方向なら移動
            blocking = engine.game_map.get_blocking_entity_at(
                self.entity.x + adx, self.entity.y + ady
            )
            if blocking is not None:
                continue
            move = MovementAction(adx, ady)
            move.perform(engine, self.entity)
            if move.consumes_turn:
                chosen_a = action
                break
        if chosen_a is None:
            # どれも不可なら攻撃にフォールバック（隣接しているので殴る）
            p_hp = target.fighter.hp
            MeleeAction(self._sign(dx), self._sign(dy)).perform(engine, self.entity)
            dealt = p_hp - target.fighter.hp
            chosen_a = int(np.argmax(learner.q[state]))

        # この判断を記録（次の perform か on_death で報酬付き学習）
        self._rl_prev = {"s": state, "a": chosen_a, "hp": self_hp0,
                         "dist": 1, "dealt": dealt}
        # プレイヤーを倒したら次ターンは来ないので、この一手を即・終端報酬で確定
        if target.fighter.hp <= 0:
            from rl.online import R_KILL
            self._learn_prev(engine, learner, target, extra=R_KILL, done=True)

    @staticmethod
    def _sign(v: int) -> int:
        return (v > 0) - (v < 0)


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


class BossAI(BaseAI):
    """3×3 の大型ボス。追跡＋近接に加え、薙ぎ払い(範囲)・突進・取り巻き召喚を使う。

    1×1 用の Movement/Melee は使えないため、3×3 をまとめて動かす専用ロジック。
    プレイヤーがボスの9マスのどれかに隣接（外周1マス）したら攻撃する。
    """

    SPECIAL_CHANCE = 0.35  # 特殊行動を試みる確率
    MAX_SUMMONS = 2        # 召喚で出せる取り巻きの上限

    def __init__(self, entity: "Entity"):
        super().__init__(entity)
        self.cd = 0          # 特殊行動のクールダウン
        self.summons = 0     # これまで召喚した取り巻きの数

    def perform(self, engine: "Engine") -> None:
        boss = self.entity
        s = getattr(boss, "size", 3)
        gm = engine.game_map
        if not any(
            gm.in_bounds(boss.x + ox, boss.y + oy) and gm.visible[boss.x + ox, boss.y + oy]
            for ox in range(s) for oy in range(s)
        ):
            return
        if self.cd > 0:
            self.cd -= 1
        player = engine.player
        adjacent = (boss.x - 1 <= player.x <= boss.x + s
                    and boss.y - 1 <= player.y <= boss.y + s)
        # 特殊行動（クールダウンが明けていれば確率で）：隣接=薙ぎ払い / 遠い=召喚 or 突進
        if self.cd == 0 and random.random() < self.SPECIAL_CHANCE:
            if adjacent:
                self._aoe(engine, boss, player); self.cd = 4; return
            if self.summons < self.MAX_SUMMONS and random.random() < 0.5:
                self._summon(engine); self.cd = 6; return
            self._charge(engine, boss, player); self.cd = 5; return
        # 通常：隣接なら近接、でなければ1歩接近
        if adjacent:
            self._attack(engine, boss, player)
            return
        cx, cy = boss.x + s // 2, boss.y + s // 2
        dx = (player.x > cx) - (player.x < cx)
        dy = (player.y > cy) - (player.y < cy)
        for mx, my in ((dx, dy), (dx, 0), (0, dy)):
            if (mx or my) and self._can_move(engine, boss, s, mx, my):
                boss.x += mx
                boss.y += my
                engine.pending_moves.append((boss, mx, my))
                return

    @staticmethod
    def _can_move(engine: "Engine", boss, s: int, mx: int, my: int) -> bool:
        gm = engine.game_map
        for ox in range(s):
            for oy in range(s):
                nx, ny = boss.x + mx + ox, boss.y + my + oy
                if not gm.in_bounds(nx, ny) or not gm.tiles["walkable"][nx, ny]:
                    return False
                other = gm.get_blocking_entity_at(nx, ny)
                if other is not None and other is not boss:
                    return False
        return True

    @staticmethod
    def _hit(engine: "Engine", boss, player, mult: float, verb: str) -> None:
        if player.fighter is None or boss.fighter is None:
            return
        damage = max(1, int((boss.fighter.power - player.fighter.defense) * mult))
        engine.message_log.add_message(f"{boss.name} の{verb}！ {damage} ダメージ", colors.ENEMY_ATK)
        engine.pending_fx.append(("flash", player))
        engine.pending_fx.append(("popup", player.x, player.y, f"-{damage}", (255, 90, 90)))
        combat.inflict_damage(engine, player, damage, attacker=boss)

    def _attack(self, engine: "Engine", boss, player) -> None:
        self._hit(engine, boss, player, 1.0, "大振り")

    def _aoe(self, engine: "Engine", boss, player) -> None:
        """薙ぎ払い：3×3の外周をなぎ、隣接プレイヤーに1.5倍ダメージ。"""
        s = getattr(boss, "size", 3)
        for x in range(boss.x - 1, boss.x + s + 1):
            for y in range(boss.y - 1, boss.y + s + 1):
                inside = boss.x <= x < boss.x + s and boss.y <= y < boss.y + s
                if not inside and engine.game_map.in_bounds(x, y):
                    engine.pending_fx.append(("slash", x, y, 1, 0))
        if (boss.x - 1 <= player.x <= boss.x + s and boss.y - 1 <= player.y <= boss.y + s):
            self._hit(engine, boss, player, 1.5, "薙ぎ払い")
        else:
            engine.message_log.add_message(f"{boss.name} が薙ぎ払った！", colors.ENEMY_ATK)

    def _charge(self, engine: "Engine", boss, player) -> None:
        """突進：プレイヤー方向の主軸へ最大5マス突っ込み、隣接したら一撃。"""
        s = getattr(boss, "size", 3)
        cx, cy = boss.x + s // 2, boss.y + s // 2
        if abs(player.x - cx) >= abs(player.y - cy):
            dx, dy = (1 if player.x > cx else -1), 0
        else:
            dx, dy = 0, (1 if player.y > cy else -1)
        moved = 0
        for _ in range(5):
            if self._can_move(engine, boss, s, dx, dy):
                boss.x += dx
                boss.y += dy
                engine.pending_moves.append((boss, dx, dy))
                moved += 1
            else:
                break
        if moved:
            engine.message_log.add_message(f"{boss.name} が突進してきた！", colors.ENEMY_ATK)
        if (boss.x - 1 <= player.x <= boss.x + s and boss.y - 1 <= player.y <= boss.y + s):
            self._hit(engine, boss, player, 1.0, "突進")

    def _summon(self, engine: "Engine") -> None:
        """取り巻き召喚：フットプリント外周の空きマスにゴブリンを最大2体湧かせる。"""
        import entity_factories
        from procgen import _scale_monster
        boss = self.entity
        s = getattr(boss, "size", 3)
        gm = engine.game_map
        ring = [(x, y)
                for x in range(boss.x - 1, boss.x + s + 1)
                for y in range(boss.y - 1, boss.y + s + 1)
                if not (boss.x <= x < boss.x + s and boss.y <= y < boss.y + s)]
        random.shuffle(ring)
        placed = 0
        for x, y in ring:
            if placed >= 2 or self.summons >= self.MAX_SUMMONS:
                break
            if (gm.in_bounds(x, y) and gm.tiles["walkable"][x, y]
                    and gm.get_blocking_entity_at(x, y) is None):
                m = entity_factories.goblin.spawn(x, y)
                _scale_monster(m, engine.current_floor)
                gm.entities.append(m)
                placed += 1
                self.summons += 1
        if placed:
            engine.message_log.add_message(f"{boss.name} が取り巻きを呼んだ！", colors.ENEMY_ATK)
