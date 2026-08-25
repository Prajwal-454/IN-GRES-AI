# Modelling and Forecasting Approach

Forecasting combines physics-based hydrology, statistical time-series models and
machine learning, with uncertainty quantification so every projection is honest
about its confidence.

## Statistical time-series models (currently in production)

Pure-Python models implemented with NumPy only — no external ML dependencies:

- Linear trend (ordinary least squares with a 95% prediction interval and R²).
- Moving average (trailing-window mean).
- Exponential smoothing.
- ARIMA(1,1,0): an autoregressive model on first differences.
- Holt's linear trend (double exponential smoothing).
- Auto: walk-forward holdout validation across all methods; the model with the
  lowest out-of-sample RMSE is chosen and reported.

All projections are clearly labelled as statistical estimates from the current
dataset, never official IN-GRES/CGWB forecasts. When the trend is rising, the
service estimates the years until the over-exploited threshold (100% stage) is
crossed.

## Hydrological models

Physics-based models such as MODFLOW, WEAP and VIC simulate groundwater with
water-balance and flow equations. They are interpretable and support scenario
analysis but need extensive parameterisation and calibration, so they may be
used in tandem to generate synthetic training data.

## Deep learning approaches (roadmap)

- LSTM / RNN for sequential groundwater series. Per-well training is costly, so
  transfer learning pre-trains one model basin-wide and fine-tunes to individual
  wells (reported NSE around 0.91 with far less training time).
- Transformers (attention-based) model long-range dependencies and have been
  reported to outperform CNNs and LSTMs on long-range groundwater prediction,
  though they need more data and compute.
- Spatio-temporal Graph Neural Networks (ST-GNNs) encode spatial relationships
  among wells using graph convolution plus recurrent layers for time; they
  handle missing data well but are computationally intensive.

## Hybrid physics-informed ML

Embedding physical laws (Darcy's law, storage equations, mass balance) into loss
functions or architectures. Hybrid models tend to outperform purely data-driven
ones and give more robust extrapolations and physically consistent behaviour.

## Bayesian and ensemble methods

Bayesian approaches (Gaussian Processes, Bayesian neural nets) or ensemble
averaging (bagging, model averaging) produce predictive distributions, giving
confidence intervals on forecasts. Model averaging combines multiple models, and
bootstrap / dropout / quantile regression provide approximate Bayesian
intervals for fan charts.

## Feature engineering

Key predictors include lagged rainfall, temperature, evapotranspiration, river
levels and abstraction rates, plus spatial features (soil type, elevation) and
seasonal indicators. Automated feature selection and domain-driven indices such
as cropping intensity and NDVI reduce noise.

## Uncertainty quantification

Model runs yield a median forecast and confidence bands visualised as shaded
fans. Calibration is checked (for example 80% of observations inside the 80%
band) and CRPS is tracked in addition to RMSE.

## Scenario and counterfactual analysis

Given a trained model, users can ask what-if questions such as "what if pumping
increases 10%" or "what if rainfall decreases 20%" and see the projected change
versus a no-intervention baseline, supporting recharge projects and policy
planning.

## Explainability

SHAP values quantify each feature's contribution for tree-based or neural
models; attention weights highlight influential time-steps or neighbours. This
lets the system say why a decline is forecast, for example below-normal rainfall
and rising irrigation demand.

## Evaluation

Models are evaluated with RMSE and MAE, Nash-Sutcliffe Efficiency or R², and
CRPS for probabilistic forecasts. Validation splits data by time (train before a
cut-off, test after) and by space (leave-one-region-out cross-validation), plus
historical backtesting against known past years. Skill scores compare against a
persistence or seasonal baseline, and categorical outputs (safe / semi-critical
/ critical / over-exploited) use accuracy and F1. Domain experts review sample
outputs and systematic discrepancies trigger refinement.