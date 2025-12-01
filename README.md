# Falcon Trading Application

A Python application for connecting to Interactive Brokers IB Gateway and monitoring trading accounts in realtime.

## Setup

### Virtual Environment (Recommended)

For local development, it's recommended to use a virtual environment to avoid disrupting your system Python:

```bash
# Create virtual environment
python -m venv .falcon_py

# Activate virtual environment
source .falcon_py/bin/activate  # Linux/Mac
# OR
.falcon_py\Scripts\activate     # Windows
```

**Note**: Virtual environments are recommended for local development but not required. Container deployments can use the system Python directly.

### Installation

1. Copy `.env.example` to `.env` and configure your settings:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Ensure IB Gateway is running on your local machine.

## Configuration

- `IB_HOST`: IB Gateway host (default: 127.0.0.1)
- `IB_PORT`: IB Gateway port (4001 for paper trading, 4002 for live)
- `IB_CLIENT_ID`: Client ID for connection (default: 1)
- `TRADING_MODE`: Trading mode (paper or live)

## Usage

```bash
python falcon/main.py
```

## Development

### Running Tests

Run the comprehensive test suite to ensure code quality:

```bash
# Run all tests
./run_tests.sh

# Run with verbose output
./run_tests.sh -v

# Run specific test file
./run_tests.sh tests/test_config.py

# Run tests matching a pattern
./run_tests.sh -k "test_connection"

# Run only unit tests
./run_tests.sh -m unit
```

### Test Coverage

The test suite includes:
- **Configuration tests**: 12 tests covering config validation, environment variables, and edge cases
- **Connection tests**: 16 tests covering IB Gateway connection, disconnection, status, and account management
- **Main application tests**: 4 tests covering display functionality and error handling

All tests use mocking to avoid requiring a live IB Gateway connection during testing.

### Installing Development Dependencies

```bash
pip install -e ".[dev]"
```

This installs:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-mock` - Mocking utilities
- `black` - Code formatting
