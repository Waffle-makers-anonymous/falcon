"""Database for persisting screen results and enabling backtesting"""

import sqlite3
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from falcon.strategy import ScreeningStrategy
from falcon.screener import ScreenResult


@dataclass
class ScreenRun:
    """Record of a screening strategy execution"""

    id: Optional[int] = None
    strategy_name: str = ""
    scan_code: str = ""
    executed_at: str = ""
    result_count: int = 0

    # Strategy configuration snapshot
    filters: Optional[Dict[str, Any]] = None
    bias: str = ""
    style: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Tuple) -> 'ScreenRun':
        """Create ScreenRun from database row"""
        import json
        return cls(
            id=row[0],
            strategy_name=row[1],
            scan_code=row[2],
            executed_at=row[3],
            result_count=row[4],
            filters=json.loads(row[5]) if row[5] else None,
            bias=row[6],
            style=row[7],
        )


@dataclass
class StoredScreenResult:
    """Screen result with metadata for backtesting"""

    id: Optional[int] = None
    run_id: int = 0

    # Stock identification
    symbol: str = ""
    exchange: str = ""
    contract_id: int = 0

    # Screen data
    rank: int = 0
    distance: Optional[str] = None
    benchmark: Optional[str] = None

    # Market data at screen time
    price_at_screen: Optional[float] = None
    volume_at_screen: Optional[int] = None

    # For backtesting - filled in later
    price_1d_later: Optional[float] = None
    price_1w_later: Optional[float] = None
    price_1m_later: Optional[float] = None

    return_1d: Optional[float] = None
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Tuple) -> 'StoredScreenResult':
        """Create StoredScreenResult from database row"""
        return cls(
            id=row[0],
            run_id=row[1],
            symbol=row[2],
            exchange=row[3],
            contract_id=row[4],
            rank=row[5],
            distance=row[6],
            benchmark=row[7],
            price_at_screen=row[8],
            volume_at_screen=row[9],
            price_1d_later=row[10],
            price_1w_later=row[11],
            price_1m_later=row[12],
            return_1d=row[13],
            return_1w=row[14],
            return_1m=row[15],
        )


