# Models And Evaluation

The quantitative loop uses a model only after features have been computed from candles available
at the prediction timestamp. The baseline momentum model and dependency-free logistic model run
in the base installation. C2 adds XGBoost and LightGBM behind the `ml` extra.

## Training

`build_directional_examples` creates one row per decision timestamp and shifts the label forward
to the next candle or configured horizon. The feature engine is causal: rolling statistics and
indicators use the current row and earlier rows only.

## Walk-Forward

`WalkForwardSplit` uses expanding training windows by default. `purge_size` removes examples
between the end of a training window and the beginning of its test window, preventing forward
labels from crossing the boundary. Each fold fits a fresh model and reports classification and
trading metrics only on its out-of-sample test window.

## Artifacts

XGBoost is saved as `model.json`; LightGBM is saved as `model.txt`. Both are accompanied by
`manifest.json`, which records the feature schema, training configuration, library version and
SHA-256 checksum. Loading refuses a missing, mismatched or modified native model file.

## Costs And Metrics

The backtester applies two fee legs, two slippage legs and one full spread per round trip. It
reports gross and net basis points, expectancy, Profit Factor, trade Sharpe, trade Sortino,
maximum drawdown, ending equity, net PnL and total return. These figures are research outputs;
synthetic-data performance does not establish real-market profitability.
