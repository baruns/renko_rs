from __future__ import annotations

import polars as pl

from ._renko_rs import transform as _transform

_VALID_MODES = [
    "normal", "wicks", "nongap",
    "reverse-wicks", "reverse-nongap",
    "fake-r-wicks", "fake-r-nongap",
]


class Renko:
    def __init__(self, df, brick_size: float):
        if brick_size is None or brick_size <= 0:
            raise ValueError("brick_size cannot be None or <= 0")

        self._brick_size = brick_size

        if not isinstance(df, pl.DataFrame):
            import pandas as pd

            if isinstance(df, pd.DataFrame):
                if "datetime" not in df.columns:
                    df = df.copy()
                    df["datetime"] = df.index

                if "datetime" not in df.columns:
                    raise ValueError("Column 'datetime' doesn't exist and index is not usable")
                if "close" not in df.columns:
                    raise ValueError("Column 'close' doesn't exist!")

                df = df[["datetime", "close"]].reset_index(drop=True)
                df = pl.from_pandas(df)
            else:
                raise TypeError(f"Expected pandas or polars DataFrame, got {type(df)}")
        else:
            if "datetime" not in df.columns:
                raise ValueError("Column 'datetime' doesn't exist!")
            if "close" not in df.columns:
                raise ValueError("Column 'close' doesn't exist!")

        self._df_renko: pl.DataFrame = _transform(df, brick_size)

    def renko_df(self, mode: str = "wicks", utils_columns: bool = True) -> pl.DataFrame:
        if mode not in _VALID_MODES:
            raise ValueError(f"Only {_VALID_MODES} options are valid.")

        df = self._df_renko.clone()
        df = df.drop("datetime")

        nongap_columns = ["nongap_open"]
        normal_columns = ["normal_high", "normal_low"]
        reverse_columns = ["reverse_high", "reverse_low"]
        fake_r_columns = ["fake_high", "fake_low"]
        nongap_reverse_columns = ["reverse_nongap_open", "reverse_fake_nongap_open"]
        remaining_columns = ["direction", "is_reversal", "tick_index_open", "tick_index_close"]

        highlow_columns = reverse_columns + fake_r_columns + nongap_reverse_columns
        nn_columns = nongap_columns + normal_columns

        drop_map = {
            "normal": highlow_columns + nongap_columns,
            "wicks": highlow_columns + nn_columns,
            "nongap": highlow_columns + normal_columns,
            "reverse-wicks": fake_r_columns + nn_columns,
            "reverse-nongap": fake_r_columns + nn_columns + [nongap_reverse_columns[1]],
            "fake-r-wicks": reverse_columns + nn_columns,
            "fake-r-nongap": reverse_columns + nn_columns + [nongap_reverse_columns[0]],
        }
        df = df.drop(drop_map[mode])

        if not utils_columns:
            df = df.drop(remaining_columns)

        if mode == "wicks":
            return df

        to_replace = ["high", "low"] if mode != "nongap" else ["open"]
        if mode in ("reverse-nongap", "fake-r-nongap"):
            to_replace = to_replace + ["open"]
        df = df.drop(to_replace)

        mode_columns = {
            "normal": normal_columns,
            "nongap": nongap_columns,
            "reverse-wicks": reverse_columns,
            "reverse-nongap": reverse_columns + [nongap_reverse_columns[0]],
            "fake-r-wicks": fake_r_columns,
            "fake-r-nongap": fake_r_columns + [nongap_reverse_columns[1]],
        }
        keys = mode_columns[mode]
        values = list(to_replace)
        if mode in ("reverse-nongap", "fake-r-nongap"):
            values = values + ["open"]

        rename_map = dict(zip(keys, values))
        df = df.rename(rename_map)

        order = ["open", "high", "low", "close", "volume"]
        if utils_columns:
            order = order + remaining_columns

        return df.select(order)
