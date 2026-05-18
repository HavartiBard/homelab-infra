from __future__ import annotations

import json
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from .store import RunRecord


_INITIALIZED = False


def init_tracing(*, otlp_endpoint: str, service_name: str = "llm-bench") -> None:
    """Initialize OTel tracing with OTLP gRPC exporter targeting Phoenix.

    Safe to call multiple times — only configures the global provider once.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _INITIALIZED = True


def log_run_to_phoenix(record: RunRecord) -> None:
    """Emit one OTel span representing this benchmark run."""
    tracer = trace.get_tracer("bench")
    with tracer.start_as_current_span("benchmark_run") as span:
        for k, v in record.model_dump().items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                span.set_attribute(f"bench.{k}", v)
            else:
                span.set_attribute(f"bench.{k}", json.dumps(v, default=str))
