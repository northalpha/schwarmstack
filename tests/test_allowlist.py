import pytest

from uploads.allowlist import allowed_format


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("m31.fits", "fits"),
        ("M31.FIT", "fits"),
        ("a.fts", "fits"),
        ("x.xisf", "xisf"),
        ("X.XISF", "xisf"),
        ("a.fits.zip", None),
        ("a.zip", None),
        ("a.jpg", None),
        ("a.fits.exe", None),
        ("fits", None),
        ("", None),
    ],
)
def test_endungen(name, expected):
    assert allowed_format(name) == expected
