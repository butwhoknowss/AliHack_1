"""Alternative display units for the catalog variables.

Every option is a linear conversion  new = value * factor + offset  applied to the monthly
series *before* the statistics. So slopes and confidence intervals scale by `factor`,
p-values and the verdict do not change, and anomalies ignore the offset.
Options are keyed by the catalog's base unit string, so any variable with that unit gets them.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import DataQualityError

DAYS_PER_YEAR = 365.25
DAYS_PER_MONTH = DAYS_PER_YEAR / 12  # an average month


@dataclass(frozen=True)
class UnitOption:
    id: str
    label: str
    factor: float = 1.0
    offset: float = 0.0


# base unit (exactly as in storage/seed.py) -> extra options (the base unit itself is always offered first)
UNIT_OPTIONS: dict[str, list[UnitOption]] = {
    "°C": [
        UnitOption("degF", "°F", 1.8, 32.0),
        UnitOption("K", "K", 1.0, 273.15),
    ],
    "mm/day": [
        UnitOption("mm_month", "mm/month", DAYS_PER_MONTH),
        UnitOption("mm_year", "mm/year", DAYS_PER_YEAR),
        UnitOption("in_year", "inches/year", DAYS_PER_YEAR / 25.4),
    ],
    "m/s": [
        UnitOption("km_h", "km/h", 3.6),
        UnitOption("mph", "mph", 3600 / 1609.344),
        UnitOption("knots", "knots", 3600 / 1852),
    ],
    "kPa": [
        UnitOption("hPa", "hPa", 10.0),
        UnitOption("inHg", "inHg", 1 / 3.386389),
    ],
    "MJ/m²/day": [
        UnitOption("kWh_m2_day", "kWh/m²/day", 1 / 3.6),
        UnitOption("W_m2", "W/m²", 1e6 / 86400),
    ],
    "fraction (0–1)": [
        UnitOption("percent", "% (0–100)", 100.0),
    ],
}

BASE_ID = "base"


def options_for(base_units: str) -> list[UnitOption]:
    """All units a variable can be shown in; the first one is its own (base) unit."""
    return [UnitOption(BASE_ID, base_units), *UNIT_OPTIONS.get(base_units, [])]


def resolve(base_units: str, unit_id: str | None) -> UnitOption:
    """The option for `unit_id` (None or 'base' -> no conversion). Unknown ids -> HTTP 422."""
    if not unit_id or unit_id == BASE_ID:
        return options_for(base_units)[0]
    for opt in options_for(base_units):
        if opt.id == unit_id:
            return opt
    offered = ", ".join(o.label for o in options_for(base_units))
    raise DataQualityError(f"This variable can't be shown in '{unit_id}'. Available units: {offered}.")
