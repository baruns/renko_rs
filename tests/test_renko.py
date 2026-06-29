import numpy as np
import pandas as pd
import polars as pl

from renko_rs import Renko

MODES = ["normal", "wicks", "nongap", "reverse-wicks", "reverse-nongap", "fake-r-wicks", "fake-r-nongap"]

EXPECTED_COLUMNS_WITH_UTILS = ["open", "high", "low", "close", "volume", "direction", "is_reversal", "tick_index_open", "tick_index_close"]
EXPECTED_COLUMNS_NO_UTILS = ["open", "high", "low", "close", "volume"]


def make_tick_data(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    prices = 100.0 + np.cumsum(rng.randn(n) * 0.5)
    dates = pd.date_range("2020-01-01", periods=n, freq="1min")
    return pd.DataFrame({"close": prices}, index=dates)


def test_all_modes_with_utils():
    df = make_tick_data(10_000)
    brick_size = 2.0
    r = Renko(df, brick_size)

    for mode in MODES:
        result = r.renko_df(mode, utils_columns=True)
        assert isinstance(result, pl.DataFrame), f"[{mode}] Expected polars DataFrame"
        assert len(result) > 0, f"[{mode}] Expected non-empty result"
        assert list(result.columns) == EXPECTED_COLUMNS_WITH_UTILS, (
            f"[{mode}] Column mismatch: {list(result.columns)}"
        )
        print(f"  PASS: mode={mode}, rows={len(result)}")


def test_all_modes_without_utils():
    df = make_tick_data(10_000)
    brick_size = 2.0
    r = Renko(df, brick_size)

    for mode in MODES:
        result = r.renko_df(mode, utils_columns=False)
        assert isinstance(result, pl.DataFrame), f"[{mode}] Expected polars DataFrame"
        assert len(result) > 0, f"[{mode}] Expected non-empty result"
        assert list(result.columns) == EXPECTED_COLUMNS_NO_UTILS, (
            f"[{mode}] Column mismatch: {list(result.columns)}"
        )
        print(f"  PASS: mode={mode} (no utils), rows={len(result)}")


def test_brick_size_alignment():
    df = make_tick_data(10_000)
    brick_size = 2.0
    r = Renko(df, brick_size)
    result = r.renko_df("wicks", utils_columns=True)

    closes = result["close"].to_numpy()
    opens = result["open"].to_numpy()

    for i in range(len(closes)):
        close_mod = abs(closes[i] % brick_size)
        assert close_mod < 1e-9 or abs(close_mod - brick_size) < 1e-9, (
            f"Close {closes[i]} is not aligned to brick_size {brick_size}"
        )

    print(f"  PASS: all {len(closes)} bricks aligned to brick_size={brick_size}")


def test_direction_values():
    df = make_tick_data(10_000)
    brick_size = 2.0
    r = Renko(df, brick_size)
    result = r.renko_df("wicks", utils_columns=True)

    directions = result["direction"].to_numpy()
    unique_dirs = set(directions)
    assert unique_dirs.issubset({1, -1}), f"Unexpected direction values: {unique_dirs}"
    assert 1 in unique_dirs, "No up bricks found"
    assert -1 in unique_dirs, "No down bricks found"

    print(f"  PASS: directions are valid (up={sum(directions == 1)}, down={sum(directions == -1)})")


def test_reversal_flags():
    df = make_tick_data(10_000)
    brick_size = 2.0
    r = Renko(df, brick_size)
    result = r.renko_df("wicks", utils_columns=True)

    is_reversal = result["is_reversal"].to_numpy()
    directions = result["direction"].to_numpy()

    for i in range(1, len(directions)):
        if is_reversal[i] == 1:
            assert directions[i] != directions[i - 1], (
                f"Reversal at index {i} but direction didn't change"
            )

    print(f"  PASS: reversal flags consistent ({sum(is_reversal)} reversals)")


def test_high_low_relationship():
    df = make_tick_data(10_000)
    brick_size = 2.0
    r = Renko(df, brick_size)
    result = r.renko_df("wicks", utils_columns=False)

    highs = result["high"].to_numpy()
    lows = result["low"].to_numpy()
    opens = result["open"].to_numpy()
    closes = result["close"].to_numpy()

    for i in range(len(highs)):
        assert highs[i] >= lows[i], f"High < Low at index {i}"
        assert highs[i] >= opens[i], f"High < Open at index {i}"
        assert highs[i] >= closes[i], f"High < Close at index {i}"
        assert lows[i] <= opens[i], f"Low > Open at index {i}"
        assert lows[i] <= closes[i], f"Low > Close at index {i}"

    print(f"  PASS: high/low relationships valid for {len(highs)} bricks")


def test_small_dataset():
    df = make_tick_data(100)
    brick_size = 1.0
    r = Renko(df, brick_size)

    for mode in ["wicks", "normal", "nongap"]:
        result = r.renko_df(mode)
        assert isinstance(result, pl.DataFrame), f"[small_{mode}] Expected polars DataFrame"
        assert len(result) > 0, f"[small_{mode}] Expected non-empty result"
        print(f"  PASS: small dataset mode={mode}, rows={len(result)}")


def test_large_brick():
    df = make_tick_data(5_000)
    brick_size = 50.0
    r = Renko(df, brick_size)
    result = r.renko_df("wicks")
    assert isinstance(result, pl.DataFrame)
    print(f"  PASS: large brick, rows={len(result)}")


def test_tiny_brick():
    df = make_tick_data(2_000)
    brick_size = 0.1
    r = Renko(df, brick_size)
    result = r.renko_df("wicks")
    assert isinstance(result, pl.DataFrame)
    assert len(result) > 100, f"Expected many bricks with tiny brick_size, got {len(result)}"
    print(f"  PASS: tiny brick, rows={len(result)}")


def test_polars_input():
    df_pd = make_tick_data(5_000)
    df_pl = pl.from_pandas(df_pd.reset_index().rename(columns={"index": "datetime"}))
    brick_size = 2.0

    r = Renko(df_pl, brick_size)
    result = r.renko_df("wicks")
    assert isinstance(result, pl.DataFrame)
    assert len(result) > 0
    print(f"  PASS: polars input, rows={len(result)}")


def test_invalid_brick_size():
    df = make_tick_data(100)
    try:
        Renko(df, brick_size=0.0)
        assert False, "Should have raised ValueError for brick_size=0"
    except ValueError:
        print("  PASS: brick_size=0 raises ValueError")

    try:
        Renko(df, brick_size=-1.0)
        assert False, "Should have raised ValueError for negative brick_size"
    except ValueError:
        print("  PASS: negative brick_size raises ValueError")


def test_invalid_mode():
    df = make_tick_data(100)
    r = Renko(df, brick_size=2.0)
    try:
        r.renko_df("invalid_mode")
        assert False, "Should have raised ValueError for invalid mode"
    except ValueError:
        print("  PASS: invalid mode raises ValueError")


def test_consistent_results():
    df = make_tick_data(5_000)
    brick_size = 2.0

    r1 = Renko(df, brick_size)
    result1 = r1.renko_df("wicks")

    r2 = Renko(df, brick_size)
    result2 = r2.renko_df("wicks")

    assert result1.equals(result2), "Same input should produce same output"
    print(f"  PASS: consistent results across instances")


if __name__ == "__main__":
    print("Running renko_rs tests...\n")

    print("--- All modes (with utils) ---")
    test_all_modes_with_utils()

    print("\n--- All modes (without utils) ---")
    test_all_modes_without_utils()

    print("\n--- Brick size alignment ---")
    test_brick_size_alignment()

    print("\n--- Direction values ---")
    test_direction_values()

    print("\n--- Reversal flags ---")
    test_reversal_flags()

    print("\n--- High/Low relationships ---")
    test_high_low_relationship()

    print("\n--- Small dataset ---")
    test_small_dataset()

    print("\n--- Large brick ---")
    test_large_brick()

    print("\n--- Tiny brick ---")
    test_tiny_brick()

    print("\n--- Polars input ---")
    test_polars_input()

    print("\n--- Invalid brick size ---")
    test_invalid_brick_size()

    print("\n--- Invalid mode ---")
    test_invalid_mode()

    print("\n--- Consistent results ---")
    test_consistent_results()

    print("\nAll tests passed!")
