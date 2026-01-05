from nado_protocol.utils.math import to_x18


def test_to_x18():
    assert to_x18(10.15) == 10150000000000000000
    assert to_x18(10) == 10000000000000000000
    assert to_x18(2000.150) == 2000150000000000000000
