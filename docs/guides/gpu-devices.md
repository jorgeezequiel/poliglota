# GPU Device Selection and Translation Engine Behavior

This guide documents how Poliglota resolves CPU/GPU execution for the local translation workflow.

## Overview

The runtime supports a permissive `auto` path and strict explicit device requests. The project intentionally avoids silent misreporting: if the user requests a specific device, the code validates that device and fails clearly when it is missing.

## Device selection contract

### Auto mode (default)

**Command:** `poliglota translate --device auto "text"` or `poliglota translate "text"`

**Behavior:**
- tries CUDA first
- falls back to MPS when CUDA is unavailable
- falls back to CPU as the last option
- does not raise an error for the `auto` path

**When to use:** development environments where compatibility is more important than guaranteeing a GPU.

### Explicit device requests

**Commands:**
- `poliglota translate --device cpu "text"` — CPU only
- `poliglota translate --device cuda "text"` — CUDA required
- `poliglota translate --device mps "text"` — MPS required on Apple Silicon

**Behavior:**
- `cpu`: always resolves to CPU; no GPU fallback
- `cuda`: requires CUDA; raises a clear error if unavailable
- `mps`: requires MPS; raises a clear error if unavailable
- invalid device names also fail clearly

**When to use:** explicit environment validation, benchmarking, or production workflows where the requested backend must exist.

### GPU alias

**Command:** `poliglota translate --device gpu "text"`

**Behavior:**
- the low-level helper in `poliglota/gpu.py` accepts `gpu` and may prefer CUDA, then MPS, then CPU when permissive detection is used
- the CLI resolves explicit device values in strict mode, so an unavailable explicit GPU request fails with a clear error instead of silently using another backend

This distinction matters: the helper is permissive by design, but the CLI is stricter about user-requested device guarantees.

## Device detection logic

The helper in `poliglota/gpu.py` implements the runtime decision path:

```python
def detect_device(preferred: str = "auto", strict: bool = False) -> str:
    ...
```

The lower-level device selection order is:

- `auto`: CUDA > MPS > CPU
- `gpu`: prefer CUDA, then MPS, then CPU in permissive mode
- `cpu`: forced CPU
- `cuda`: explicit CUDA request, strict failure when unavailable
- `mps`: explicit MPS request, strict failure when unavailable

The CLI layer resolves explicit requests with strict validation, while `auto` remains permissive. That is the behavior enforced in `poliglota/cli.py` via `_resolve_device_name()`.

## Practical examples

### Flexible local development

```bash
poliglota translate --source pt_BR --target en_US "Olá, mundo!"
# or explicitly:
poliglota translate --source pt_BR --target en_US --device auto "Olá, mundo!"
```

Expected behavior: select CUDA if available, otherwise MPS, otherwise CPU.

### Fail-fast GPU validation

```bash
poliglota translate --source pt_BR --target en_US --device cuda "Olá, mundo!"
```

Expected behavior: if CUDA is not available, the command fails clearly instead of silently switching to CPU.

### macOS Metal path

```bash
poliglota translate --source pt_BR --target en_US --device mps "Olá, mundo!"
```

Expected behavior: uses MPS only when available; otherwise the command errors.

### CPU-only mode

```bash
poliglota translate --source pt_BR --target en_US --device cpu "Olá, mundo!"
```

Expected behavior: run on CPU only. No GPU fallback.

## Offline and environment requirements

The project expects local model assets to be prepared in advance. The offline workflow is intentionally explicit:

```bash
export HF_HUB_OFFLINE=1
```

When this variable is enabled, the code checks for a local cache and fails clearly when the required model is not already available. The project does not promise a fully offline environment without pre-cached resources.

## Troubleshooting

### CUDA requested but unavailable

**Cause:** explicit `--device cuda` or `POLIGLOTA_DEVICE=cuda` was requested but CUDA is absent.

**Solution:**
- verify the NVIDIA GPU is present
- confirm PyTorch CUDA support in the current environment
- use `--device auto` or `--device cpu` for a non-failing fallback path

### MPS requested but unavailable

**Cause:** explicit `--device mps` was requested on a non-Apple or unsupported environment.

**Solution:**
- use `--device auto` for a permissive selection flow
- use `--device cpu` for CPU-only execution

### Unexpected device behavior

**Cause:** the project intentionally distinguishes between requested device, detected device, and actual device usage.

**Solution:**
- inspect logs for the exact selection path
- prefer `--device auto` for flexible development
- prefer strict devices when you need an unambiguous environment contract

## Limitations

- real GPU performance is hardware- and model-specific
- the repository does not guarantee a final benchmark suite or universal speed profile
- CI and development boxes may not reproduce the exact device conditions of a user machine
- the offline path requires the model to be present in the local cache or configured directory

See also:
- `docs/LIMITATIONS.md`
- `docs/guides/translation-engine.md`
- `poliglota/gpu.py`
- `poliglota/cli.py`
