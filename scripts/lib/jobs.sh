#!/usr/bin/env bash
# Shared compile parallelism for Cloud Agent / local builds.
# Default 2: -j$(nproc) on a Cloud VM can thrash RAM during Yosys/OpenSTA.
# Override with EDA_JOBS=N.
if [[ -z "${EDA_JOBS:-}" ]]; then
  EDA_JOBS=2
fi
if ! [[ "${EDA_JOBS}" =~ ^[0-9]+$ ]] || [[ "${EDA_JOBS}" -lt 1 ]]; then
  EDA_JOBS=2
fi
if [[ "${EDA_JOBS}" -gt 8 ]]; then
  EDA_JOBS=8
fi
export EDA_JOBS
