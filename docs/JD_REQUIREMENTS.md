# Role JD → measurable project evidence

This table is a mapping, **not** a claim that a candidate is automatically eligible.

| Role focus | Demonstrable requirements | Planned repository evidence | Still missing |
|---|---|---|---|
| 九坤量化策略/AI算法 | ML factors, time-series modeling, statistics, repeatable backtests | Causal factors, Ridge/LightGBM, purged walk-forward, cost-adjusted benchmark | Real point-in-time market dataset, exposure controls, statistically valid out-of-sample results |
| 国金量化研究/AI算法 | Financial market modeling, reproducibility, return/risk evaluation | RankIC, return and drawdown, provenance manifest, failure records | Market microstructure, realistic execution and production data |
| 同花顺数据算法 | Data pipeline quality, feature processing, ML experimentation | Typed OHLCV validation, feature engineering, tests/CLI/CI | Spark/Flink/SQL production pipelines and business-scale data |

## Delivery grades
- **G0:** deterministic synthetic engineering demo; correct input/label chronology and green tests, **no investment claims**.
- **G1:** licensed real data, frozen holdouts, clean time-aware testing and benchmark/cost comparisons.
- **G2:** point-in-time membership, halts/delistings, realistic fills, robust factor/risk/turnover exposure analysis.

Do not mark G1/G2 complete based only on a synthetic demo.
