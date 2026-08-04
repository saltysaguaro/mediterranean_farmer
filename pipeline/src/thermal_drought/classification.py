"""Variable-neutral fixed classification with explicit threshold ownership."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

BreakAssignment = Literal["lower_class", "upper_class"]
ClassArray = NDArray[np.int8]


@dataclass(frozen=True)
class FixedClassification:
    """A validated ascending fixed classification from a variable manifest."""

    breaks: tuple[float, ...]
    break_assignments: tuple[BreakAssignment, ...]
    labels: tuple[str, ...]
    version: str

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> FixedClassification:
        raw = manifest["classification"]
        breaks = tuple(float(value) for value in raw["breaks"])
        assignments = tuple(str(value) for value in raw["break_assignments"])
        labels = tuple(str(value) for value in raw["labels"])
        if tuple(sorted(breaks)) != breaks or len(set(breaks)) != len(breaks):
            raise ValueError("classification breaks must be strictly ascending")
        if len(assignments) != len(breaks) or len(labels) != len(breaks) + 1:
            raise ValueError("classification breaks, assignments, and labels do not align")
        if any(value not in {"lower_class", "upper_class"} for value in assignments):
            raise ValueError("unsupported classification break assignment")
        typed_assignments = cast(tuple[BreakAssignment, ...], assignments)
        return cls(
            breaks=breaks,
            break_assignments=typed_assignments,
            labels=labels,
            version=str(raw["version"]),
        )

    def index(self, value: float | None) -> int | None:
        """Return the raw-value-order class index, preserving no data as None."""

        if value is None or not math.isfinite(value):
            return None
        for index, threshold in enumerate(self.breaks):
            if value < threshold:
                return index
            if value == threshold and self.break_assignments[index] == "lower_class":
                return index
        return len(self.breaks)

    def label(self, value: float | None) -> str:
        index = self.index(value)
        return "No data" if index is None else self.labels[index]

    def indices(self, values: NDArray[Any]) -> ClassArray:
        """Classify an array, using -1 for non-finite no-data cells."""

        numeric = np.asarray(values, dtype=np.float64)
        finite = np.isfinite(numeric)
        result = np.full(numeric.shape, -1, dtype=np.int8)
        if not finite.any():
            return result
        breaks = np.asarray(self.breaks, dtype=np.float64)
        classified = np.searchsorted(breaks, numeric[finite], side="left").astype(np.int8)
        finite_values = numeric[finite]
        for index, (threshold, assignment) in enumerate(zip(self.breaks, self.break_assignments)):
            if assignment == "upper_class":
                classified[finite_values == threshold] = index + 1
        result[finite] = classified
        return result

    def cache_signature(self) -> dict[str, object]:
        return {
            "breaks": list(self.breaks),
            "break_assignments": list(self.break_assignments),
            "labels": list(self.labels),
            "version": self.version,
        }
