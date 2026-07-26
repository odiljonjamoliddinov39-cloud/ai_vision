from __future__ import annotations


class Inventory:
    def __init__(self):
        self.stock: dict[str, int] = {}

    def apply(self, product_name: str, delta: int) -> int:
        current = self.stock.get(product_name, 0)
        self.stock[product_name] = max(0, current + int(delta))
        return self.stock[product_name]
