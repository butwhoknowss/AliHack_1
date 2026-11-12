"""DataSource protocol — every time-series provider implements this."""

from typing import Literal, Protocol

import pandas as pd


class DataSource(Protocol):
    name: str
    citation: str

    async def fetch_point(
        self,
        variable_id: str,
        lat: float,
        lon: float,
        start_year: int,
        end_year: int,
        resolution: Literal["monthly", "daily"],
    ) -> pd.Series:
        """Float Series indexed by Timestamp (month start or day); NaN for missing values."""
        ...
