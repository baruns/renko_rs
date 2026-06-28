use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;

use crate::error::RenkoError;
use crate::renko::Renko;

fn to_py_err(e: RenkoError) -> PyErr {
    pyo3::exceptions::PyValueError::new_err(e.to_string())
}

#[pyfunction]
#[pyo3(name = "transform")]
pub fn py_transform(
    py: Python<'_>,
    df: &Bound<'_, PyAny>,
    brick_size: f64,
) -> PyResult<PyDataFrame> {
    let _ = py;
    let py_df: PyDataFrame = df.extract()?;
    let polars_df: polars::prelude::DataFrame = py_df.0;

    let renko = Renko::new(brick_size).map_err(to_py_err)?;
    let result = renko.transform(&polars_df).map_err(to_py_err)?;

    Ok(PyDataFrame(result))
}
