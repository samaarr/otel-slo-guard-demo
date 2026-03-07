# Building a Production-Grade Observability Stack from Scratch (and What I Learned)

*A student's two-week dive into OpenTelemetry, SLOs, and Go — as interview prep for Google Dublin.*

---

I'm a recent grad preparing for Google Dublin SRE/infrastructure interviews. One thing I kept reading was that the best way to demonstrate systems thinking is to build something real, not just study flashcards. So I spent two weeks building `otel-slo-guard-demo`: a failure-injected microservices stack with full observability, SLO enforcement, and burn-rate alerting.

This post is a honest account of what I built, what broke, and what I'd do differently.

---

## What I Was Trying to Learn

Google SRE interviews test whether you understand *reliability as an engineering discipline*, not just as a vague goal. That means:

- How do you define "reliable enough"? (SLOs)
- How do you know when you're burning through reliability too fast? (error budgets + burn-rate alerts)
- How do you instrument code so you can answer those questions? (OpenTelemetry)

I wanted to build something that forced me to answer all three questions with real code, not theory.

---

## The Stack

Eight containers, one compose command:

```
service_a (Python/FastAPI) ─── HTTP ──► service_b (Go/FastAPI)
      │                                       │
      └──── OTLP gRPC ──► otel-collector ◄────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
                 Jaeger               Prometheus
                (traces)              (metrics)
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                         Alertmanager           Grafana
                              │
                              ▼
                       webhook-receiver
```

`service_a` is the gateway — it receives requests and calls `service_b`. `service_b` has a `/admin/failmode` endpoint that lets you inject errors, latency, or both at runtime without restarting anything.

The OTel Collector receives traces over gRPC (port 4317) and exports them to Jaeger. Prometheus scrapes `/metrics` from both services. Alertmanager handles routing. Grafana visualises everything.

---

## SLO Design: The Math Matters

Before writing any instrumentation code, I should have done this. I didn't — I wrote metrics first and designed the SLO after, which meant I had to re-label some counters. Lesson learned.

**The SLO:** 99% success rate on `service_a_requests_total`. That's a 1% error budget.

**What "1% error budget" actually means:**
- Over a 30-day window: ~7.2 hours of acceptable downtime
- Over a 7-day window: ~1.68 hours

**Multi-window burn-rate alerting** is how you catch both fast and slow failures:

| Alert | Windows | Burn Rate | Error Budget Gone In |
|---|---|---|---|
| SLOBurnFast (page) | 5m + 1h | >14.4× | ~2 hours |
| SLOBurnSlow (ticket) | 30m + 6h | >6× | ~5 days |

The logic: if errors are arriving 14.4× faster than your budget allows, your entire monthly budget is gone in under 2 hours. That's a 3am page. If they're arriving at 6×, it'll last days — worth a ticket, not a wake-up call.

In Prometheus recording rules:

```yaml
- record: service_a:burn_rate:5m
  expr: |
    (
      rate(service_a_requests_total{status="error"}[5m])
      /
      rate(service_a_requests_total[5m])
    ) / 0.01
```

Then the alert:

```yaml
- alert: SLOServiceAErrorBudgetBurnFast
  expr: |
    service_a:burn_rate:5m > 14.4
    AND
    service_a:burn_rate:1h > 14.4
  labels:
    severity: page
```

The dual-window requirement (both 5m AND 1h must exceed threshold) prevents noisy alerts from short spikes.

---

## OpenTelemetry: What Actually Tripped Me Up

OTel has a lot of moving parts and the Python docs assume you already know the right setup order. I didn't, so I hit this:

**Spans were silently no-ops.** The instrumentation appeared to work — no errors — but Jaeger showed nothing. The root cause: I was calling `FastAPIInstrumentor.instrument_app(app)` before configuring the `TracerProvider`. OTel falls back to a no-op provider if none is set, and it does so silently.

Correct order:

