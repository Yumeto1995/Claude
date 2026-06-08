"""エンティティのテンプレート集。ここを増やせば敵やアイテムの種類が増える。

sprite は assets/<sprite>.png に対応する。画像が無ければ graphics.py が仮タイルを生成する。
"""
from __future__ import annotations

from components.ai import HostileEnemy
from components.consumable import (
    ConfusionConsumable,
    FoodConsumable,
    HealingConsumable,
    LightningConsumable,
    TentConsumable,
    UnlockZoneConsumable,
)
from components.equipment import Equipment
from components.equippable import Equippable, EquipmentType
from components.fighter import Fighter
from components.inventory import Inventory
from components.level import Level
from entity import Entity
from item_category import ItemCategory

player = Entity(
    sprite="player",
    name="プレイヤー",
    blocks_movement=True,
    fighter=Fighter(hp=30, defense=2, power=5, max_stamina=100, max_satiety=100),
    level=Level(level_up_base=50, level_up_factor=100),
    inventory=Inventory(capacity=12),
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
# 武器：素手の消費は30。軽い武器ほど安く、重い武器ほど高い。
dagger = Entity(
    sprite="dagger",
    name="短剣",
    blocks_movement=False,
    # 軽い：攻撃力控えめだがスタミナ消費が少なく手数で攻める
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=2, stamina_cost=18),
)

sword = Entity(
    sprite="sword",
    name="剣",
    blocks_movement=False,
    # 重い：高火力だがスタミナ消費が大きく、連続では振れない
    equippable=Equippable(EquipmentType.WEAPON, power_bonus=4, stamina_cost=42),
)

# 防具：stamina_cost は攻撃時の追加消費（重い防具ほど攻撃が重くなる）。
leather_armor = Entity(
    sprite="leather_armor",
    name="革の鎧",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=1, stamina_cost=2),
)

chain_mail = Entity(
    sprite="chain_mail",
    name="鎖帷子",
    blocks_movement=False,
    equippable=Equippable(EquipmentType.ARMOR, defense_bonus=3, stamina_cost=8),
)

# --- 素材アイテム（効果なし。将来の合成用などに持っておく）---
slime_shard = Entity(
    sprite="material",
    name="スライムのかけら",
    blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)

# --- 食料・食材（消費アイテム。満腹度を回復し、料理の材料にもなる）---
nuts = Entity(
    sprite="food", name="木の実", blocks_movement=False,
    consumable=FoodConsumable(amount=25),
)
preserved_food = Entity(
    sprite="food", name="携帯食料", blocks_movement=False,
    consumable=FoodConsumable(amount=50),
)
herb = Entity(
    sprite="food", name="薬草", blocks_movement=False,
    consumable=FoodConsumable(amount=15),
)
mushroom = Entity(
    sprite="food", name="キノコ", blocks_movement=False,
    consumable=FoodConsumable(amount=15),
)
meat = Entity(
    sprite="food", name="肉", blocks_movement=False,
    consumable=FoodConsumable(amount=20),
)
# 毒キノコ：生食はできない素材。料理して毒を抜けば食材になる（生焼けだと食中毒）
poison_mushroom = Entity(
    sprite="material", name="毒キノコ", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)

# --- 種（素材。拠点の畑に植えると、階を潜るうちに食材が育つ）---
nut_seed = Entity(
    sprite="seed", name="木の実の種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)
herb_seed = Entity(
    sprite="seed", name="薬草の種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)
mushroom_seed = Entity(
    sprite="seed", name="キノコの種", blocks_movement=False,
    item_category=ItemCategory.MATERIAL,
)

# --- 畜産・漁業の産物（食材。満腹度回復＋料理素材）---
egg = Entity(sprite="food", name="卵", blocks_movement=False,
             consumable=FoodConsumable(amount=15))
milk = Entity(sprite="food", name="ミルク", blocks_movement=False,
              consumable=FoodConsumable(amount=20))
fish = Entity(sprite="food", name="魚", blocks_movement=False,
              consumable=FoodConsumable(amount=20))
big_fish = Entity(sprite="food", name="大魚", blocks_movement=False,
                  consumable=FoodConsumable(amount=35))
# フグ：生食危険な素材（料理して毒を抜く前提）
puffer = Entity(sprite="material", name="フグ", blocks_movement=False,
                item_category=ItemCategory.MATERIAL)

# --- 牧場の動物・漁業のエサ（素材）---
chicken = Entity(sprite="material", name="ニワトリ", blocks_movement=False,
                 item_category=ItemCategory.MATERIAL)
cow = Entity(sprite="material", name="ウシ", blocks_movement=False,
             item_category=ItemCategory.MATERIAL)
bait = Entity(sprite="material", name="エサ", blocks_movement=False,
              item_category=ItemCategory.MATERIAL)

# 料理は固定テンプレートではなく cooking.cook() が動的に生成する。

# --- 大切なもの（捨てられない重要アイテム）---
adventurers_proof = Entity(
    sprite="key_item",
    name="冒険者の証",
    blocks_movement=False,
    item_category=ItemCategory.KEY,
)

# 魔法のテント：大切なものだが「使う」と拠点へ移動できる（消費されない）
magic_tent = Entity(
    sprite="tent",
    name="魔法のテント",
    blocks_movement=False,
    consumable=TentConsumable(),
    item_category=ItemCategory.KEY,
)

# 区画開放の鍵（大切なもの。使うと拠点の区画が開放される）
ranch_key = Entity(
    sprite="key_item", name="牧場の鍵", blocks_movement=False,
    consumable=UnlockZoneConsumable("ranch", "牧場"),
    item_category=ItemCategory.KEY,
)
fishery_key = Entity(
    sprite="key_item", name="漁業の鍵", blocks_movement=False,
    consumable=UnlockZoneConsumable("fishery", "漁業"),
    item_category=ItemCategory.KEY,
)
