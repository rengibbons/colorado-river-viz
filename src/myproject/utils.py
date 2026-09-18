import numpy as np


def hello_world() -> np.ndarray:
    """Return a sample array of 100 random values drawn from a normal distribution."""
    rng = np.random.default_rng(seed=42)
    return rng.standard_normal(size=(100,))
