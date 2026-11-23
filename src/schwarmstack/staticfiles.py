"""Ablage der statischen Dateien im Image: komprimiert und mit Hash im Namen (WhiteNoise)."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


def _ohne_source_maps(patterns):
    return tuple(
        (glob, tuple(p for p in muster if "sourceMappingURL" not in str(p)))
        for glob, muster in patterns
    )


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Verweise auf Source Maps bleiben unangetastet.

    Uppy wird unverändert mitgeliefert und verweist auf `uppy.min.js.map`, das nicht dabei ist;
    ohne diese Ausnahme bricht `collectstatic` ab.
    """

    patterns = _ohne_source_maps(CompressedManifestStaticFilesStorage.patterns)
