package main

import (
	"context"
	"encoding/json"
	"log"
	"math/rand"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// --- Failure state ---

type FailMode struct {
	Mode      string  `json:"mode"`
	LatencyMs int     `json:"latency_ms"`
	ErrorRate float64 `json:"error_rate"`
}

var (
	mu      sync.RWMutex
	state   = FailMode{Mode: "none", LatencyMs: 50, ErrorRate: 0.0}
)

// --- Prometheus metrics ---

var (
	requestsTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "service_b_requests_total",
		Help: "Total requests to service_b",
	}, []string{"endpoint", "method", "status"})

	requestDuration = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "service_b_request_duration_seconds",
		Help:    "Request duration for service_b",
		Buckets: prometheus.DefBuckets,
	}, []string{"endpoint", "method", "status"})
)

func initMetrics() {
	prometheus.MustRegister(requestsTotal, requestDuration)
}

// --- OTel setup ---

func initTracer(ctx context.Context) func() {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "otel-collector:4317"
	}

	conn, err := grpc.DialContext(ctx, endpoint,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		log.Printf("Warning: could not connect to OTel collector: %v", err)
		return func() {}
	}

	exporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
	if err != nil {
		log.Printf("Warning: could not create trace exporter: %v", err)
		return func() {}
	}

	res := resource.NewWithAttributes(
		semconv.SchemaURL,
		semconv.ServiceName("service_b_go"),
	)

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)

	return func() {
		_ = tp.Shutdown(ctx)
	}
}

// --- Handlers ---

func healthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]bool{"ok": true})
}

func adminState(w http.ResponseWriter, r *http.Request) {
	mu.RLock()
	defer mu.RUnlock()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"state": state})
}

func adminFailmode(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req FailMode
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	mu.Lock()
	if req.Mode != "" {
		state.Mode = req.Mode
	}
	if req.LatencyMs > 0 {
		state.LatencyMs = req.LatencyMs
	}
	if req.ErrorRate >= 0 {
		state.ErrorRate = req.ErrorRate
	}
	current := state
	mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "state": current})
}

func compute(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	status := "success"

	mu.RLock()
	mode := state.Mode
	latencyMs := state.LatencyMs
	errorRate := state.ErrorRate
	mu.RUnlock()

	// Apply latency
	if mode == "latency" || mode == "mixed" {
		time.Sleep(time.Duration(latencyMs) * time.Millisecond)
	} else {
		time.Sleep(time.Duration(latencyMs) * time.Millisecond)
	}

	// Apply error rate
	if (mode == "error" || mode == "mixed") && rand.Float64() < errorRate {
		status = "error"
		requestsTotal.WithLabelValues("/compute", "GET", status).Inc()
		requestDuration.WithLabelValues("/compute", "GET", status).Observe(time.Since(start).Seconds())
		http.Error(w, `{"status":"error","reason":"injected"}`, http.StatusInternalServerError)
		return
	}

	requestsTotal.WithLabelValues("/compute", "GET", status).Inc()
	requestDuration.WithLabelValues("/compute", "GET", status).Observe(time.Since(start).Seconds())

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"result":     "processed by B (go)",
		"mode":       mode,
		"latency_ms": latencyMs,
		"error_rate": errorRate,
	})
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	shutdown := initTracer(ctx)
	cancel()
	defer shutdown()

	initMetrics()

	mux := http.NewServeMux()
	mux.Handle("/healthz", otelhttp.NewHandler(http.HandlerFunc(healthz), "healthz"))
	mux.Handle("/compute", otelhttp.NewHandler(http.HandlerFunc(compute), "compute"))
	mux.Handle("/admin/state", otelhttp.NewHandler(http.HandlerFunc(adminState), "admin_state"))
	mux.Handle("/admin/failmode", otelhttp.NewHandler(http.HandlerFunc(adminFailmode), "admin_failmode"))
	mux.Handle("/metrics", promhttp.Handler())

	port := os.Getenv("PORT")
	if port == "" {
		port = "8002"
	}

	log.Printf("service_b_go listening on :%s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatal(err)
	}
}
