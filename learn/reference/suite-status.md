# Current suite status

Status is evaluated when a command runs. The current JSON report is the source
of the actual result.

| Status | Meaning |
|---|---|
| `READY` | current tool and inputs completed validation |
| `GAP` | optional capability or input is unavailable |
| `FAIL` | current invocation failed |
| `REFUSED` | request violated a contract or safety rule |
| `incomplete` | required evidence is missing |

```bash
python3 learn/scripts/test_signoff_honesty.py
python3 learn/scripts/test_lab_physics.py
./scripts/test_all_phases.sh
```

Inspect the report path printed by the command. This page is a vocabulary,
not stored result data.
