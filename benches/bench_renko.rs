use criterion::{black_box, criterion_group, criterion_main, Criterion};
use polars::prelude::*;
use rand::Rng;

use renko_rs::renko::Renko;

fn generate_tick_data(n: usize, seed: u64) -> DataFrame {
    let mut rng = rand::thread_rng();
    let mut prices: Vec<f64> = Vec::with_capacity(n);
    let mut datetimes: Vec<i64> = Vec::with_capacity(n);

    let mut price = 100.0_f64;
    let base_ts = 1_577_836_800_000_000_000_i64;

    for i in 0..n {
        price += rng.gen_range(-0.5..0.5);
        prices.push(price);
        datetimes.push(base_ts + (i as i64) * 60_000_000_000);
    }

    df![
        "datetime" => datetimes,
        "close" => prices,
    ]
    .expect("failed to create test dataframe")
    .lazy()
    .with_column(col("datetime").cast(DataType::Datetime(TimeUnit::Nanoseconds, None)))
    .collect()
    .expect("failed to cast datetime")
}

fn bench_renko_100k(c: &mut Criterion) {
    let df = generate_tick_data(100_000, 42);
    let renko = Renko::new(2.0).expect("invalid brick size");

    c.bench_function("renko_100k", |b| {
        b.iter(|| {
            let result = renko.transform(black_box(&df)).expect("transform failed");
            black_box(result);
        })
    });
}

fn bench_renko_1m(c: &mut Criterion) {
    let df = generate_tick_data(1_000_000, 42);
    let renko = Renko::new(2.0).expect("invalid brick size");

    c.bench_function("renko_1m", |b| {
        b.iter(|| {
            let result = renko.transform(black_box(&df)).expect("transform failed");
            black_box(result);
        })
    });
}

fn bench_renko_10m(c: &mut Criterion) {
    let df = generate_tick_data(10_000_000, 42);
    let renko = Renko::new(2.0).expect("invalid brick size");

    c.bench_function("renko_10m", |b| {
        b.iter(|| {
            let result = renko.transform(black_box(&df)).expect("transform failed");
            black_box(result);
        })
    });
}

criterion_group!(benches, bench_renko_100k, bench_renko_1m, bench_renko_10m);
criterion_main!(benches);
