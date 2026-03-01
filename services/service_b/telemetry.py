import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


def setup_tracing(app, service_name: str):
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))

    RequestsInstrumentor().instrument()
    FastAPIInstrumentor.instrument_app(app)
