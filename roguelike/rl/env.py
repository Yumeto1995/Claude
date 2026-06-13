"""1対1の戦闘アリーナ環境（gym風 reset/step）。

学習用に「小部屋でゴブリン（エージェント） vs プレイヤーbot」を高速に回す。
ダメージ計算・移動判定は本編と同じ actions.MeleeAction / MovementAction を
そのまま使うので、学習した方策は本番のダンジョンでも同じ力学で動く。

プレイヤーbot の行動（本編のプレイヤー挙動の単純化）：
- 隣接していてスタミナがあれば攻撃
- 隣接しているがスタミナ不足なら待機（回復を待つ）
- 離れていれば近づく（まれにランダムに動く）
- 攻撃しなかったターンはスタミナ回復（本編と同じ +10/ターン）

エージェント（敵）はスタミナ無制限（本編の敵と同じ）。
学習で狙う面白さ：「プレイヤーのスタミナが切れた隙に殴り、
回復中は距離を取る」というヒット＆アウェイの獲得。
"""
from __future__ import annotations

import random
from typing import Optional, Tuple

import entity_factories
import tile_types
from actions import MeleeAction, MovementAction
from components.fighter import Fighter
from entity import Entity
from game_map import GameMap
from procgen import _scale_monster
from rl.obs import ACTIONS, encode


class _NullLog:
    """メッセージを捨てるログ（学習中はログ不要・メモリも食わない）。"""

    def add_message(self, *args, **kwargs) -> None:
        pass


class _NullList:
    """アニメ・エフェクト予約を捨てるリスト（学習中は描画しない）。"""

    def append(self, *args) -> None:
        pass


class _ArenaEngine:
    """actions / combat が参照する Engine の最小スタブ。"""

    def __init__(self, game_map: GameMap, player: Entity):
        self.game_map = game_map
        self.player = player
        self.message_log = _NullLog()
        self.pending_animations = _NullList()
        self.pending_moves = _NullList()
        self.pending_fx = _NullList()
        self.game_over = False
        self.current_floor = 1


