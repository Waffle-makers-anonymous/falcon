# Falcon Screener System Design

## Overview

The Falcon Screener System provides agent-driven stock screening capabilities for discretionary trading. It's designed to allow an AI agent to:
- Execute pre-defined screening strategies
- Learn from strategy performance
- Adapt strategies based on success/failure
- Maintain a library of evolving strategies

## Architecture

### Core Components

1. **Strategy Definition** (`falcon/strategy.py`)
   - `ScreeningStrategy`: Defines a complete screening strategy
   - `ScreenFilters`: Configurable filtering criteria
   - `StrategyPerformance`: Tracks success metrics
   - `TradingBias` & `TradingStyle`: Strategy categorization

2. **Screener Engine** (`falcon/screener.py`)
   - `Screener`: Executes strategies against IB Gateway
   - `ScreenResult`: Standardized result format
   - Multi-strategy execution support

3. **Strategy Library** (`falcon/library.py`)
   - `StrategyLibrary`: Manages strategy persistence
   - JSON-based storage in `~/.falcon/strategies/`
   - Import/export capabilities
   - Performance-based filtering

4. **CLI Interface** (`falcon/screen_cli.py`)
   - Command-line testing tool
   - Single or multi-strategy execution
   - Performance reporting

## Predefined Strategies

### 1. momentum_long
- **Purpose**: Long-biased momentum trading
- **Scan Code**: TOP_PERC_GAIN
- **Filters**:
  - Price: $5 - $500
  - Volume: > 1M
  - Market Cap: > $100M
- **Use Case**: Identify strong uptrending stocks for long positions

### 2. short_bias
- **Purpose**: Short-biased trading
- **Scan Code**: TOP_PERC_LOSE
- **Filters**:
  - Price: $5 - $500
  - Volume: > 1M
  - Market Cap: > $100M
- **Use Case**: Identify weak stocks for short positions

### 3. high_volume_breakout
- **Purpose**: Breakout candidates
- **Scan Code**: HOT_BY_VOLUME
- **Filters**:
  - Price: $10 - $200
  - Volume: > 2M
- **Use Case**: Identify potential breakout opportunities

### 4. high_volatility
- **Purpose**: Volatility plays
- **Scan Code**: HIGH_OPT_IMP_VOLAT
- **Filters**:
  - Price: $5 - $500
  - Volume: > 500K
- **Use Case**: Identify high IV stocks for options strategies

## Strategy Library System

### Storage Format

Strategies are stored as JSON files in `~/.falcon/strategies/`:

```json
{
  "name": "custom_strategy",
  "description": "My custom strategy",
  "scan_code": "TOP_PERC_GAIN",
  "filters": {
    "price_min": 10.0,
    "volume_min": 1000000
  },
  "bias": "long",
  "style": "momentum",
  "performance": {
    "total_runs": 42,
    "successful_picks": 28,
    "failed_picks": 14,
    "avg_return": 3.5,
    "last_run": "2025-12-01T..."
  }
}
```

### Performance Tracking

Each strategy tracks:
- **Total Runs**: Number of times executed
- **Successful/Failed Picks**: Win/loss record
- **Average Return**: Mean return percentage
- **Success Rate**: Win percentage
- **Last Run**: Timestamp of last execution

## Agent Integration (Future)

### Planned Capabilities

1. **Strategy Selection**
   - Agent queries library for relevant strategies
   - Filtered by bias (long/short), style, and performance
   - Top performers prioritized

2. **Result Analysis**
   - Agent reviews screening results
   - Selects interesting stocks for further analysis
   - Makes discretionary trading decisions

3. **Strategy Learning**
   - Agent tracks pick outcomes
   - Updates strategy performance metrics
   - Creates new strategies based on patterns
   - Disables underperforming strategies

4. **Adaptive Behavior**
   - Learns from market conditions
   - Adjusts filter parameters
   - Combines successful patterns
   - Evolves strategy library over time

## Usage Examples

### Run Single Strategy

```bash
python -m falcon.screen_cli momentum_long
```

### Run All Enabled Strategies

```bash
python -m falcon.screen_cli
```

### Python API

```python
from falcon.library import StrategyLibrary
from falcon.screener import Screener
from falcon.connection import IBConnection
from falcon.config import get_config

# Initialize
config = get_config()
conn = IBConnection(config)
await conn.connect()

library = StrategyLibrary()
screener = Screener(conn)

# Run a strategy
strategy = library.get_strategy("momentum_long")
results = await screener.run_strategy(strategy)

# Analyze results
for result in results:
    print(f"{result.rank}. {result.symbol} ({result.exchange})")
```

### Create Custom Strategy

```python
from falcon.strategy import ScreeningStrategy, ScreenFilters, TradingBias, TradingStyle
from falcon.library import StrategyLibrary

# Define custom strategy
custom = ScreeningStrategy(
    name="my_custom_screen",
    description="Custom screening logic",
    scan_code="MOST_ACTIVE",
    filters=ScreenFilters(
        price_min=20.0,
        price_max=100.0,
        volume_min=5_000_000
    ),
    bias=TradingBias.LONG,
    style=TradingStyle.BREAKOUT,
    tags=["custom", "high_volume"]
)

# Save to library
library = StrategyLibrary()
library.save_strategy(custom)
```

## Available IB Scan Codes

- `TOP_PERC_GAIN` - Top % gainers
- `TOP_PERC_LOSE` - Top % losers
- `MOST_ACTIVE` - Most active by volume
- `HOT_BY_VOLUME` - Hot by volume
- `HOT_BY_OPT_VOLUME` - Hot by option volume
- `HIGH_OPT_IMP_VOLAT` - High implied volatility
- `LOW_OPT_IMP_VOLAT` - Low implied volatility
- `TOP_VOLUME_RATE` - Highest volume growth rate

## Future Enhancements

1. **Machine Learning Integration**
   - Pattern recognition in successful picks
   - Automated filter optimization
   - Market regime detection

2. **Advanced Filtering**
   - Technical indicators (RSI, MACD, etc.)
   - Fundamental filters (P/E, EPS, etc.)
   - Custom scoring functions

3. **Multi-Timeframe Analysis**
   - Intraday, daily, weekly screens
   - Trend confirmation across timeframes

4. **Portfolio Integration**
   - Screen for diversification
   - Sector/industry balance
   - Risk-adjusted selection

5. **Backtesting Framework**
   - Historical strategy performance
   - Walk-forward optimization
   - Out-of-sample validation
