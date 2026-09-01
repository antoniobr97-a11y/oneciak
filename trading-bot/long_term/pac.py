"""Piano di Accumulo (PAC / DCA): never sells, only buys toward target
weights at each deposit, tracking average cost basis. See STRATEGY.md 1.1
("Piano di Accumulo (PAC)")."""
import math
from dataclasses import dataclass


def pac_buy_orders(
    deposit_amount: float,
    current_value: dict[str, float],
    target_weights: dict[str, float],
    prices: dict[str, float],
) -> dict[str, int]:
    """Alloca il versamento solo verso gli asset sotto peso, senza mai
    vendere. Se il deficit totale verso i pesi target è inferiore al
    versamento (es. un asset è già sopra peso ovunque tranne uno), il
    residuo si distribuisce proporzionalmente ai pesi target."""
    total_future_value = sum(current_value.values()) + deposit_amount
    target_value = {asset: total_future_value * weight for asset, weight in target_weights.items()}
    deficit = {
        asset: max(0.0, target_value[asset] - current_value.get(asset, 0.0)) for asset in target_weights
    }

    total_deficit = sum(deficit.values())
    if total_deficit <= 0:
        dollars_by_asset = {asset: deposit_amount * weight for asset, weight in target_weights.items()}
    elif total_deficit <= deposit_amount:
        remainder = deposit_amount - total_deficit
        dollars_by_asset = {
            asset: deficit[asset] + remainder * target_weights.get(asset, 0.0) for asset in target_weights
        }
    else:
        dollars_by_asset = {
            asset: deposit_amount * (deficit[asset] / total_deficit) for asset in target_weights
        }

    return {
        asset: math.floor(dollars / prices[asset])
        for asset, dollars in dollars_by_asset.items()
        if asset in prices and prices[asset] > 0
    }


@dataclass
class CostBasis:
    avg_cost: float
    qty: float


def update_average_cost(position: CostBasis, buy_qty: float, buy_price: float) -> CostBasis:
    """Prezzo medio di carico (PMC) aggiornato dopo un nuovo acquisto (il
    PAC non vende mai, quindi il PMC scende solo per nuovi acquisti a
    prezzo più basso della media corrente)."""
    if buy_qty <= 0:
        return position
    new_qty = position.qty + buy_qty
    new_avg_cost = (position.avg_cost * position.qty + buy_price * buy_qty) / new_qty
    return CostBasis(avg_cost=new_avg_cost, qty=new_qty)
