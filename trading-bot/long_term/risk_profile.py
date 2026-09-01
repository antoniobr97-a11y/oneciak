"""Risk-profile -> asset-class allocation for the Advanced long-term
portfolio (STRATEGY.md 1.2). The course gives a range per profile; this
takes the midpoint of each range and normalizes to 100% (course does not
give a single exact number, only ranges)."""
from dataclasses import dataclass

from common import config

# (min_score, max_score, profile_name, bond_pct, equity_pct, gold_pct, real_estate_pct)
# max_score=None means "and above". Percentages are the range midpoints from
# STRATEGY.md 1.2, normalized to sum to 100.
_TABLE = [
    (None, 18, "molto_basso", 100.0, 0.0, 0.0, 0.0),
    (19, 22, "basso", 87.5, 6.25, 6.25, 0.0),
    (23, 28, "medio", 67.5, 17.5, 7.5, 2.5),
    (29, 32, "alto", 52.5, 32.5, 7.5, 7.5),
    (33, None, "molto_alto", 32.5, 47.5, 10.0, 10.0),
]


@dataclass
class AssetClassWeights:
    profile: str
    bond: float
    equity: float
    gold: float
    real_estate: float

    def as_dict(self) -> dict[str, float]:
        return {"bond": self.bond, "equity": self.equity, "gold": self.gold, "real_estate": self.real_estate}


def classify(score: int) -> AssetClassWeights:
    for min_score, max_score, name, bond, equity, gold, real_estate in _TABLE:
        if min_score is not None and score < min_score:
            continue
        if max_score is not None and score > max_score:
            continue
        # I punti medi delle 4 fasce indipendenti del corso non sommano
        # sempre esattamente a 100 (sono range non vincolati a un simplex);
        # si normalizza mantenendo le proporzioni relative.
        total = bond + equity + gold + real_estate
        scale = 100.0 / total if total else 1.0
        return AssetClassWeights(name, bond * scale, equity * scale, gold * scale, real_estate * scale)
    raise ValueError(f"Unreachable: score={score} not covered by any risk profile band")


def advanced_target_weights(score: int | None = None) -> dict[str, float]:
    """Per-ticker target weights for long_term/advanced_portfolio.py,
    keyed the same as config.ADVANCED_TICKERS: equity, bond_long,
    bond_short, gold, real_estate. Splits the single 'bond' bucket per
    config.ADVANCED_BOND_LONG_SPLIT (not specified by the course)."""
    weights = classify(score if score is not None else config.LONG_TERM_RISK_SCORE)
    bond_long = weights.bond * config.ADVANCED_BOND_LONG_SPLIT / 100
    bond_short = weights.bond * (1 - config.ADVANCED_BOND_LONG_SPLIT) / 100
    return {
        "equity": weights.equity / 100,
        "bond_long": bond_long,
        "bond_short": bond_short,
        "gold": weights.gold / 100,
        "real_estate": weights.real_estate / 100,
    }
