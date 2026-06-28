mod error;
mod python;
mod renko;

use pyo3::prelude::*;

#[pymodule]
fn _renko_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(python::py_transform, m)?)?;
    Ok(())
}
