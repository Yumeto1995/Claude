from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Entity

# スタミナ関連の調整値（ここを変えればバランス調整できる）
ATTACK_STAMINA_COST = 30  # 攻撃1回で消費するスタミナ
STAMINA_REGEN = 10        # 攻撃以外のターンで回復するスタミナ


class Fighter:
    """HP・攻撃力・防御力・スタミナを持つ、戦えるエンティティ用のコンポーネント。

    max_stamina が 0 のエンティティ（敵など）はスタミナ無制限として扱う。
    プレイヤーだけ max_stamina を持たせ、攻撃の連打を抑制する。
    """

    entity: "Entity"  # 所有者。Entity 側で設定される。

    def __init__(self, hp: int, defense: int, power: int, max_stamina: int = 0):
        self.max_hp = hp
        self._hp = hp          # 現在HP（setter経由で 0..max_hp に収める）
        self.defense = defense  # 防御力（受けるダメージを軽減）
        self.power = power      # 攻撃力
        self.max_stamina = max_stamina
        self.stamina = max_stamina  # 最初は満タン

    @property
    def hp(self) -> int:
        return self._hp

    @hp.setter
    def hp(self, value: int) -> None:
        self._hp = max(0, min(value, self.max_hp))

    @property
    def uses_stamina(self) -> bool:
        """スタミナ制の対象か（プレイヤーのみ True）。"""
        return self.max_stamina > 0

    def can_attack(self) -> bool:
        """攻撃に必要なスタミナがあるか。スタミナ制でなければ常に True。"""
        return (not self.uses_stamina) or self.stamina >= ATTACK_STAMINA_COST

    def spend_attack_stamina(self) -> None:
        """攻撃1回分のスタミナを消費する。"""
        if self.uses_stamina:
            self.stamina = max(0, self.stamina - ATTACK_STAMINA_COST)

    def regenerate_stamina(self) -> None:
        """攻撃以外のターンにスタミナを少し回復する。"""
        if self.uses_stamina:
            self.stamina = min(self.max_stamina, self.stamina + STAMINA_REGEN)
