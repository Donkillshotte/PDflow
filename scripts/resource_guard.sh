#!/usr/bin/env bash
# Exit successfully only when the caller is inside a PDflow-owned transient
# systemd service cgroup.  The environment marker alone is intentionally not
# trusted: it is user-controlled and must not disable the isolation boundary.
set -Eeuo pipefail

[[ "${PD_FLOW_RESOURCE_ACTIVE:-0}" == "1" ]] || exit 1
[[ -r /proc/self/cgroup ]] || exit 1

cgroup_path="$(awk -F: '$1 == "0" { print $3; exit }' /proc/self/cgroup)"
[[ -n "${cgroup_path}" ]] || exit 1
[[ "${cgroup_path}" == */pdflow-*.service || "${cgroup_path}" == */pdflow-*.scope ]] || exit 1
