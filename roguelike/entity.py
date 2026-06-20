from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Optional, Type

if TYPE_CHECKING:
    from components.ai import BaseAI
    from components.consumable import Consumable
    from components.equipment import Equipment
    from components.equippable import Equippable
    from components.fighter import Fighter
    from components.inventory import Inventory
    from components.level import Level
    from item_category import ItemCategory


class Entity:
    """プレイヤー・敵・アイテムなど、ゲーム内の汎用オブジェクト。

    各種 entity_factories のインスタンスを「テンプレート」として用意し、
    spawn() で複製してマップに配置する使い方を想定している。
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        sprite: str = "player",
        name: str = "<未設定>",
        blocks_movement: bool = False,
        ai_cls: Optional[Type["BaseAI"]] = None,
        fighter: Optional["Fighter"] = None,
        level: Optional["Level"] = None,
        consumable: Optional["Consumable"] = None,
        inventory: Optional["Inventory"] = None,
        equippable: Optional["Equippable"] = None,
        equipment: Optional["Equipment"] = None,
        item_category: Optional["ItemCategory"] = None,
        count: int = 1,
        skills=None,
        dialogue=None,
    ):
        self.x = x
        self.y = y
        self.sprite = sprite  # 描画に使うスプライトのキー（graphics.py で画像に対応）
        self.name = name
        self.blocks_movement = blocks_movement  # True なら他者がすり抜けられない
        # AI を持つエンティティ（＝敵）はここに行動ロジックが入る。
        # ★この中身を強化学習の方策に差し替えるのが最終目標。
        self.ai: Optional["BaseAI"] = ai_cls(self) if ai_cls else None
        # 戦闘能力（HP・攻撃力・防御力）。戦えるエンティティだけが持つ。
        self.fighter = fighter
        if self.fighter is not None:
            self.fighter.entity = self  # コンポーネントから所有者を辿れるように
        # 経験値・レベル。プレイヤーは蓄積用、敵は xp_given 提供用。
        self.level = level
        if self.level is not None:
            self.level.entity = self
        # スキルツリー（プレイヤーのみ）。Level と連携してレベル増減で習得/巻戻し。
        self.skills = skills
        if self.skills is not None:
            self.skills.entity = self
            if self.level is not None:
                self.level.skills = self.skills
        # アイテム用：使用効果。プレイヤー用：持ち物。
        self.consumable = consumable
        if self.consumable is not None:
            self.consumable.entity = self
        self.inventory = inventory
        if self.inventory is not None:
            self.inventory.entity = self
        # 装備：equippable はアイテム側（武器/防具）、equipment はプレイヤー側（装備枠）
        self.equippable = equippable
        if self.equippable is not None:
            self.equippable.entity = self
        self.equipment = equipment
        if self.equipment is not None:
            self.equipment.entity = self
        # 持ち物画面の分類の明示指定（素材・大切なもの用。武器/防具/消費は自動判定）
        self.item_category = item_category
        # スタック数（矢などの弾用。通常アイテムは 1）。
        self.count = count
        # 一時的な状態効果（料理バフなど）。主にプレイヤーが使う。
        self.status_effects = []
        # 村のNPC用のセリフ（リスト）。NPC以外は None。
        self.dialogue = dialogue

    def spawn(self, x: int, y: int) -> "Entity":
        """このテンプレートの複製を (x, y) に作って返す。"""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        return clone

    def move(self, dx: int, dy: int) -> None:
        self.x += dx
        self.y += dy
