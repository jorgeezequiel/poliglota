# Poliglota Limitations and Support Matrix

This document provides a comprehensive overview of Poliglota's current capabilities, limitations, and support status across formats, operations, translation engines, and device configurations.

## Supported Formats Matrix

| Format | Discovery | Validation | Synchronization | Translation | Status | Notes |
|--------|-----------|-----------|-----------------|-------------|--------|-------|
| **ARB** | ✅ Implemented | ✅ Implemented | ✅ Implemented | ✅ Supported | Reference implementation | Full support: placeholder checks, locale inference, round-trip I/O. Pre-1.0, not a production-stability guarantee |
| **YAML** | ✅ Confirmed | ⚠️ Via adapter contract | ⚠️ Via generic operations | ✅ Supported | Experimental | Format adapter exists; validation coverage may vary |
| **JSON** | ✅ Confirmed | ⚠️ Via adapter contract | ⚠️ Via generic operations | ✅ Supported | Experimental | Generic operations; locale files supported |
| **XML** | ✅ Confirmed | ⚠️ Via adapter contract | ⚠️ Via generic operations | ✅ Supported | Experimental | Adapter exists in runtime registry |
| **CSV** | ❌ Not implemented | — | — | — | Planned | No adapter implementation |
| **Gettext** | ❌ Not implemented | — | — | — | Planned | No adapter implementation |
| **Other formats** | ❌ Not implemented | — | — | — | Planned | Requires explicit `FormatAdapter` implementation |

**Key:**
- ✅ Implemented: feature is working and tested
- ⚠️ Partial: feature exists via generic layer; may require format-specific tuning
- ❌ Not implemented: requires new code or adapter
- Reference implementation: most complete adapter, exercised by the wider test suite
- Experimental: implemented but maturity may vary; local testing recommended

## Translation Engines and Device Support

### Engines

| Engine | Default | Status | Model Source | Offline | Notes |
|--------|---------|--------|--------------|---------|-------|
| **Marian** | ✅ Yes | Implemented in code | Local or cached Marian-compatible model | ✅ After cache prep | Local engine path; use requires compatible environment and model assets |
| **PyTorch** | ❌ No | Alternative path | Hugging Face / Custom | ✅ After cache prep | Flexible model selection; requires ML stack |

### Device Selection

| Mode | Platform | Auto Fallback | Strict Failure | Use Case | Status |
|------|----------|---------------|----------------|----------|--------|
| `--device auto` | All | ✅ CUDA → MPS → CPU | ❌ Never fails | Development, flexible inference | Implemented in code |
| `--device cuda` | Windows, Linux | ❌ None | ✅ Fails if CUDA unavailable | Production GPU-required workflows | Implemented in code |
| `--device mps` | macOS | ❌ None | ✅ Fails if MPS unavailable | Apple Silicon GPU inference | Implemented in code |
| `--device cpu` | All | ❌ None | ❌ Never fails | CPU-only, low-resource environments | Implemented in code |
| `--device gpu` | All | ✅ Alias for auto (same as `--device auto`) | ❌ Never fails | Shorthand for GPU auto-selection; tries CUDA → MPS → CPU | Implemented in code |

### GPU Support Status

| GPU Type | Platform | Status | Compute Capability | VRAM (observed) | Validation |
|----------|----------|--------|-------------------|----------------|------------|
| **NVIDIA CUDA** | Windows, Linux | ✅ Supported when available | Depends on installed PyTorch build | Variable | Requires local validation in the target environment |
| **Apple MPS** | macOS 12.3+ | ⚠️ Experimental | N/A | Variable | Not guaranteed across all Apple Silicon environments |
| **AMD ROCm** | Linux | ⚠️ Experimental or unsupported depending on stack | N/A | Variable | Not validated in this repository |
| **CPU** | All | ✅ Required fallback | N/A | N/A | Default path when no compatible GPU is available |

**Performance notes:**
- Any GPU latency or throughput result is hardware- and model-specific.
- The repository does not claim a final benchmark suite or universal performance guarantee for the current local environment.
- Runtime performance should be validated on the target machine before being treated as a production baseline.

## CLI Operations and Command Support

| Command | Status | Formats Supported | Options | Notes |
|---------|--------|-------------------|---------|-------|
| `validate` | ✅ Implemented | ARB, YAML, JSON, XML | `--root`, `--source`, `--format` | Validates keys across locales |
| `sync` | ✅ Implemented | ARB, YAML, JSON, XML | `--root`, `--source`, `--dry-run`, `--format` | Synchronizes missing keys |
| `translate` | ✅ Implemented | N/A (plain text, not resources) | positional `text`, `--source`, `--target`, `--device`, `--engine`, `--batch-size`, `--model` | Requires the `[gpu]` extra and a model already available locally; there is no `--text` option |
| `list-locales` | ✅ Implemented | ARB, YAML, JSON, XML | `--root`, `--format {arb,yaml,json,xml}` | Discovers locale files; `--format` selects the adapter, not the output format |

