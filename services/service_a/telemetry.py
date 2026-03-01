import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


def setup_tracing(app, service_name: str):
    """
    Tracing strategy:
    - Default: Console exporter (you WILL see spans in docker logs)
    - Later (D05): set OTEL_EXPORTER_OTLP_ENDPOINT to send to collector/jaeger
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    if endpoint:
        # Example endpoint we'll use in D05:
        # http://otel-collector:4318/v1/traces
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Auto-instrument inbound FastAPI + outbound requests
    RequestsInstrumentor().instrument()
    FastAPIInstrumentor.instrument_app(app)
