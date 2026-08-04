from __future__ import annotations

from pathlib import Path

import numpy as np

from thermal_drought.classification import FixedClassification
from thermal_drought.contracts import load_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VARIABLES = REPOSITORY_ROOT / "config" / "variables"


def test_utci_threshold_ownership_matches_scientific_contract() -> None:
    classification = FixedClassification.from_manifest(
        load_json(VARIABLES / "utci_daymax_median.json")
    )

    assert [classification.index(value) for value in [8.999, 9.0, 26.0, 26.001]] == [
        0,
        1,
        1,
        2,
    ]


def test_spei_threshold_ownership_matches_scientific_contract() -> None:
    classification = FixedClassification.from_manifest(load_json(VARIABLES / "spei_3.json"))

    assert [classification.index(value) for value in [-1.501, -1.5, -1.499, -1.0, -0.999]] == [
        0,
        0,
        1,
        1,
        2,
    ]


def test_array_classification_preserves_no_data() -> None:
    classification = FixedClassification.from_manifest(load_json(VARIABLES / "spei_3.json"))
    values = np.asarray([[-2.0, -1.5, -1.25, -1.0, 0.0, np.nan]])

    np.testing.assert_array_equal(
        classification.indices(values),
        [[0, 0, 1, 1, 2, -1]],
    )
    assert classification.label(None) == "No data"