## Offline Execution Requirements

**Offline mode is NOT automatic.** Local translation requires:

1. **Model preparation:**
   - Model must be pre-cached locally before offline use
   - Set `HF_HUB_OFFLINE=1` to enforce offline-only behavior
   - Without cache, download will be attempted if `HF_HUB_OFFLINE=0` (default)

2. **Required dependencies:**
   - `torch>=2.7.0`
   - `transformers>=5.20.0` (as declared in the `gpu` extra; the installed version must be compatible with the chosen model)
   - `huggingface-hub>=0.20.0`
   - `sacremoses>=0.1.0`

3. **Supported language pairs:**
    - Marian engine: Helsinki-NLP Opus-MT language pairs. Default model selection covers only `en`, `es`, `fr`, `pt` combinations (see `_SUPPORTED_PAIRS` in `poliglota/cli.py`). Other pairs require explicit `--model` specification.
    - PyTorch engine: Any model supporting source/target language codes

4. **Device compatibility:**
   - CPU: Always available
   - CUDA: Requires NVIDIA GPU + compatible PyTorch build
   - MPS: Requires macOS 12.3+ with Apple Silicon

**Environment variables (POSIX shells):**
```bash
export POLIGLOTA_ENGINE=pytorch       # Select engine
export HF_HUB_OFFLINE=1                # Enforce offline (fail if model not cached)
export POLIGLOTA_DEVICE=cuda           # Set device preference
```

Windows PowerShell equivalent:

```powershell
$env:POLIGLOTA_ENGINE = "pytorch"
$env:HF_HUB_OFFLINE = "1"
$env:POLIGLOTA_DEVICE = "cuda"
```

## Known Limitations

### Format Support
- **YAML, JSON, XML:** Adapters exist; validation and sync coverage may vary by file structure
- **CSV, Gettext, others:** Not implemented; requires custom `FormatAdapter`
- **Locale inference:** Currently tied to file naming conventions (e.g., `app_<module>_<locale>.arb`)

### Translation Engines
- **Model selection:** Default free models are recommended; custom models require compatible tokenizer registration
- **Language pair support:** Limited to models available in the engine (Marian: Opus-MT pairs; PyTorch: any compatible model)
- **Translation quality:** Depends on model size, training data, and source language; not guaranteed to match professional translation services

### GPU and Device Behavior
- **GPU memory management:** Out-of-memory failures fall back to CPU or require `--batch-size` reduction; no automatic memory estimation
- **Multi-GPU systems:** Current implementation selects first available GPU; multi-GPU distribution not implemented
- **Device behavior in CI:** the CI matrix does not install PyTorch; device tests run with mocks and real GPU paths are not exercised there. Real GPU behavior depends on the local environment
- **Performance guarantees:** Benchmarks are hardware- and model-specific; results vary across environments

### Offline Execution
- **No automatic offline verification:** User must test offline capability after model caching
- **Silent fallback to download:** If model is not cached and `HF_HUB_OFFLINE=0`, Hugging Face Hub will be contacted; set `HF_HUB_OFFLINE=1` to prevent this
- **Network-dependent initialization:** First-time model loading may require network access unless model is pre-cached

### Architecture and Design
- **No license enforcement:** Poliglota does not audit or enforce third-party model licenses; user is responsible for verifying model license compatibility
- **No automatic format detection:** Format must be explicitly specified via CLI or code
- **Generic adapter contracts:** YAML, JSON, XML adapters use generic operations; format-specific validation is limited

## Pre-1.0 Status

Poliglota is in active development (v0.0.1). The following aspects remain subject to change:

- **API stability:** Core contracts (engines, formats) may change before 1.0
- **CLI argument names:** Command arguments may be renamed or restructured
- **Device selection behavior:** Fallback chains and strict mode semantics may be refined
- **Error messages:** Error reporting format and text may change
- **Performance characteristics:** Benchmarks and throughput are not guaranteed across versions

## See Also

- `docs/supported-formats.md` — Detailed format support status
- `docs/guides/translation-engine.md` — Translation engine behavior and model configuration
- `docs/guides/gpu-devices.md` — Device selection contract and troubleshooting
- `docs/guides/gpu-setup.md` — GPU setup and performance tuning
- `docs/third-party-resources.md` — Third-party model licenses and user responsibility
