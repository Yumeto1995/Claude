"""観測（状態）のエンコードと行動の定義。

学習（rl/env.py）と本番ゲーム（components/ai.py の RLEnemy）の両方が
この関数を使うことで、「学習時と本番で見えているものが同じ」を保証する。

状態は表形式Q学習で扱える小さな離散値に圧縮する：

- プレイヤーとの相対位置 dx, dy（各 ±CLAMP に丸め → 9×9 通り）
- 自分のHP（3段階：高/中/低）
- プレイヤーのHP（3段階）
- プレイヤーが今攻撃できるか（スタミナが足りているか：2通り）
- 最寄りの味方の方向（8方向＋「味方なし」＝9通り）＝群れ連携の鍵

→ 9 × 9 × 3 × 3 × 2 × 9 = 13122 状態 × 9 行動。

HPを比率（バケット）で持つため、階層スケールで強化された個体でも
同じ方策をそのまま使える。味方方向は最も上位の桁に置くので、
味方なし（コード4）のスライスは 0..1457 が旧設計（味方無し）と同じ並び。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Entity

# 行動：8方向への移動/攻撃（ぶつかれば攻撃）＋ その場で待機
ACTIONS = [
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
    (0, 0),  # 待機
]
N_ACTIONS = len(ACTIONS)

CLAMP = 4  # 相対座標の丸め幅（±4。それより遠くは「遠い」とだけ分かる）
_SPAN = CLAMP * 2 + 1  # 9

_BASE_STATES = _SPAN * _SPAN * 3 * 3 * 2  # 味方情報を除いた基本状態数（=旧設計 1458）
N_ALLY = 9                                # 最寄り味方の方向 8＋なし
N_STATES = _BASE_STATES * N_ALLY          # 13122


def _clamp(v: int) -> int:
    return max(-CLAMP, min(CLAMP, v))


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def _ally_code(agent: "Entity", allies) -> int:
    """最寄りの生存味方の方向を 0..8 で返す（(sx+1)*3+(sy+1)）。

    味方が居なければ中央コード 4 を返す。実在の味方は必ず別マスに居る
    （blocks_movement）ので方向(0,0)＝コード4 とは衝突しない。"""
    if not allies:
        return 4
    living = [a for a in allies
              if a is not agent and a.fighter is not None and a.fighter.hp > 0]
    if not living:
        return 4
    nb = min(living, key=lambda a: max(abs(a.x - agent.x), abs(a.y - agent.y)))
    return (_sign(nb.x - agent.x) + 1) * 3 + (_sign(nb.y - agent.y) + 1)


def _hp_bucket(fighter) -> int:
    """HP比率を 3 段階に分ける（2=高 / 1=中 / 0=低）。"""
    ratio = fighter.hp / max(1, fighter.max_hp)
    if ratio > 2 / 3:
        return 2
    if ratio > 1 / 3:
        return 1
    return 0


def encode(agent: "Entity", player: "Entity", allies=None) -> int:
    """エージェント（敵）から見た現在の状態番号を返す。

    allies に他の敵の一覧を渡すと「最寄り味方の方向」を状態に含める
    （群れ連携の学習用）。渡さない／味方無しなら単体時と同じ扱い。
    """
    dx = _clamp(player.x - agent.x) + CLAMP   # 0..8
    dy = _clamp(player.y - agent.y) + CLAMP   # 0..8
    own_hp = _hp_bucket(agent.fighter)         # 0..2
    foe_hp = _hp_bucket(player.fighter)        # 0..2
    foe_ready = 1 if player.fighter.can_attack() else 0  # スタミナ切れ狙いの鍵
    base = (((dx * _SPAN + dy) * 3 + own_hp) * 3 + foe_hp) * 2 + foe_ready
    return _ally_code(agent, allies) * _BASE_STATES + base
