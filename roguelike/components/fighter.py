from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Entity

# スタミナ・満腹度の調整値（ここを変えればバランス調整できる）
DEFAULT_ATTACK_STAMINA_COST = 30  # 武器未装備（素手）時の攻撃消費スタミナ
STAMINA_REGEN = 10                # 攻撃以外のターンで回復するスタミナ
SATIETY_DRAIN = 1                 # 1ターンに減る満腹度
HUNGER_STAMINA_MULT = 1.5         # 空腹時の攻撃消費スタミナ倍率
HUNGER_DAMAGE_MULT = 1.5          # 空腹時に受けるダメージ倍率


class Fighter:
    """HP・攻撃力・防御力・スタミナを持つ、戦えるエンティティ用のコンポーネント。

    max_stamina が 0 のエンティティ（敵など）はスタミナ無制限として扱う。
    プレイヤーだけ max_stamina を持たせ、攻撃の連打を抑制する。
    """

    entity: "Entity"  # 所有者。Entity 側で設定される。

    def __init__(
        self,
        hp: int,
        defense: int,
        power: int,
        max_stamina: int = 0,
        max_satiety: int = 0,
    ):
        self.max_hp = hp
        self._hp = hp                # 現在HP（setter経由で 0..max_hp に収める）
        self.base_defense = defense  # 素の防御力（装備ボーナスは別途加算）
        self.base_power = power       # 素の攻撃力
        self.max_stamina = max_stamina
        self.stamina = max_stamina   # 最初は満タン
        self.max_satiety = max_satiety  # 0 なら満腹度システムの対象外（敵など）
        self.satiety = max_satiety

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
        total = eq.defense_bonus if eq is not None else 0
        for s in getattr(self.entity, "status_effects", []):
            total += s.defense_bonus
        return total

    @property
    def power_bonus(self) -> int:
        eq = getattr(self.entity, "equipment", None)
        total = eq.power_bonus if eq is not None else 0
        for s in getattr(self.entity, "status_effects", []):
            total += s.power_bonus
        return total

    @property
    def uses_stamina(self) -> bool:
        """スタミナ制の対象か（プレイヤーのみ True）。"""
        return self.max_stamina > 0

    @property
    def is_hungry(self) -> bool:
        """空腹か（満腹度が尽きた状態。各種ペナルティが発生）。"""
        return self.max_satiety > 0 and self.satiety <= 0

    def drain_satiety(self) -> None:
        """1ターン分、満腹度を減らす。"""
        if self.max_satiety > 0:
            self.satiety = max(0, self.satiety - SATIETY_DRAIN)

    def restore_satiety(self, amount: int) -> int:
        """満腹度を回復し、実際に回復した量を返す。"""
        if self.max_satiety <= 0:
            return 0
        restored = min(amount, self.max_satiety - self.satiety)
        self.satiety += restored
        return restored

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
        if self.is_hungry:
            cost = int(cost * HUNGER_STAMINA_MULT)  # 空腹だと攻撃が重くなる
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
