use polars::prelude::*;

use crate::error::{RenkoError, Result};

pub struct Renko {
    pub brick_size: f64,
}

impl Renko {
    pub fn new(brick_size: f64) -> Result<Self> {
        if brick_size <= 0.0 {
            return Err(RenkoError::InvalidBrickSize(brick_size));
        }
        Ok(Self { brick_size })
    }

    pub fn transform(&self, df: &DataFrame) -> Result<DataFrame> {
        if df.height() == 0 {
            return Err(RenkoError::EmptyDataFrame);
        }

        let datetime_series = df
            .column("datetime")
            .map_err(|_| RenkoError::MissingColumn("datetime".into()))?
            .cast(&DataType::Datetime(TimeUnit::Nanoseconds, None))?
            .rechunk();
        let close_series = df
            .column("close")
            .map_err(|_| RenkoError::MissingColumn("close".into()))?
            .cast(&DataType::Float64)?
            .rechunk();

        let datetime_ca = datetime_series.datetime().map_err(|_| {
            RenkoError::WrongColumnType("datetime".into(), "Datetime(ns)".into())
        })?;
        let close_ca = close_series
            .f64()
            .map_err(|_| RenkoError::WrongColumnType("close".into(), "Float64".into()))?;

        let tick_len = close_ca.len();
        if tick_len < 2 {
            return Ok(DataFrame::empty());
        }

        let dt = datetime_ca
            .cont_slice()
            .map_err(|_| RenkoError::WrongColumnType("datetime".into(), "contiguous i64".into()))?;
        let prices = close_ca
            .cont_slice()
            .map_err(|_| RenkoError::WrongColumnType("close".into(), "contiguous f64".into()))?;

        let bricks = self.compute_bricks(dt, prices, self.brick_size);
        self.build_dataframe(bricks)
    }

