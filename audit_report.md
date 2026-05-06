# swiftdeploy Audit Report

Generated: 2026-05-06T16:26:09Z
Period: `2026-05-06T16:23:42Z` → `2026-05-06T16:23:52Z`
Total entries: 3

## Summary

| Metric | Value |
|--------|-------|
| Total scrapes | 3 |
| Time in stable | 3 scrapes |
| Time in canary | 0 scrapes |
| Avg P99 latency | 5.0ms |
| Max P99 latency | 5.0ms |
| Avg error rate | 0.000% |
| Total violations | 3 |

## Timeline

| Timestamp | Event | Mode | Detail |
|-----------|-------|------|--------|
| `2026-05-06T16:23:42Z` | Stack started | stable | Initial state — mode=stable |

## Policy Violations

| Timestamp | Mode | Violation | P99 (ms) | Error Rate |
|-----------|------|-----------|----------|------------|
| `2026-05-06T16:23:42Z` | stable | [policy/infra] Disk free 3.5GB is below minimum 10.0GB | 5 | 0.000% |
| `2026-05-06T16:23:47Z` | stable | [policy/infra] Disk free 3.5GB is below minimum 10.0GB | 5 | 0.000% |
| `2026-05-06T16:23:52Z` | stable | [policy/infra] Disk free 3.5GB is below minimum 10.0GB | 5 | 0.000% |

## Recent Metrics (last 5 scrapes)

| Timestamp | Mode | Req/s | P99 (ms) | Error Rate | Chaos |
|-----------|------|-------|----------|------------|-------|
| `2026-05-06T16:23:42Z` | stable | 0.00 | 5 | 0.000% | none |
| `2026-05-06T16:23:47Z` | stable | 0.00 | 5 | 0.000% | none |
| `2026-05-06T16:23:52Z` | stable | 0.20 | 5 | 0.000% | none |