class ArenaEnv:
    """reset() → 状態番号、step(行動番号) → (状態, 報酬, 終了, info)。"""

    # 報酬の設計（ここを変えると性格が変わる）。
    # 旧設計は「生き残りボーナス＋大きな被弾ペナルティ」で“逃げ得”になり、
    # 敵が近づかず攻撃もしなかった。攻めて削るほど得する形に作り直す：
    #  - 与ダメ・撃破を高評価、被弾・死亡ペナルティは控えめ（攻めを促す）
    #  - プレイヤーへ近づくと加点（接近報酬）／離れる・1ターン経過は減点
    #  - 生存ボーナスは廃止（逃げ続けても得しない）
    R_DEALT = 3.0      # 与ダメージ1点あたり
    R_TAKEN = -0.4     # 被ダメージ1点あたり（小さめ＝攻めても割に合う）
    R_KILL = 40.0      # プレイヤー撃破
    R_DEATH = -6.0     # 自分が倒される（控えめ＝交戦を恐れすぎない）
    R_STEP = -0.3      # 1ターンごとの減点（モタつき・棒立ちを嫌う）
    R_APPROACH = 1.2   # プレイヤーへ1マス近づくごと（離れると同額の減点）

    def __init__(
        self,
        size: int = 9,
        max_steps: int = 80,
        bot_random: float = 0.1,
        floor_range: Tuple[int, int] = (1, 6),
        seed: Optional[int] = None,
    ):
        self.size = size              # 外周1マスは壁
        self.max_steps = max_steps
        self.bot_random = bot_random  # botがランダムに動く確率（行動の多様性）
        # エピソードごとにこの範囲の階層からゴブリンの強さを抽選する。
        # 本編と同じ procgen._scale_monster を使う。観測はHP「比率」なので、
        # 浅層の弱い個体も深層の強い個体も1つのQ表でカバーできる。
        self.floor_range = floor_range
        self.rng = random.Random(seed)
        self.engine: Optional[_ArenaEngine] = None
        self.agent: Optional[Entity] = None
        self.steps = 0

    # ------------------------------------------------------------------ API
    def reset(self) -> int:
        gm = GameMap(self.size, self.size)
        gm.tiles[1:-1, 1:-1] = tile_types.floor  # 外周だけ壁の小部屋

        # ステータスは本編のテンプレートから写す（本編との力学一致のため）
        pf = entity_factories.player.fighter
        gf = entity_factories.goblin.fighter
        player = Entity(
            name="プレイヤーbot", blocks_movement=True,
            fighter=Fighter(hp=pf.max_hp, defense=pf.base_defense,
                            power=pf.base_power, max_stamina=pf.max_stamina),
        )
        agent = Entity(
            name="RLゴブリン", blocks_movement=True,
            fighter=Fighter(hp=gf.max_hp, defense=gf.base_defense,
                            power=gf.base_power),
        )
        _scale_monster(agent, self.rng.randint(*self.floor_range))

        # 離れた2マスにランダム配置
        while True:
            px, py = self._random_floor(gm)
            ax, ay = self._random_floor(gm)
            if max(abs(px - ax), abs(py - ay)) >= 2:
                break
        player.x, player.y = px, py
        agent.x, agent.y = ax, ay

        gm.entities.extend([player, agent])
        self.engine = _ArenaEngine(gm, player)
        self.agent = agent
        self.steps = 0
        return encode(agent, player)

    @staticmethod
    def _dist(a, b) -> int:
        return max(abs(a.x - b.x), abs(a.y - b.y))  # チェビシェフ距離（8方向）

    def step(self, action: int) -> Tuple[int, float, bool, dict]:
        eng, agent, player = self.engine, self.agent, self.engine.player
        self.steps += 1
        agent_hp0 = agent.fighter.hp
        player_hp0 = player.fighter.hp
        dist0 = self._dist(agent, player)

        # --- エージェントの行動（ぶつかれば攻撃、空きマスなら移動、(0,0)は待機）
        dx, dy = ACTIONS[action]
        if (dx, dy) != (0, 0):
            blocking = eng.game_map.get_blocking_entity_at(agent.x + dx, agent.y + dy)
            if blocking is player:
                MeleeAction(dx, dy).perform(eng, agent)
            else:
                MovementAction(dx, dy).perform(eng, agent)

        # --- プレイヤーbot の応手（エージェントが生きていれば）
        if player.fighter.hp > 0 and agent.fighter.hp > 0:
            self._bot_turn()

        # --- 報酬と終了判定
        dealt = player_hp0 - player.fighter.hp
        taken = agent_hp0 - agent.fighter.hp
        # 接近報酬：プレイヤーに近づくほど加点（離れると減点）
        approach = (dist0 - self._dist(agent, player)) * self.R_APPROACH
        reward = dealt * self.R_DEALT + taken * self.R_TAKEN + approach + self.R_STEP
        done = False
        if player.fighter.hp <= 0:
            reward += self.R_KILL
            done = True
        elif agent.fighter.hp <= 0:
            reward += self.R_DEATH
            done = True
        elif self.steps >= self.max_steps:
            done = True   # 時間切れ（生存ボーナスは無し）
        info = {"dealt": dealt, "taken": taken, "steps": self.steps}
        return encode(agent, player), reward, done, info

    # ------------------------------------------------------------- 内部処理
    def _random_floor(self, gm: GameMap) -> Tuple[int, int]:
        return (self.rng.randint(1, self.size - 2),
                self.rng.randint(1, self.size - 2))

    @staticmethod
    def _sign(v: int) -> int:
        return (v > 0) - (v < 0)

    def _bot_turn(self) -> None:
        eng, agent, player = self.engine, self.agent, self.engine.player
        dx = agent.x - player.x
        dy = agent.y - player.y
        adjacent = max(abs(dx), abs(dy)) == 1

        if adjacent and player.fighter.can_attack():
            MeleeAction(self._sign(dx), self._sign(dy)).perform(eng, player)
            return  # 攻撃ターンはスタミナ回復なし（本編と同じ）

        if not adjacent:
            # エージェントへ1歩近づく（たまにランダム）。斜めが角で塞がれて
            # いれば縦・横を試す（失敗時は何も起きない＝その場で待機相当）。
            if self.rng.random() < self.bot_random:
                candidates = [self.rng.choice(ACTIONS[:8])]
            else:
                sx, sy = self._sign(dx), self._sign(dy)
                candidates = [(sx, sy), (sx, 0), (0, sy)]
            for mx, my in candidates:
                if (mx, my) == (0, 0):
                    continue
                move = MovementAction(mx, my)
                move.perform(eng, player)
                if move.consumes_turn:  # 実際に動けたら終わり
                    break
        # 攻撃しなかったターンはスタミナ回復（隣接でスタミナ不足の待機も含む）
        player.fighter.regenerate_stamina()
