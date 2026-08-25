# Data Sources and Reliability

The system aggregates heterogeneous Indian groundwater datasets. Each source has
different spatial resolution, temporal frequency, access method and data quality,
so answers should always state which source and year they rely on.

## Groundwater levels (CGWB)

The Central Ground Water Board (CGWB) monitors about 25,000 wells nationwide
(open wells and piezometers). Readings are seasonal manual observations
(quarterly: March, August, November, January) and newer telemetry via Digital
Water Level Recorders (DWLR) at 6-hourly intervals. Point data come with
significant gaps and outliers; published studies filter tens of thousands of
wells down to a few thousand reliable series after quality control. Access is via
the CGWB Water Level Data portal or WIMS.

## Rainfall (IMD)

The India Meteorological Department (IMD) publishes high-resolution gridded
daily rainfall (0.25 degree grid, roughly 135 by 129 cells) for 1901 to 2024 in
NetCDF format with very few missing values. The National Water Data Portal (CWC)
also publishes daily rain-gauge totals used for cross-checks. Rainfall is the
primary recharge input to the models.

## River flows (CWC / NWDP)

The National Water Data Portal publishes river discharge time series from about
600 gauging stations, for example "River Discharge (Manual - Daily)" as CSV.
Frequency ranges from hourly telemetry to daily manual readings. Coverage is
dense in major basins but has gaps in some tributaries, which can be filled by
interpolation or river modelling.

## Soil and moisture (NRSC / Bhuvan, NBSS)

Soil type and texture maps exist at roughly 5-10 km resolution (NBSS / ICAR).
ISRO's Bhuvan portal provides a Surface Soil Moisture product (0.25 degree grid,
bi-daily) derived from AWiFS and static soil parameters (soil organic carbon,
pH, etc.) at 5 km. These help estimate water retention and recharge. Known
issues: remote sensing gaps from clouds and retrieval errors.

## Land use / land cover (NRSC / Bhuvan)

Bhuvan hosts Land Use-Land Cover (LULC) maps: 1:50,000-scale maps for 2005-06,
2011-12 and 2015-16, and annual 1:250,000 maps from 2004-05 through 2022-23.
They classify cropland, forest, built-up and other cover and inform irrigation
demand and recharge. LULC updates are periodic (multi-year) so they may not
reflect annual changes.

## Irrigation and extraction

There is no real-time pumpage dataset. CGWB publishes annual Dynamic Ground
Water Resources reports (for example, about 247 billion cubic metres extracted
nationally in the 2025 assessment). State Irrigation Departments report canal
supplies and the agricultural census gives irrigated area by district. These
aggregates calibrate the models; fine-scale pumping uses proxies such as power
usage and cropping intensity.

## Aquifer and well logs (CGWB NAQUIM)

CGWB's NAQUIM aquifer mapping covers the country at 1:50,000 scale and provides
aquifer geometry and lithology. Well construction logs (depth, strata) exist in
CGWB and state databases. These refine model parameters such as specific yield
and transmissivity.

## Satellite storage and soil moisture (NASA GRACE, SMAP)

GRACE / GRACE-FO deliver Terrestrial Water Storage anomalies from 2002 onward at
about 300 km resolution. They capture large-scale groundwater trends, especially
in northwest India, but require conversion via specific yield to estimate depth
to water. NASA SMAP gives near-surface soil moisture (top 5 cm, 9 km grid) that
aids data assimilation. These global products must be downscaled where well
coverage is sparse.

## Socio-economic data

Demographics (Census), land-use economics (state budgets, crop yields) and
water-use tariffs inform demand-side modelling at district or state resolution
with multi-year updates. They prioritise interventions but are not fed directly
into short-term prediction models.

## Policies and regulation

Groundwater regulation information (CGWA permits, Atal Bhujal Yojana investment)
is qualitative. These inputs shape system knowledge about where extraction
limits apply and act as constraints or scenario triggers rather than direct
numeric data.

## Data quality summary

- Groundwater and soil data are point-based or coarse grids; rainfall and GRACE
  are continuous gridded fields.
- Temporal spans: groundwater roughly 1970s to present (quarterly), rainfall
  1901 to present (daily), soil moisture and GRACE 2002 to present (bi-daily /
  monthly).
- Missing records and measurement error are handled with mean / KNN imputation,
  Kalman filters and model-based gap filling, plus outlier removal (for example
  three-sigma filters) before any modelling.