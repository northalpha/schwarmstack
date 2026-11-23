"""Ablage der statischen Dateien im Image: komprimiert und mit Hash im Namen (WhiteNoise)."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


def _ohne_source_maps(patterns):
    return tuple(
        (
            glob,
            tuple(
                ersetzung for ersetzung in ersetzungen if "sourceMappingURL" not in str(ersetzung)
            ),
        )
        for glob, ersetzungen in patterns
    )


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Verweise auf Source Maps bleiben unangetastet.

    Uppy wird unverändert mitgeliefert und verweist auf `uppy.min.js.map`, das nicht dabei ist;
    ohne diese Ausnahme bricht `collectstatic` ab.
    """

    patterns = _ohne_source_maps(CompressedManifestStaticFilesStorage.patterns)