    fn compute_bricks(&self, dt: &[i64], prices: &[f64], brick_size: f64) -> BrickOutput {
        let tick_len = prices.len();
        let est = (tick_len / 4).max(64);

        let mut datetime_arr = Vec::with_capacity(est);
        let mut open_arr = Vec::with_capacity(est);
        let mut high_arr = Vec::with_capacity(est);
        let mut low_arr = Vec::with_capacity(est);
        let mut close_arr = Vec::with_capacity(est);
        let mut vol_arr = Vec::with_capacity(est);
        let mut dir_arr = Vec::with_capacity(est);
        let mut rev_arr = Vec::with_capacity(est);
        let mut t_open_arr = Vec::with_capacity(est);
        let mut t_close_arr = Vec::with_capacity(est);
        let mut n_high_arr = Vec::with_capacity(est);
        let mut n_low_arr = Vec::with_capacity(est);
        let mut n_gap_arr = Vec::with_capacity(est);
        let mut r_n_gap_arr = Vec::with_capacity(est);
        let mut r_f_n_gap_arr = Vec::with_capacity(est);
        let mut r_high_arr = Vec::with_capacity(est);
        let mut r_low_arr = Vec::with_capacity(est);
        let mut f_high_arr = Vec::with_capacity(est);
        let mut f_low_arr = Vec::with_capacity(est);

        let initial_price = (prices[0] / brick_size).floor() * brick_size;
        let mut wick_min_i = initial_price;
        let mut wick_max_i = initial_price;
        let mut volume_i: i64 = 1;
        let mut tick_open_i: i64 = 1;
        let mut tick_close_i: i64;
        let mut last_renko = initial_price;
        let mut last_direction: i64 = 0;
        let invariant_brick = 1.0 / brick_size;

        for i in 1..tick_len {
            let price = prices[i];

            if price < wick_min_i {
                wick_min_i = price;
            }
            if price > wick_max_i {
                wick_max_i = price;
            }
            volume_i += 1;
            tick_close_i = i as i64;

            let current_n_bricks = (price - last_renko) * invariant_brick;
            if current_n_bricks.abs() < 1.0 {
                continue;
            }

            let is_up = current_n_bricks > 0.0;
            let current_direction: i64 = if is_up { 1 } else { -1 };
            let is_same_direction = current_direction * last_direction >= 0;
            let mut total_same_bricks: f64 = if is_same_direction {
                current_n_bricks
            } else {
                0.0
            };

            if !is_same_direction && current_n_bricks.abs() >= 2.0 {
                let renko_price = last_renko + (current_direction as f64 * 2.0 * brick_size);
                let open_price = if is_up {
                    renko_price - brick_size
                } else {
                    renko_price + brick_size
                };
                let wick = if is_up { wick_min_i } else { wick_max_i };

                datetime_arr.push(dt[i]);
                open_arr.push(open_price);
                high_arr.push(if is_up { renko_price } else { wick });
                low_arr.push(if is_up { wick } else { renko_price });
                close_arr.push(renko_price);
                vol_arr.push(volume_i);
                dir_arr.push(current_direction);
                t_open_arr.push(tick_open_i);
                t_close_arr.push(tick_close_i);
                rev_arr.push(1);

                let n_h = if is_up { renko_price } else { open_price };
                let n_l = if is_up { open_price } else { renko_price };
                n_high_arr.push(n_h);
                n_low_arr.push(n_l);

                let ng_val = if (is_up && open_price > wick) || (!is_up && open_price < wick) {
                    wick
                } else {
                    open_price
                };
                n_gap_arr.push(ng_val);
                r_high_arr.push(wick);
                r_low_arr.push(wick);
                r_n_gap_arr.push(ng_val);

                let f_wick = last_renko;
                f_high_arr.push(if !is_up { f_wick } else { n_h });
                f_low_arr.push(if is_up { f_wick } else { n_l });
                r_f_n_gap_arr.push(f_wick);

                wick_min_i = open_price;
                wick_max_i = open_price;
                tick_open_i = i as i64;
                tick_close_i = i as i64;
                volume_i = 1;
                last_direction = current_direction;
                last_renko = renko_price;
                total_same_bricks = current_n_bricks - 2.0 * current_direction as f64;
            }

            let same_bricks_count = total_same_bricks.abs() as usize;

            if same_bricks_count == 0 && current_n_bricks.abs() < 2.0 {
                continue;
            }

            if same_bricks_count > 0 {
                let renko_price = last_renko + (current_direction as f64 * brick_size);
                let open_price = if is_up {
                    renko_price - brick_size
                } else {
                    renko_price + brick_size
                };
                let wick = if is_up { wick_min_i } else { wick_max_i };

                datetime_arr.push(dt[i]);
                open_arr.push(open_price);
                high_arr.push(if is_up { renko_price } else { wick });
                low_arr.push(if is_up { wick } else { renko_price });
                close_arr.push(renko_price);
                vol_arr.push(volume_i);
                dir_arr.push(current_direction);
                t_open_arr.push(tick_open_i);
                t_close_arr.push(tick_close_i);
                rev_arr.push(0);

                let n_h = if is_up { renko_price } else { open_price };
                let n_l = if is_up { open_price } else { renko_price };
                n_high_arr.push(n_h);
                n_low_arr.push(n_l);

                let ng_val = if (is_up && open_price > wick) || (!is_up && open_price < wick) {
                    wick
                } else {
                    open_price
                };
                n_gap_arr.push(ng_val);
                r_high_arr.push(n_h);
                r_low_arr.push(n_l);
                r_n_gap_arr.push(open_price);

                let _f_wick = last_renko;
                f_high_arr.push(n_h);
                f_low_arr.push(n_l);
                r_f_n_gap_arr.push(open_price);

                wick_min_i = renko_price;
                wick_max_i = renko_price;
                tick_open_i = i as i64;
                tick_close_i = i as i64;
                volume_i = 1;
                last_direction = current_direction;
                last_renko = renko_price;

                let remaining = same_bricks_count - 1;
                if remaining > 0 {
                    let dir_f = current_direction as f64;
                    let base_close = last_renko;
                    let base_open = if is_up {
                        base_close - brick_size
                    } else {
                        base_close + brick_size
                    };

                    for j in 0..remaining {
                        let k = (j + 1) as f64;
                        let c = base_close + dir_f * brick_size * k;
                        let o = base_open + dir_f * brick_size * k;

                        datetime_arr.push(dt[i]);
                        open_arr.push(o);
                        close_arr.push(c);
                        vol_arr.push(volume_i);
                        dir_arr.push(current_direction);
                        t_open_arr.push(tick_open_i);
                        t_close_arr.push(tick_close_i);
                        rev_arr.push(0);

                        if is_up {
                            high_arr.push(c);
                            low_arr.push(o);
                            n_high_arr.push(c);
                            n_low_arr.push(o);
                        } else {
                            high_arr.push(o);
                            low_arr.push(c);
                            n_high_arr.push(o);
                            n_low_arr.push(c);
                        }

                        n_gap_arr.push(o);
                        r_high_arr.push(if is_up { c } else { o });
                        r_low_arr.push(if is_up { o } else { c });
                        r_n_gap_arr.push(o);
                        f_high_arr.push(if is_up { c } else { o });
                        f_low_arr.push(if is_up { o } else { c });
                        r_f_n_gap_arr.push(o);
                    }

                    let last_close = base_close + dir_f * brick_size * remaining as f64;
                    wick_min_i = last_close;
                    wick_max_i = last_close;
                    last_renko = last_close;
                }
            }
        }

        BrickOutput {
            datetime: datetime_arr,
            open: open_arr,
            high: high_arr,
            low: low_arr,
            close: close_arr,
            volume: vol_arr,
            direction: dir_arr,
            is_reversal: rev_arr,
            tick_index_open: t_open_arr,
            tick_index_close: t_close_arr,
            normal_high: n_high_arr,
            normal_low: n_low_arr,
            nongap_open: n_gap_arr,
            reverse_nongap_open: r_n_gap_arr,
            reverse_fake_nongap_open: r_f_n_gap_arr,
            reverse_high: r_high_arr,
            reverse_low: r_low_arr,
            fake_high: f_high_arr,
            fake_low: f_low_arr,
        }
    }