class ScreenDatabase:
    """Database for screen results and backtesting"""

    # Schema version for migrations
    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file.
                    Defaults to ~/.falcon/falcon.db
        """
        if db_path is None:
            db_path = os.path.expanduser("~/.falcon/falcon.db")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema if not exists"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Version tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)

            # Screen runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screen_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    scan_code TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    result_count INTEGER NOT NULL DEFAULT 0,
                    filters TEXT,
                    bias TEXT,
                    style TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Screen results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screen_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    contract_id INTEGER NOT NULL,
                    rank INTEGER NOT NULL,
                    distance TEXT,
                    benchmark TEXT,
                    price_at_screen REAL,
                    volume_at_screen INTEGER,
                    price_1d_later REAL,
                    price_1w_later REAL,
                    price_1m_later REAL,
                    return_1d REAL,
                    return_1w REAL,
                    return_1m REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES screen_runs(id)
                )
            """)

            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_screen_runs_strategy
                ON screen_runs(strategy_name, executed_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_screen_results_run
                ON screen_results(run_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_screen_results_symbol
                ON screen_results(symbol, run_id)
            """)

            # Record schema version
            cursor.execute(
                "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (self.SCHEMA_VERSION, datetime.now().isoformat())
            )

    def save_screen_run(
        self,
        strategy: ScreeningStrategy,
        results: List[ScreenResult],
        executed_at: Optional[str] = None
    ) -> int:
        """
        Save a screen run and its results

        Args:
            strategy: Strategy that was executed
            results: List of screen results
            executed_at: Timestamp of execution (defaults to now)

        Returns:
            ID of the created screen run
        """
        import json

        if executed_at is None:
            executed_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert screen run
            cursor.execute("""
                INSERT INTO screen_runs
                (strategy_name, scan_code, executed_at, result_count, filters, bias, style)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy.name,
                strategy.scan_code,
                executed_at,
                len(results),
                json.dumps(strategy.filters.to_dict()),
                strategy.bias.value,
                strategy.style.value,
            ))

            run_id = cursor.lastrowid

            # Insert screen results
            for result in results:
                cursor.execute("""
                    INSERT INTO screen_results
                    (run_id, symbol, exchange, contract_id, rank, distance, benchmark)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    result.symbol,
                    result.exchange,
                    result.contract_id,
                    result.rank,
                    result.distance,
                    result.benchmark,
                ))

            return run_id

    def get_screen_run(self, run_id: int) -> Optional[ScreenRun]:
        """Get a screen run by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM screen_runs WHERE id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            return ScreenRun.from_row(row) if row else None

    def get_screen_results(self, run_id: int) -> List[StoredScreenResult]:
        """Get all results for a screen run"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM screen_results WHERE run_id = ? ORDER BY rank",
                (run_id,)
            )
            return [StoredScreenResult.from_row(row) for row in cursor.fetchall()]

    def get_recent_runs(
        self,
        strategy_name: Optional[str] = None,
        limit: int = 10
    ) -> List[ScreenRun]:
        """
        Get recent screen runs

        Args:
            strategy_name: Filter by strategy name
            limit: Maximum number of runs to return

        Returns:
            List of recent screen runs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if strategy_name:
                cursor.execute("""
                    SELECT * FROM screen_runs
                    WHERE strategy_name = ?
                    ORDER BY executed_at DESC
                    LIMIT ?
                """, (strategy_name, limit))
            else:
                cursor.execute("""
                    SELECT * FROM screen_runs
                    ORDER BY executed_at DESC
                    LIMIT ?
                """, (limit,))

            return [ScreenRun.from_row(row) for row in cursor.fetchall()]

    def get_runs_by_date_range(
        self,
        start_date: str,
        end_date: str,
        strategy_name: Optional[str] = None
    ) -> List[ScreenRun]:
        """
        Get screen runs within a date range

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            strategy_name: Optional strategy filter

        Returns:
            List of screen runs in date range
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if strategy_name:
                cursor.execute("""
                    SELECT * FROM screen_runs
                    WHERE executed_at BETWEEN ? AND ?
                    AND strategy_name = ?
                    ORDER BY executed_at DESC
                """, (start_date, end_date, strategy_name))
            else:
                cursor.execute("""
                    SELECT * FROM screen_runs
                    WHERE executed_at BETWEEN ? AND ?
                    ORDER BY executed_at DESC
                """, (start_date, end_date))

            return [ScreenRun.from_row(row) for row in cursor.fetchall()]

    def get_symbol_appearances(
        self,
        symbol: str,
        days_back: int = 30
    ) -> List[Tuple[ScreenRun, StoredScreenResult]]:
        """
        Get all times a symbol appeared in screens

        Args:
            symbol: Stock symbol to search for
            days_back: How many days to look back

        Returns:
            List of (ScreenRun, StoredScreenResult) tuples
        """
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    r.id, r.strategy_name, r.scan_code, r.executed_at,
                    r.result_count, r.filters, r.bias, r.style,
                    s.id, s.run_id, s.symbol, s.exchange, s.contract_id,
                    s.rank, s.distance, s.benchmark,
                    s.price_at_screen, s.volume_at_screen,
                    s.price_1d_later, s.price_1w_later, s.price_1m_later,
                    s.return_1d, s.return_1w, s.return_1m
                FROM screen_results s
                JOIN screen_runs r ON s.run_id = r.id
                WHERE s.symbol = ?
                AND r.executed_at >= ?
                ORDER BY r.executed_at DESC
            """, (symbol, cutoff))

            results = []
            for row in cursor.fetchall():
                # Split row into run and result parts (8 run columns, 16 result columns)
                run = ScreenRun.from_row(row[:8])
                result = StoredScreenResult.from_row(row[8:])
                results.append((run, result))

            return results

    def update_result_prices(
        self,
        result_id: int,
        price_1d: Optional[float] = None,
        price_1w: Optional[float] = None,
        price_1m: Optional[float] = None
    ):
        """
        Update forward-looking prices for backtesting

        Args:
            result_id: Screen result ID
            price_1d: Price 1 day later
            price_1w: Price 1 week later
            price_1m: Price 1 month later
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get current price at screen
            cursor.execute(
                "SELECT price_at_screen FROM screen_results WHERE id = ?",
                (result_id,)
            )
            row = cursor.fetchone()
            if not row or row[0] is None:
                return

            price_at_screen = row[0]

            # Calculate returns
            return_1d = ((price_1d - price_at_screen) / price_at_screen * 100) if price_1d else None
            return_1w = ((price_1w - price_at_screen) / price_at_screen * 100) if price_1w else None
            return_1m = ((price_1m - price_at_screen) / price_at_screen * 100) if price_1m else None

            # Update prices and returns
            cursor.execute("""
                UPDATE screen_results
                SET price_1d_later = ?,
                    price_1w_later = ?,
                    price_1m_later = ?,
                    return_1d = ?,
                    return_1w = ?,
                    return_1m = ?
                WHERE id = ?
            """, (price_1d, price_1w, price_1m, return_1d, return_1w, return_1m, result_id))

    def get_strategy_statistics(
        self,
        strategy_name: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Get performance statistics for a strategy

        Args:
            strategy_name: Name of strategy
            days_back: How many days to analyze

        Returns:
            Dictionary with statistics
        """
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get run statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_runs,
                    SUM(result_count) as total_results,
                    AVG(result_count) as avg_results_per_run
                FROM screen_runs
                WHERE strategy_name = ?
                AND executed_at >= ?
            """, (strategy_name, cutoff))

            run_stats = cursor.fetchone()

            # Get return statistics (for results with backtesting data)
            cursor.execute("""
                SELECT
                    AVG(return_1d) as avg_return_1d,
                    AVG(return_1w) as avg_return_1w,
                    AVG(return_1m) as avg_return_1m,
                    COUNT(CASE WHEN return_1d > 0 THEN 1 END) as winners_1d,
                    COUNT(CASE WHEN return_1d < 0 THEN 1 END) as losers_1d,
                    COUNT(return_1d) as total_with_data
                FROM screen_results s
                JOIN screen_runs r ON s.run_id = r.id
                WHERE r.strategy_name = ?
                AND r.executed_at >= ?
                AND s.return_1d IS NOT NULL
            """, (strategy_name, cutoff))

            return_stats = cursor.fetchone()

            return {
                "strategy_name": strategy_name,
                "period_days": days_back,
                "total_runs": run_stats[0] or 0,
                "total_results": run_stats[1] or 0,
                "avg_results_per_run": run_stats[2] or 0,
                "avg_return_1d": return_stats[0],
                "avg_return_1w": return_stats[1],
                "avg_return_1m": return_stats[2],
                "winners_1d": return_stats[3] or 0,
                "losers_1d": return_stats[4] or 0,
                "total_with_backtest_data": return_stats[5] or 0,
            }

    def get_top_symbols(
        self,
        strategy_name: Optional[str] = None,
        days_back: int = 30,
        limit: int = 20
    ) -> List[Tuple[str, int]]:
        """
        Get most frequently screened symbols

        Args:
            strategy_name: Optional strategy filter
            days_back: How many days to look back
            limit: Max symbols to return

        Returns:
            List of (symbol, appearance_count) tuples
        """
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if strategy_name:
                cursor.execute("""
                    SELECT s.symbol, COUNT(*) as appearances
                    FROM screen_results s
                    JOIN screen_runs r ON s.run_id = r.id
                    WHERE r.strategy_name = ?
                    AND r.executed_at >= ?
                    GROUP BY s.symbol
                    ORDER BY appearances DESC
                    LIMIT ?
                """, (strategy_name, cutoff, limit))
            else:
                cursor.execute("""
                    SELECT s.symbol, COUNT(*) as appearances
                    FROM screen_results s
                    JOIN screen_runs r ON s.run_id = r.id
                    WHERE r.executed_at >= ?
                    GROUP BY s.symbol
                    ORDER BY appearances DESC
                    LIMIT ?
                """, (cutoff, limit))

            return [(row[0], row[1]) for row in cursor.fetchall()]

    def delete_old_runs(self, days_to_keep: int = 90) -> int:
        """
        Delete screen runs older than specified days

        Args:
            days_to_keep: Number of days of data to keep

        Returns:
            Number of runs deleted
        """
        cutoff = (datetime.now() - timedelta(days=days_to_keep)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get IDs to delete
            cursor.execute(
                "SELECT id FROM screen_runs WHERE executed_at < ?",
                (cutoff,)
            )
            run_ids = [row[0] for row in cursor.fetchall()]

            if not run_ids:
                return 0

            # Delete results first (foreign key constraint)
            placeholders = ','.join('?' * len(run_ids))
            cursor.execute(
                f"DELETE FROM screen_results WHERE run_id IN ({placeholders})",
                run_ids
            )

            # Delete runs
            cursor.execute(
                f"DELETE FROM screen_runs WHERE id IN ({placeholders})",
                run_ids
            )

            return len(run_ids)
