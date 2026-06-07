from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Entity

# スタミナ関連の調整値（ここを変えればバランス調整できる）
DEFAULT_ATTACK_STAMINA_COST = 30  # 武器未装備（素手）時の攻撃消費スタミナ
STAMINA_REGEN = 10                # 攻撃以外のターンで回復するスタミナ


class Fighter:
    """HP・攻撃力・防御力・スタミナを持つ、戦えるエンティティ用のコンポーネント。

    max_stamina が 0 のエンティティ（敵など）はスタミナ無制限として扱う。
    プレイヤーだけ max_stamina を持たせ、攻撃の連打を抑制する。
    """

    entity: "Entity"  # 所有者。Entity 側で設定される。

    def __init__(self, hp: int, defense: int, power: int, max_stamina: int = 0):
        self.max_hp = hp
        self._hp = hp                # 現在HP（setter経由で 0..max_hp に収める）
        self.base_defense = defense  # 素の防御力（装備ボーナスは別途加算）
        self.base_power = power       # 素の攻撃力
        self.max_stamina = max_stamina
        self.stamina = max_stamina   # 最初は満タン

    @property
    def hp(self) -> int:
        return self._hp

    @hp.setter
    def hp(self, value: int) -> None:
        self._hp = max(0, min(value, self.max_hp))

    # 実効ステータス＝素のステ＋装備ボーナス
    @property
    def defense(self) -> int:
        return self.base_defense + self.defense_bonus

    @property
    def power(self) -> int:
        return self.base_power + self.power_bonus

    @property
    def defense_bonus(self) -> int:
        eq = getattr(self.entity, "equipment", None)
        return eq.defense_bonus if eq is not None else 0

    @property
    def power_bonus(self) -> int:
        eq = getattr(self.entity, "equipment", None)
        return eq.power_bonus if eq is not None else 0

    @property
    def uses_stamina(self) -> bool:
        """スタミナ制の対象か（プレイヤーのみ True）。"""
        return self.max_stamina > 0

    @property
    def attack_stamina_cost(self) -> int:
        """攻撃1回あたりの消費スタミナ。

        武器の消費（武器なしは既定値）＋ 防具の追加消費（重い防具ほど大）。
        """
        cost = DEFAULT_ATTACK_STAMINA_COST
        eq = getattr(self.entity, "equipment", None)
        if eq is not None:
            weapon = eq.weapon
            if (
                weapon is not None
                and weapon.equippable is not None
                and weapon.equippable.stamina_cost is not None
            ):
                cost = weapon.equippable.stamina_cost
            armor = eq.armor
            if (
                armor is not None
                and armor.equippable is not None
                and armor.equippable.stamina_cost is not None
            ):
                cost += armor.equippable.stamina_cost  # 防具の重さ分を加算
        return cost

    def can_attack(self) -> bool:
        """攻撃に必要なスタミナがあるか。スタミナ制でなければ常に True。"""
        return (not self.uses_stamina) or self.stamina >= self.attack_stamina_cost

    def spend_attack_stamina(self) -> None:
        """攻撃1回分のスタミナを消費する。"""
        if self.uses_stamina:
            self.stamina = max(0, self.stamina - self.attack_stamina_cost)

    def regenerate_stamina(self) -> None:
        """攻撃以外のターンにスタミナを少し回復する。"""
        if self.uses_stamina:
            self.stamina = min(self.max_stamina, self.stamina + STAMINA_REGEN)
