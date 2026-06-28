from typing import Union
import pandas as pd
import polars as pl


class Renko:
    def __init__(self, df: Union[pd.DataFrame, pl.DataFrame], brick_size: float) -> None: ...
    def renko_df(self, mode: str = "wicks", utils_columns: bool = True) -> pl.DataFrame: ...
