use thiserror::Error;

#[derive(Error, Debug)]
pub enum RenkoError {
    #[error("brick_size must be > 0, got {0}")]
    InvalidBrickSize(f64),

    #[error("missing required column: '{0}'")]
    MissingColumn(String),

    #[error("column '{0}' has wrong type: expected {1}")]
    WrongColumnType(String, String),

    #[error("input dataframe is empty")]
    EmptyDataFrame,

    #[error("polars error: {0}")]
    Polars(#[from] polars::error::PolarsError),

    #[allow(dead_code)]
    #[error("invalid mode: '{0}'")]
    InvalidMode(String),
}

pub type Result<T> = std::result::Result<T, RenkoError>;
