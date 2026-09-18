import numpy as np

from myproject.utils import hello_world


def test_hello_world_shape() -> None:
    data = hello_world()
    assert data.shape == (100,)
    assert isinstance(data, np.ndarray)
