import sys
import os
import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from renkodf import Renko as PyRenko
from renko_rs import Renko as RsRenko


def make_tick_data(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    prices = 100.0 + np.cumsum(rng.randn(n) * 0.5)
    dates = pd.date_range("2020-01-01", periods=n, freq="1min")
    return pd.DataFrame({"close": prices}, index=dates)


def compare_dataframes(py_df: pd.DataFrame, rs_df: pl.DataFrame, mode: str, tol: float = 1e-9):
    rs_pd = rs_df.to_pandas().reset_index(drop=True)
    py_df = py_df.reset_index(drop=True)

    assert list(py_df.columns) == list(rs_pd.columns), (
        f"[{mode}] Column mismatch: {list(py_df.columns)} vs {list(rs_pd.columns)}"
    )
    assert len(py_df) == len(rs_pd), (
        f"[{mode}] Row count mismatch: {len(py_df)} vs {len(rs_pd)}"
    )

    for col in py_df.columns:
        py_col = py_df[col].values
        rs_col = rs_pd[col].values

        if py_col.dtype.kind == "f":
            mask = np.isfinite(py_col) & np.isfinite(rs_col)
            if mask.any():
                max_diff = np.max(np.abs(py_col[mask] - rs_col[mask]))
                assert max_diff < tol, (
                    f"[{mode}] Column '{col}' max diff: {max_diff}"
                )
        else:
            assert np.array_equal(py_col, rs_col), (
                f"[{mode}] Column '{col}' not equal"
            )


def test_all_modes():
    df = make_tick_data(10_000)
    brick_size = 2.0

    py_renko = PyRenko(df, brick_size)
    rs_renko = RsRenko(df, brick_size)

    for mode in ["normal", "wicks", "nongap", "reverse-wicks",
                  "reverse-nongap", "fake-r-wicks", "fake-r-nongap"]:
        py_df = py_renko.renko_df(mode, utils_columns=True)
        rs_df = rs_renko.renko_df(mode, utils_columns=True)
        compare_dataframes(py_df, rs_df, mode)
        print(f"  PASS: mode={mode}, rows={len(rs_df)}")

    for mode in ["normal", "wicks", "nongap", "reverse-wicks",
                  "reverse-nongap", "fake-r-wicks", "fake-r-nongap"]:
        py_df = py_renko.renko_df(mode, utils_columns=False)
        rs_df = rs_renko.renko_df(mode, utils_columns=False)
        compare_dataframes(py_df, rs_df, f"{mode}_no_utils")
        print(f"  PASS: mode={mode} (no utils), rows={len(rs_df)}")


def test_small_dataset():
    df = make_tick_data(100)
    brick_size = 1.0

    py_renko = PyRenko(df, brick_size)
    rs_renko = RsRenko(df, brick_size)

    for mode in ["wicks", "normal", "nongap"]:
        py_df = py_renko.renko_df(mode)
        rs_df = rs_renko.renko_df(mode)
        compare_dataframes(py_df, rs_df, f"small_{mode}")
        print(f"  PASS: small dataset mode={mode}, rows={len(rs_df)}")


def test_large_brick():
    df = make_tick_data(5_000)
    brick_size = 50.0

    py_renko = PyRenko(df, brick_size)
    rs_renko = RsRenko(df, brick_size)

    py_df = py_renko.renko_df("wicks")
    rs_df = rs_renko.renko_df("wicks")
    compare_dataframes(py_df, rs_df, "large_brick")
    print(f"  PASS: large brick, rows={len(rs_df)}")


def test_tiny_brick():
    df = make_tick_data(2_000)
    brick_size = 0.1

    py_renko = PyRenko(df, brick_size)
    rs_renko = RsRenko(df, brick_size)

    py_df = py_renko.renko_df("wicks")
    rs_df = rs_renko.renko_df("wicks")
    compare_dataframes(py_df, rs_df, "tiny_brick")
    print(f"  PASS: tiny brick, rows={len(rs_df)}")


def test_polars_input():
    df_pd = make_tick_data(5_000)
    df_pl = pl.from_pandas(df_pd.reset_index().rename(columns={"index": "datetime"}))
    brick_size = 2.0

    py_renko = PyRenko(df_pd, brick_size)
    rs_renko = RsRenko(df_pl, brick_size)

    py_df = py_renko.renko_df("wicks")
    rs_df = rs_renko.renko_df("wicks")
    compare_dataframes(py_df, rs_df, "polars_input")
    print(f"  PASS: polars input, rows={len(rs_df)}")


if __name__ == "__main__":
    print("Running correctness tests...")
    print("\n--- All modes ---")
    test_all_modes()
    print("\n--- Small dataset ---")
    test_small_dataset()
    print("\n--- Large brick ---")
    test_large_brick()
    print("\n--- Tiny brick ---")
    test_tiny_brick()
    print("\n--- Polars input ---")
    test_polars_input()
    print("\nAll tests passed!")
