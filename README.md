# Treasury Yield Curve Factor Research and a Relative-Value Trading Framework

Research project exploring U.S. Treasury yield curve dynamics using rolling principal component analysis (PCA), then testing whether factor-neutral curve dislocations can support a relative-value trading framework.

This project has two goals:

1. understand the economic structure of the Treasury curve through level, slope, and curvature factors;
2. evaluate whether those factor insights can be turned into a realistic trading signal once delays, volatility targeting, and transaction costs are considered.

## Why this project matters

The Treasury yield curve is one of the most important objects in macroeconomics, fixed income, and systematic trading. Instead of treating each maturity as a separate time series, this project studies the curve as a structured object driven by a small number of common factors.

The research asks two linked questions:

- Can rolling PCA recover the classic level / slope / curvature interpretation of the Treasury curve?
- After removing common factor exposure, do residual relative-value dislocations contain enough signal to support a tradable strategy?

## Main findings

- The Treasury curve is highly low-dimensional: the first few principal components explain the vast majority of daily curve variation.
- The first three components align closely with the classic economic interpretation of:
  - **Level**: the whole curve shifts up or down
  - **Slope**: the front end and long end move differently
  - **Curvature**: the belly moves differently from the wings
- A naive relative-value backtest can appear promising.
- Once more realistic assumptions are added — such as signal delay, volatility targeting, and transaction costs — performance weakens materially.
- The main conclusion is that **factor structure is strong, but extracting robust trading edge is much harder than a simple in-sample backtest suggests**.

## Project overview

The workflow is:

1. Load Treasury curve data across maturities.
2. Convert the data into a clean panel of yield changes.
3. Estimate rolling PCA to study how curve factors evolve through time.
4. Interpret the leading components economically.
5. Build a relative-value signal from residual curve dislocations.
6. Backtest both a naive and a more realistic implementation.
7. Compare performance under progressively stricter assumptions.

## Methods

### 1. Yield curve factor extraction
Rolling PCA is applied to changes in Treasury yields across maturities. This allows the project to estimate the dominant modes of curve movement over time rather than assuming a fixed covariance structure for the full sample.

### 2. Factor interpretation
The leading components are interpreted through their loading shapes:

- **PC1**: broad parallel shift of the curve
- **PC2**: steepening vs flattening
- **PC3**: curvature or belly-vs-wings movement

### 3. Relative-value construction
Using the factor model, the framework looks for curve segments whose movement is unusually rich or cheap relative to the common factor structure. This motivates a factor-aware relative-value signal.

### 4. Backtesting
The strategy is evaluated under increasingly realistic assumptions, including:

- lagged signals to avoid lookahead bias
- volatility scaling
- transaction costs / spread assumptions
- out-of-sample style evaluation logic
