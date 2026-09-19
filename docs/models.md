# Models And Evaluation

The quantitative loop uses a model only after features have been computed from candles available
at the prediction timestamp. The baseline momentum model and dependency-free logistic model run
in the base installation. C2 adds XGBoost and LightGBM behind the `ml` extra.

## Operational Adaptive Model

The live scan and chart endpoints use `AdaptiveDirectionalModel` when the selected provider has
at least 120 labelled candles. It is a local multinomial logistic classifier with standardised
causal OHLCV features: multi-horizon returns, EMA distance and slope, RSI, ATR, Bollinger
position/width, volume z-score and candle geometry. It retrains when the latest candle or the
cost configuration changes, so a periodic scan gradually incorporates newly closed candles.

Labels are deliberately cost-aware and have three outcomes: `LONG` when the forward close
exceeds the configured round-trip cost threshold, `SHORT` when it falls below the negative
threshold, and `NO_TRADE` otherwise. The latest candle is predicted without a label, so its
future close is never used as an input. If history is too short, classes are insufficient or the
optional ML dependencies are missing, the application reports a visible `momentum-baseline`
fallback instead of pretending that the adaptive model was trained.

Every trained signal carries its sample count, label threshold, walk-forward folds, directional
accuracy, precision, recall, coverage and net PnL in metadata. The UI exposes the same information in
the quantitative model panel and `/api/v1/model-status`. These are monitoring metrics, not a
promise of future profitability.

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
