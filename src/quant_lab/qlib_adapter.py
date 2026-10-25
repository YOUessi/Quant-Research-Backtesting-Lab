"""Optional, unverified-with-real-data Alpha158 integration.

Qlib features are imported only from col_set='feature'. Qlib's default label
is deliberately ignored; this project's open-to-open target is reconstructed
from raw Qlib OHLCV. Install Qlib and download an authorized data provider
before running the 'qlib' CLI.
"""

from __future__ import annotations

import pandas as pd


def load_qlib_alpha158(
    *, provider_uri: str, instruments: str,
    start: str, end: str, fit_end: str,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Load Qlib Alpha158 features and join point-aligned raw OHLCV.

    Caveats: this is an adapter, *not* point-in-time universe or tradability
    certification. Qlib's adjusted prices and changing constituents still
    require an independent data audit.
    """
    try:
        import qlib
        from qlib.contrib.data.handler import Alpha158
        from qlib.data import D
    except ImportError as exc:
        raise RuntimeError("Optional Qlib dependency missing: pip install -e '.[qlib]'") from exc
    if not start <= fit_end < end:
        raise ValueError("fit_end must be inside the requested range and before end")
    qlib.init(provider_uri=provider_uri, region="cn")
    handler = Alpha158(
        instruments=instruments,
        start_time=start, end_time=end,
        fit_start_time=start, fit_end_time=fit_end,
    )
    features = handler.fetch(col_set="feature")
    if not isinstance(features.index, pd.MultiIndex):
        raise ValueError("Unexpected Qlib Alpha158 index type; expected MultiIndex")
    feat = features.reset_index()
    feat = feat.rename(columns={"datetime": "date", "instrument": "asset"})
    if not {"date", "asset"}.issubset(feat.columns):
        raise ValueError("Unexpected Qlib feature MultiIndex names")
    rename = {col: "alpha_" + str(col) for col in feat.columns if col not in ("date", "asset")}
    feat = feat.rename(columns=rename)
    alpha_names = tuple(rename.values())

    # Raw Qlib fields refer only to the contemporaneous daily bars. No Ref(-1).
    bars = D.features(
        D.instruments(instruments), ["$open", "$close", "$volume"],
        start_time=start, end_time=end, freq="day",
    )
    if not isinstance(bars.index, pd.MultiIndex):
        raise ValueError("Unexpected Qlib raw OHLCV index type")
    bars = bars.reset_index().rename(columns={
        "datetime": "date", "instrument": "asset",
        "$open": "open", "$close": "close", "$volume": "volume",
    })
    if not {"date", "asset", "open", "close", "volume"}.issubset(bars.columns):
        raise ValueError("Unexpected Qlib raw field names")
    merged = bars.merge(feat, on=["date", "asset"], how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("Qlib raw and Alpha158 features do not align")
    return merged, alpha_names
