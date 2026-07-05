"""複数敵アリーナ（群れ戦術の学習用・gym風）。

`rl/env.py` の 1対1 を N体のゴブリン vs プレイヤーbot に拡張したもの。
全ゴブリンは **同じQ表を共有**して各自 ε-greedy で動く（独立Q学習＝IQL）。
ダメージ計算・移動判定は本編の actions.MeleeAction / MovementAction を
そのまま使うので、学習した方策は本番のダンジョンでも同じ力学で動く。

1体では強いプレイヤーにまず勝てない（rl/env.py の生存率0%参照）。
複数で囲めば勝てる——そこで「無闇に固まらず回り込んで袋叩きにする」
連携が学べるか、を狙う環境。まずは観測は 1対1 と同じ（各ゴブリンは
プレイヤーだけを見る）まま、群れの学習ループとベースライン比較の土台を作る。

プレイヤーbot（本編プレイヤーの単純化・複数敵対応）：
- 最も近いゴブリンが隣接していてスタミナがあれば、それを攻撃
- 近い敵が居なければ最も近いゴブリンへ1歩近づく（まれにランダム）
- 攻撃しなかったターンはスタミナ回復（本編と同じ）
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

import entity_factories
import tile_types
from actions import MeleeAction, MovementAction
from components.fighter import Fighter
from entity import Entity
from game_map import GameMap
from procgen import _scale_monster
from rl.env import ArenaEnv, _ArenaEngine
from rl.obs import ACTIONS, encode


class PackArenaEnv:
    """reset() → 状態リスト、step(行動リスト) → (状態, 報酬, 終了, info) の各リスト。

    行動・報酬・終了は「生きているゴブリンごと」に list で返す（index は
    self.agents と一致）。倒れたゴブリンの枠は行動を無視し、done=True を返す。
    """

    # 報酬係数は 1対1（rl/env.py）と共有してブレを防ぐ。
    R_DEALT = ArenaEnv.R_DEALT
    R_TAKEN = ArenaEnv.R_TAKEN
    R_KILL = ArenaEnv.R_KILL
    R_DEATH = ArenaEnv.R_DEATH
    R_STEP = ArenaEnv.R_STEP
    R_APPROACH = ArenaEnv.R_APPROACH

    def __init__(
        self,
        size: int = 11,
        n_agents: int = 3,
        max_steps: int = 100,
        bot_random: float = 0.1,
        floor_range: Tuple[int, int] = (1, 6),
        kiting: bool = True,
        vary_agents: bool = False,
        seed: Optional[int] = None,
    ):
        self.size = size
        self.n_agents = n_agents   # 群れの最大数（vary_agents 時は上限）
        # vary_agents=True：毎エピソード 1..n_agents 体を抽選。ソロ個体（味方なし）
        # も学習に混ぜるため。本編はゴブリンが1体だけの場面もあるので必要。
        self.vary_agents = vary_agents
        self.max_steps = max_steps
        self.bot_random = bot_random
        self.floor_range = floor_range
        # kiting=True：プレイヤーは「2体以上に囲まれたら逃げる」。開けた部屋で
        # 全員突進だと逃げ道が空くので、多方向から囲んで退路を断つ連携が要る。
        self.kiting = kiting
        self.rng = random.Random(seed)
        self.engine: Optional[_ArenaEngine] = None
        self.agents: List[Entity] = []
        self.steps = 0

    # ------------------------------------------------------------------ API
    def reset(self) -> List[int]:
        gm = GameMap(self.size, self.size)
        gm.tiles[1:-1, 1:-1] = tile_types.floor  # 外周だけ壁の小部屋

        pf = entity_factories.player.fighter
        gf = entity_factories.goblin.fighter
        player = Entity(
            name="プレイヤーbot", blocks_movement=True,
            fighter=Fighter(hp=pf.max_hp, defense=pf.base_defense,
                            power=pf.base_power, max_stamina=pf.max_stamina),
        )
        # 群れは1エピソード＝同じ階層の強さで揃える（同じ群れという想定）。
        floor = self.rng.randint(*self.floor_range)

        # プレイヤーを置いてから、そこから2マス以上離してゴブリンを重ならず配置。
        occupied = set()
        px, py = self._free_cell(gm, occupied)
        player.x, player.y = px, py
        occupied.add((px, py))

        count = self.rng.randint(1, self.n_agents) if self.vary_agents else self.n_agents
        agents: List[Entity] = []
        for _ in range(count):
            while True:
                ax, ay = self._free_cell(gm, occupied)
                if max(abs(px - ax), abs(py - ay)) >= 2:
                    break
            g = Entity(
                name="RLゴブリン", blocks_movement=True,
                fighter=Fighter(hp=gf.max_hp, defense=gf.base_defense,
                                power=gf.base_power),
            )
            _scale_monster(g, floor)
            g.x, g.y = ax, ay
            occupied.add((ax, ay))
            agents.append(g)

        gm.entities.append(player)
        gm.entities.extend(agents)
        self.engine = _ArenaEngine(gm, player)
        self.agents = agents
        self.steps = 0
        return [encode(g, player, agents) for g in agents]

    def step(self, actions: List[int]):
        eng, player = self.engine, self.engine.player
        self.steps += 1
        n = len(self.agents)

        alive0 = [g.fighter.hp > 0 for g in self.agents]
        hp0 = [g.fighter.hp for g in self.agents]
        dist0 = [self._dist(g, player) for g in self.agents]
        dealt = [0.0] * n           # このステップで各ゴブリンがプレイヤーに与えた総ダメ

        # --- ゴブリンの行動（順番の先手/後手バイアスを消すため毎回シャッフル）
        order = [i for i in range(n) if alive0[i]]
        self.rng.shuffle(order)
        for i in order:
            if player.fighter.hp <= 0:
                break  # プレイヤーが倒れたら残りは動かない
            g = self.agents[i]
            dx, dy = ACTIONS[actions[i]]
            if (dx, dy) == (0, 0):
                continue
            p_hp = player.fighter.hp
            blocking = eng.game_map.get_blocking_entity_at(g.x + dx, g.y + dy)
            if blocking is player:
                MeleeAction(dx, dy).perform(eng, g)
                dealt[i] += p_hp - player.fighter.hp
            elif blocking is None:
                MovementAction(dx, dy).perform(eng, g)
            # 他ゴブリンに塞がれている場合は何もしない（＝待機相当）

        # --- プレイヤーbot の応手（まだ生きているゴブリンが居れば1回）
        if player.fighter.hp > 0 and any(g.fighter.hp > 0 for g in self.agents):
            self._bot_turn()

        # --- 報酬・終了を各ゴブリンごとに算出
        player_dead = player.fighter.hp <= 0
        rewards = [0.0] * n
        dones = [True] * n
        for i, g in enumerate(self.agents):
            if not alive0[i]:
                continue  # もともと死んでいた枠は据え置き（学習側で無視）
            taken = hp0[i] - g.fighter.hp
            approach = (dist0[i] - self._dist(g, player)) * self.R_APPROACH
            r = dealt[i] * self.R_DEALT + taken * self.R_TAKEN + approach + self.R_STEP
            if player_dead:
                r += self.R_KILL        # 撃破は群れ全員の手柄（連携を促す）
                dones[i] = True
            elif g.fighter.hp <= 0:
                r += self.R_DEATH
                dones[i] = True
            else:
                dones[i] = False
            rewards[i] = r

        done_all = player_dead or all(g.fighter.hp <= 0 for g in self.agents) \
            or self.steps >= self.max_steps
        states = [encode(g, player, self.agents) for g in self.agents]
        info = {"player_dead": player_dead, "steps": self.steps,
                "alive0": alive0, "done_all": done_all}
        return states, rewards, dones, info

    # ------------------------------------------------------------- 内部処理
    @staticmethod
    def _dist(a, b) -> int:
        return max(abs(a.x - b.x), abs(a.y - b.y))  # チェビシェフ距離（8方向）

    @staticmethod
    def _sign(v: int) -> int:
        return (v > 0) - (v < 0)

    def _free_cell(self, gm: GameMap, occupied) -> Tuple[int, int]:
        while True:
            c = (self.rng.randint(1, self.size - 2),
                 self.rng.randint(1, self.size - 2))
            if c not in occupied:
                return c

    def _nearest_dist(self, x: int, y: int) -> int:
        """(x,y) から最寄りの生存ゴブリンまでのチェビシェフ距離。"""
        living = [g for g in self.agents if g.fighter.hp > 0]
        return min(max(abs(g.x - x), abs(g.y - y)) for g in living)

    def _try_flee(self) -> bool:
        """空きマスへ動いて最寄りゴブリンから距離を稼ぐ。稼げれば True。

        今の最寄り距離より遠くなる移動先だけを候補にする。全て塞がれて
        （＝囲まれて）距離を伸ばせなければ False＝逃げ切れず殴られる。"""
        eng, player = self.engine, self.engine.player
        cur = self._nearest_dist(player.x, player.y)
        best = None
        best_d = cur
        for mx, my in ACTIONS[:8]:
            nx, ny = player.x + mx, player.y + my
            if not eng.game_map.tiles["walkable"][nx, ny]:
                continue
            if eng.game_map.get_blocking_entity_at(nx, ny) is not None:
                continue
            d = self._nearest_dist(nx, ny)
            if d > best_d:
                best_d, best = d, (mx, my)
        if best is None:
            return False
        MovementAction(*best).perform(eng, player)
        return True

    def _nearest_agent(self) -> Optional[Entity]:
        living = [g for g in self.agents if g.fighter.hp > 0]
        if not living:
            return None
        p = self.engine.player
        return min(living, key=lambda g: self._dist(g, p))

    def _bot_turn(self) -> None:
        eng, player = self.engine, self.engine.player
        target = self._nearest_agent()
        if target is None:
            return

        # 囲まれたら逃げる（kiting）。周囲2マス以内に2体以上居たら退路を探す。
        # 全方向を塞がれて距離を稼げなければ「袋叩き」＝諦めて隣接を殴る。
        if self.kiting:
            near = sum(1 for g in self.agents
                       if g.fighter.hp > 0 and self._dist(g, player) <= 2)
            if near >= 2 and self._try_flee():
                player.fighter.regenerate_stamina()
                return

        dx = target.x - player.x
        dy = target.y - player.y
        adjacent = max(abs(dx), abs(dy)) == 1

        if adjacent and player.fighter.can_attack():
            MeleeAction(self._sign(dx), self._sign(dy)).perform(eng, player)
            return  # 攻撃ターンはスタミナ回復なし（本編と同じ）

        if not adjacent:
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
                if move.consumes_turn:
                    break
        # 攻撃しなかったターンはスタミナ回復
        player.fighter.regenerate_stamina()