```python
# 1. Configure TracerProvider
provider = TracerProvider(resource=Resource({SERVICE_NAME: "service_a"}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(...)))
trace.set_tracer_provider(provider)

# 2. Create FastAPI app
app = FastAPI()

# 3. Instrument
FastAPIInstrumentor.instrument_app(app)

# 4. Define routes
@app.get("/work")
async def work(): ...
```

This gap in the docs is what led to my upstream PR to the `opentelemetry-python-contrib` repo — the FastAPI instrumentation README had no usage example at all.

---

## Porting service_b to Go

Halfway through I decided to port `service_b` to Go. Reasons:

1. Google's backend stack is heavily Go
2. I wanted to see how OTel maps across languages
3. Go's static binary made the Docker image ~10MB vs ~200MB for Python slim

The Go OTel setup is more explicit than Python's:

```go
conn, _ := grpc.DialContext(ctx, "otel-collector:4317",
    grpc.WithTransportCredentials(insecure.NewCredentials()),
)
exporter, _ := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
tp := sdktrace.NewTracerProvider(
    sdktrace.WithBatcher(exporter),
    sdktrace.WithResource(resource.NewWithAttributes(
        semconv.SchemaURL,
        semconv.ServiceName("service_b_go"),
    )),
)
otel.SetTracerProvider(tp)
```

More boilerplate, but you can't accidentally forget to set the provider — the compiler will complain if you don't use the variable.

HTTP handlers get automatic span creation via `otelhttp`:

```go
mux.Handle("/compute", otelhttp.NewHandler(http.HandlerFunc(compute), "compute"))
```

Same Prometheus metrics shape as the Python service — same label names, same counter/histogram pattern — so the existing recording rules and alerts worked without changes.

---

## Failure Injection Demo

This is where things get fun to demo. With the stack running:

```bash
# Inject 100% error rate
curl -X POST http://localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode": "error", "error_rate": 1.0}'

# Hammer the endpoint to burn the error budget fast
for i in $(seq 1 100); do
  curl -s http://localhost:8001/work > /dev/null
done

# Watch Prometheus: burn_rate:5m spikes to >>14.4
# Alertmanager fires SLOBurnFast within 2-3 minutes
# Webhook receiver logs the alert payload

# Reset
curl -X POST http://localhost:8002/admin/failmode \
  -d '{"mode": "none"}'
```

Watching the burn rate metric spike in Grafana, then seeing the alert fire in Alertmanager, then seeing the webhook payload — that's when the SLO math stops being abstract.

---

## CI and Repo Hygiene

Since this is a portfolio project, I wanted it to look like something I'd be comfortable running in production. That meant:

- `.github/workflows/ci.yml` — spins up the full stack on push to main, hits `/healthz` on all services, tears it down
- Single `docker-compose.yml` with a single override file (I started with three separate overrides — consolidating them was a good exercise in compose file hygiene)
- `.venv` gitignored and untracked
- `README.md` with quickstart, ports table, failure injection commands, and troubleshooting section

---

## What I'd Do Differently

**1. Design the SLO before writing code.** Knowing your error budget and burn-rate thresholds upfront changes how you label your metrics. I had to relabel counters mid-project.

**2. Start with the collector config.** I spent hours debugging missing spans because the OTel Collector pipeline wasn't wired up correctly. It should have been the first thing I validated.

**3. Write the Go service first.** The Python service was a comfortable starting point, but Go forced me to be more explicit about everything — which built better understanding.

---

## Resources That Actually Helped

- [Google SRE Book — Chapter 5: Eliminating Toil](https://sre.google/sre-book/eliminating-toil/) — the burn-rate math comes from here
- [OpenTelemetry Python contrib](https://github.com/open-telemetry/opentelemetry-python-contrib) — read the source, not just the docs
- [Prometheus Alerting on SLOs](https://prometheus.io/docs/practices/alerting/) — the multi-window rationale

---

## The Repo

Everything is at: **https://github.com/samaarr/otel-slo-guard-demo**

One command to run the full stack:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prometheus.override.yml \
  up -d --build
```

If you're preparing for SRE or infrastructure interviews and want to talk through any of this — I'm learning in public and happy to compare notes.