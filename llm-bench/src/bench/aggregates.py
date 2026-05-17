from __future__ import annotations

from typing import Mapping

from .catalog import Suite, CliffTransform


def cliff_inverse(value: float, cliff: float) -> float:
    """Lower-is-better -> 0..1. score=1.0 at x=0; 0.0 at x>=cliff."""
    return max(0.0, min(1.0, 1.0 - value / cliff))


def cliff_normalize(value: float, cliff: float) -> float:
    """Higher-is-better -> 0..1. score=0.0 at x=0; 1.0 at x>=cliff."""
    return max(0.0, min(1.0, value / cliff))


def _apply_transform(value: float, transform: CliffTransform | None) -> float:
    if transform is None:
        return value
    if transform.type == "cliff_inverse":
        return cliff_inverse(value, transform.cliff)
    if transform.type == "cliff_normalize":
        return cliff_normalize(value, transform.cliff)
    raise ValueError(f"Unknown transform: {transform.type}")


def compute_aggregates(
    scores: Mapping[str, float | None],
    suite: Suite,
) -> dict[str, float | None]:
    """Compute every aggregate defined in `suite` from the raw `scores`.

    Returns None for any aggregate that has at least one null input.
    """
    out: dict[str, float | None] = {}
    for name, agg in suite.aggregates.items():
        if agg.type == "mean":
            inputs = agg.inputs   # list[str]
            values = [scores.get(i) for i in inputs]
            if any(v is None for v in values):
                out[name] = None
            else:
                out[name] = sum(values) / len(values)   # type: ignore[arg-type]
        elif agg.type == "weighted":
            inputs = agg.inputs   # dict[str, WeightedInput]
            transformed: list[tuple[float, float]] = []
            null_seen = False
            for input_id, spec in inputs.items():
                v = scores.get(input_id)
                if v is None:
                    null_seen = True
                    break
                transformed.append((spec.weight, _apply_transform(v, spec.transform)))
            if null_seen:
                out[name] = None
            else:
                total_weight = sum(w for w, _ in transformed)
                out[name] = sum(w * s for w, s in transformed) / total_weight
        else:
            raise ValueError(f"Unknown aggregate type: {agg.type}")
    return out
