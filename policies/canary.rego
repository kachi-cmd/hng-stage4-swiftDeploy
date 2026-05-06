package policy.canary

# This policy answers one question:
# "Is the canary deployment healthy enough to promote to stable?"
#
# input fields expected:
#   input.error_rate     - fraction of requests returning 5xx (e.g. 0.02 = 2%)
#   input.p99_latency_ms - 99th percentile latency in milliseconds
#   input.sample_size    - number of requests measured (for confidence)
#
# data fields loaded from canary_data.json:
#   data.thresholds.max_error_rate
#   data.thresholds.max_p99_latency_ms

default allow = false

allow {
    count(deny) == 0
}

# Deny if error rate exceeds threshold
deny[msg] {
    input.error_rate > data.thresholds.max_error_rate
    msg := sprintf(
        "Error rate %.2f%% exceeds maximum %.2f%%",
        [input.error_rate * 100, data.thresholds.max_error_rate * 100]
    )
}

# Deny if P99 latency exceeds threshold
deny[msg] {
    input.p99_latency_ms > data.thresholds.max_p99_latency_ms
    msg := sprintf(
        "P99 latency %dms exceeds maximum %dms",
        [input.p99_latency_ms, data.thresholds.max_p99_latency_ms]
    )
}

# Warn if sample size is too small to be meaningful
# Still allow but surface the concern
deny[msg] {
    input.sample_size < 10
    msg := sprintf(
        "Sample size %d is too small for reliable measurement (need >= 10)",
        [input.sample_size]
    )
}
