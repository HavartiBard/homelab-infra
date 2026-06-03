from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field


class Output(BaseModel):
    id: str
    unit: str
    direction: Literal["higher_is_better", "lower_is_better", "neutral"]


class LatencyProbe(BaseModel):
    type: Literal["latency"]
    fixture: str
    sample_size: int = 50


class LmEvalProbe(BaseModel):
    type: Literal["lm_eval_harness"]
    task: str
    num_fewshot: int = 0
    batch_size: Union[int, Literal["auto"]] = "auto"


class PrometheusProbe(BaseModel):
    type: Literal["prometheus_window"]
    queries: dict[str, str]   # output_id -> PromQL ($duration placeholder)


Probe = Annotated[
    Union[LatencyProbe, LmEvalProbe, PrometheusProbe],
    Field(discriminator="type"),
]


class Capability(BaseModel):
    id: str
    name: str
    category: str
    description: str
    probe: Probe
    outputs: list[Output]


class CliffTransform(BaseModel):
    type: Literal["cliff_inverse", "cliff_normalize"]
    cliff: float


class WeightedInput(BaseModel):
    weight: float
    transform: CliffTransform | None = None


class Aggregate(BaseModel):
    type: Literal["mean", "weighted"]
    inputs: Union[list[str], dict[str, WeightedInput]]


class Suite(BaseModel):
    id: str
    name: str
    capabilities: list[str]
    aggregates: dict[str, Aggregate]


def load_capability(path: Path) -> Capability:
    data = yaml.safe_load(Path(path).read_text())
    return Capability.model_validate(data["capability"])


def load_suite(path: Path) -> Suite:
    data = yaml.safe_load(Path(path).read_text())
    return Suite.model_validate(data["suite"])


def load_catalog(root: Path) -> dict[str, Capability]:
    """Load every benchmarks/capabilities/*.yml file under `root`."""
    caps_dir = Path(root) / "capabilities"
    return {
        cap.id: cap
        for cap in (load_capability(p) for p in sorted(caps_dir.glob("*.yml")))
    }
