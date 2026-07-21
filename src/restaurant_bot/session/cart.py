import uuid
from decimal import Decimal
from dataclasses import dataclass, field


@dataclass
class CartItem:
    menu_item_id: uuid.UUID
    name: str
    quantity: int
    unit_price: Decimal
    modifiers: list[dict] = field(default_factory=list)
    special_instructions: str | None = None

    @property
    def item_total(self) -> Decimal:
        modifier_total = sum(
            Decimal(str(opt.get("price_delta", 0)))
            for mod in self.modifiers
            for opt in (mod if isinstance(mod, list) else [mod])
        )
        return (self.unit_price + modifier_total) * self.quantity


@dataclass
class Cart:
    items: list[CartItem] = field(default_factory=list)

    def add_item(self, item: CartItem) -> None:
        # Check if same item with same modifiers exists
        for existing in self.items:
            if (existing.menu_item_id == item.menu_item_id
                and existing.modifiers == item.modifiers
                and existing.special_instructions == item.special_instructions):
                existing.quantity += item.quantity
                return
        self.items.append(item)

    def remove_item(self, menu_item_id: uuid.UUID) -> bool:
        for i, item in enumerate(self.items):
            if item.menu_item_id == menu_item_id:
                self.items.pop(i)
                return True
        return False

    def update_quantity(self, menu_item_id: uuid.UUID, quantity: int) -> bool:
        for item in self.items:
            if item.menu_item_id == menu_item_id:
                if quantity <= 0:
                    return self.remove_item(menu_item_id)
                item.quantity = quantity
                return True
        return False

    def clear(self) -> None:
        self.items.clear()

    @property
    def subtotal(self) -> Decimal:
        return sum(item.item_total for item in self.items)

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0

    def to_dict(self) -> dict:
        return {
            "items": [
                {
                    "menu_item_id": str(item.menu_item_id),
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "modifiers": item.modifiers,
                    "special_instructions": item.special_instructions,
                    "item_total": str(item.item_total),
                }
                for item in self.items
            ],
            "subtotal": str(self.subtotal),
            "item_count": self.item_count,
        }

    def to_summary_dict(self, tax_rate: Decimal = Decimal("0.00"), delivery_fee: Decimal = Decimal("0.00"), tax_inclusive: bool = False) -> dict:
        subtotal = self.subtotal
        if tax_inclusive:
            tax = Decimal("0.00")
        else:
            tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
        total = subtotal + tax + delivery_fee
        return {
            "items": [
                {
                    "menu_item_id": str(item.menu_item_id),
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "modifiers": item.modifiers,
                    "special_instructions": item.special_instructions,
                    "item_total": str(item.item_total),
                }
                for item in self.items
            ],
            "subtotal": str(subtotal),
            "tax": str(tax),
            "delivery_fee": str(delivery_fee),
            "total": str(total),
            "item_count": self.item_count,
        }
