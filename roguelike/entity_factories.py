"""エンティティのテンプレート集。ここを増やせば敵やアイテムの種類が増える。

sprite は assets/<sprite>.png に対応する。画像が無ければ graphics.py が仮タイルを生成する。
"""
from __future__ import annotations

from components.ai import HostileEnemy
from components.fighter import Fighter
from entity import Entity

player = Entity(
    sprite="player",
    name="プレイヤー",
    blocks_movement=True,
    fighter=Fighter(hp=30, defense=2, power=5, max_stamina=100),
)

goblin = Entity(
    sprite="goblin",
    name="ゴブリン",
    blocks_movement=True,
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=10, defense=0, power=3),
)

slime = Entity(
    sprite="slime",
    name="スライム",
    blocks_movement=True,
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=16, defense=1, power=4),
)
