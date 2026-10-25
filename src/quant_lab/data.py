"""Input validation and deterministic, *synthetic-only* smoke-test data."""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED = ("date", "asset", "open", "close", "volume")


def validate_market(bars: pd.DataFrame) -> pd.DataFrame:
    """Return a sorted, balanced daily OHLCV panel; fail closed on bad inputs.

    A balanced panel is a conservative v0 restriction. It is NOT a point-in-time
    universe solution: a real experiment still needs constituent/delist data.
    """
    missing = sorted(set(REQUIRED) - set(bars.columns))
    if missing:
        raise ValueError(f"OHLCV missing required columns: {missing}")

    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["asset"] = frame["asset"].astype(str).str.strip()
    if (frame["asset"] == "").any() or frame["date"].isna().any():
        raise ValueError("Date or asset contains an empty value")
    for col in ("open", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if not np.isfinite(frame[col].to_numpy(dtype=float)).all():
            raise ValueError(f"{col}: NaN/infinite values are not supported")
        if (frame[col] <= 0).any():
            raise ValueError(f"{col}: all values must be positive (halted sessions unsupported)")
    if frame.duplicated(["date", "asset"]).any():
        raise ValueError("Duplicate asset/date rows; resolve before modeling")

    frame = frame.sort_values(["asset", "date"]).reset_index(drop=True)
    n_assets = frame["asset"].nunique()
    counts = frame.groupby("date")["asset"].nunique()
    if n_assets < 3 or len(counts) < 60:
        raise ValueError("Need >=3 assets and >=60 common sessions for this research baseline")
    if not (counts == n_assets).all():
        raise ValueError("Unbalanced asset/date panel. Do not forward-fill missing or suspended prices.")

    return frame


def make_demo_market(*, days: int = 260, assets: int = 8, seed: int = 42) -> pd.DataFrame:
    """Synthetic OHLCV with reproducible random numbers; never investment data.

    Returns one common business-day calendar per synthetic asset. Uses nothing
    from live markets, exchanges, feeds, or historical price providers.
    """
    if days < 100 or assets < 3:
        raise ValueError("Demo requires >=100 sessions and >=3 synthetic assets")
    dates = pd.bdate_range("2023-01-02", periods=days)
    rng = np.random.default_rng(seed)
    market = rng.normal(0, 0.007, size=days)
    rows: list[dict] = []
    for j in range(assets):
        open_price = float(20 + 4 * j)
        for i, date in enumerate(dates):
            overnight = 0.5 * market[i] + rng.normal(0, 0.006)
            open_price = open_price * float(np.exp(overnight))
            close_price = open_price * float(np.exp(0.4 * market[i] + rng.normal(0, 0.008)))
            volume = float(np.exp(rng.normal(11.1, 0.4)))
            rows.append(
                {"date": date, "asset": f"DEMO_{j:03d}",
                 "open": open_price, "close": close_price, "volume": volume}
            )
            # The next session's open is generated from this close and new noise.
            open_price = close_price
    return validate_market(pd.DataFrame(rows))
