"""エンティティのテンプレート集。ここを増やせば敵やアイテムの種類が増える。"""
from __future__ import annotations

from components.ai import HostileEnemy
from components.fighter import Fighter
from entity import Entity

player = Entity(
    char="@",
    color=(255, 255, 255),
    name="プレイヤー",
    blocks_movement=True,
    fighter=Fighter(hp=30, defense=2, power=5),
)

goblin = Entity(
    char="g",
    color=(63, 127, 63),
    name="ゴブリン",
    blocks_movement=True,
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=10, defense=0, power=3),
)

slime = Entity(
    char="s",
    color=(63, 127, 127),
    name="スライム",
    blocks_movement=True,
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=16, defense=1, power=4),
)
