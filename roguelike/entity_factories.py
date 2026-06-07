"""エンティティのテンプレート集。ここを増やせば敵やアイテムの種類が増える。

sprite は assets/<sprite>.png に対応する。画像が無ければ graphics.py が仮タイルを生成する。
"""
from __future__ import annotations

from components.ai import HostileEnemy
from components.consumable import (
    ConfusionConsumable,
    HealingConsumable,
    LightningConsumable,
)
from components.equipment import Equipment
from components.equippable import Equippable, EquipmentType
from components.fighter import Fighter
from components.inventory import Inventory
from components.level import Level
from entity import Entity

player = Entity(
    sprite="player",
    name="プレイヤー",
    blocks_movement=True,
    fighter=Fighter(hp=30, defense=2, power=5, max_stamina=100),
    level=Level(level_up_base=50, level_up_factor=100),
    inventory=Inventory(capacity=8),
    equipment=Equipment(),
)

goblin = Entity(
    sprite="goblin",
    name="ゴブリン",
    blocks_movement=True,
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=10, defense=0, power=3),
    level=Level(xp_given=35),
)

slime = Entity(
    sprite="slime",
    name="スライム",
    blocks_movement=True,
    ai_cls=HostileEnemy,
    fighter=Fighter(hp=16, defense=1, power=4),
    level=Level(xp_given=50),
)

# --- アイテム（blocks_movement=False：床に置かれ、踏むと拾える）---
healing_potion = Entity(
    sprite="potion",
    name="回復薬",
    blocks_movement=False,
    consumable=HealingConsumable(amount=15),
)

lightning_scroll = Entity(
    sprite="scroll",
    name="雷の巻物",
    blocks_movement=False,
    consumable=LightningConsumable(damage=20, maximum_range=6),
)

confusion_scroll = Entity(
    sprite="scroll_confuse",
    name="混乱の巻物",
    blocks_movement=False,
    consumable=ConfusionConsumable(turns=8),
)

# --- 武器・防具（装備品）---
dagger = Entity(
    sprite="dagger",
    name="短剣",
    blocks_movement=False,
    # 軽い：攻撃力は控えめだがスタミナ消費が少なく、何度も振れる
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=2, stamina_cost=20),
)

sword = Entity(
    sprite="sword",
    name="剣",
    blocks_movement=False,
    # 重い：攻撃力は高いがスタミナ消費が大きく、連続では振れない
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=4, stamina_cost=45),
)

leather_armor = Entity(
    sprite="leather_armor",
    name="革の鎧",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=1),
)

chain_mail = Entity(
    sprite="chain_mail",
    name="鎖帷子",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=3),
)