    fn build_dataframe(&self, b: BrickOutput) -> Result<DataFrame> {
        if b.datetime.is_empty() {
            return Ok(DataFrame::empty());
        }

        let first_dt = b.datetime[0];
        let keep_start = b.datetime.iter().position(|&d| d != first_dt).unwrap_or(b.datetime.len());

        if keep_start == 0 {
            return Ok(DataFrame::empty());
        }

        let n = b.datetime.len();
        let s = keep_start;

        let df = df![
            "datetime" => b.datetime[s..n].to_vec(),
            "open" => b.open[s..n].to_vec(),
            "high" => b.high[s..n].to_vec(),
            "low" => b.low[s..n].to_vec(),
            "close" => b.close[s..n].to_vec(),
            "volume" => b.volume[s..n].to_vec(),
            "direction" => b.direction[s..n].to_vec(),
            "is_reversal" => b.is_reversal[s..n].to_vec(),
            "tick_index_open" => b.tick_index_open[s..n].to_vec(),
            "tick_index_close" => b.tick_index_close[s..n].to_vec(),
            "normal_high" => b.normal_high[s..n].to_vec(),
            "normal_low" => b.normal_low[s..n].to_vec(),
            "nongap_open" => b.nongap_open[s..n].to_vec(),
            "reverse_nongap_open" => b.reverse_nongap_open[s..n].to_vec(),
            "reverse_fake_nongap_open" => b.reverse_fake_nongap_open[s..n].to_vec(),
            "reverse_high" => b.reverse_high[s..n].to_vec(),
            "reverse_low" => b.reverse_low[s..n].to_vec(),
            "fake_high" => b.fake_high[s..n].to_vec(),
            "fake_low" => b.fake_low[s..n].to_vec(),
        ]?;

        Ok(df)
    }
}

pub struct BrickOutput {
    pub datetime: Vec<i64>,
    pub open: Vec<f64>,
    pub high: Vec<f64>,
    pub low: Vec<f64>,
    pub close: Vec<f64>,
    pub volume: Vec<i64>,
    pub direction: Vec<i64>,
    pub is_reversal: Vec<i64>,
    pub tick_index_open: Vec<i64>,
    pub tick_index_close: Vec<i64>,
    pub normal_high: Vec<f64>,
    pub normal_low: Vec<f64>,
    pub nongap_open: Vec<f64>,
    pub reverse_nongap_open: Vec<f64>,
    pub reverse_fake_nongap_open: Vec<f64>,
    pub reverse_high: Vec<f64>,
    pub reverse_low: Vec<f64>,
    pub fake_high: Vec<f64>,
    pub fake_low: Vec<f64>,
}
