from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from quotesquad.schemas import MoneyModel

CENT = Decimal("0.01")


def dollars(value: Decimal | int | str) -> MoneyModel:
    amount = Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    return MoneyModel(amount=amount)


def add_money(values: tuple[MoneyModel, ...]) -> MoneyModel:
    total = sum((item.amount for item in values), start=Decimal("0"))
    return dollars(total)
