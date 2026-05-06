package policy.infra

# This policy answers one question:
# "Is the host infrastructure healthy enough to deploy?"
#
# input fields expected:
#   input.disk_free_gb   - free disk space in GB
#   input.cpu_load       - 1-minute load average
#   input.mem_free_gb    - free memory in GB
#
# data fields loaded from infra_data.json:
#   data.thresholds.min_disk_gb
#   data.thresholds.max_cpu_load
#   data.thresholds.min_mem_gb

default allow = false

# Allow only when no deny rules fire
allow {
    count(deny) == 0
}

# Deny if disk free is below minimum
deny[msg] {
    input.disk_free_gb < data.thresholds.min_disk_gb
    msg := sprintf(
        "Disk free %.1fGB is below minimum %.1fGB",
        [input.disk_free_gb, data.thresholds.min_disk_gb]
    )
}

# Deny if CPU load average is too high
deny[msg] {
    input.cpu_load > data.thresholds.max_cpu_load
    msg := sprintf(
        "CPU load %.2f exceeds maximum %.2f",
        [input.cpu_load, data.thresholds.max_cpu_load]
    )
}

# Deny if free memory is too low
deny[msg] {
    input.mem_free_gb < data.thresholds.min_mem_gb
    msg := sprintf(
        "Free memory %.1fGB is below minimum %.1fGB",
        [input.mem_free_gb, data.thresholds.min_mem_gb]
    )
}
