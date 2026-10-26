# Arquitetura Multi-Dispositivo para Poliglota v0.0.1+

**Data:** 2026-10-24  
**Status:** DESIGN APENAS (sem código implementado)  
**Objetivo:** Permitir modelos CPU e GPU **independentes** sem fallbacks silenciosos, respeitando Rule of Gold.

---

## 1. Problema Atual

### Estado Existente
- `pytorch_engine.py:__init__(device="auto")` — device selecionado em init, **fixo para lifetime da engine**
- `load_model(device="cpu")` — aceita override de device, mas **reutiliza model/tokenizer já carregados**
- `_move_model_to_device()` — **silenciosamente faz fallback GPU→CPU em OOM** (RuntimeError com "out of memory")
- CLI `translate --device auto` — permite fallback silencioso; `translate --device cuda` é strict (erro se indisponível)
- **CPU e GPU forçosamente compartilham** o mesmo model + tokenizer; nenhum suporte para modelos diferentes

### Violações da Rule of Gold
1. **"No silent fallback"** — `_move_model_to_device()` silenciosamente move para CPU quando OOM ocorre em GPU
2. **"Explicit device selection honored"** — device é selecionado no `__init__`, não permitindo mudança de modelo + device em runtime
3. **"CPU and GPU may use different models"** — a arquitetura força o mesmo modelo em ambos os dispositivos

---

## 2. Solução Proposta

### 2.1 Separação de Configuração: CPU vs. GPU

**Arquivo de configuração externo** (YAML ou JSON, fora do Git):

```yaml
# poliglota_config.yaml (exemplo; localização definida por user)
models:
  cpu:
    engine: pytorch          # ou 'marian'
    model_name: facebook/m2m100_418M
    max_batch_size: 4        # CPU: batch pequeno
    max_memory_mb: 2048      # CPU: limite conservador
    device: cpu              # explícito
  
  gpu:
    engine: pytorch
    model_name: facebook/m2m100_418M  # pode ser diferente de CPU
    max_batch_size: 8
    max_memory_mb: 4096
    device: cuda             # ou 'mps', 'auto'
    fallback_on_oom: false   # CRÍTICO: desabilitar fallback silencioso

inference:
  default_device: auto        # 'auto', 'cpu', 'cuda', 'mps'
  strict: false               # se true, erro em device indisponível
  preserve_placeholders: true
```

**Alternativa: Environment variables** (para CI/containers)

```bash
export POLIGLOTA_MODEL_CPU="facebook/m2m100_418M"
export POLIGLOTA_MODEL_GPU="facebook/m2m100_418M"
export POLIGLOTA_DEVICE_DEFAULT="auto"
export POLIGLOTA_DEVICE_STRICT="false"
```

**Alternativa: CLI --config flag**

```bash
poliglota translate --config ./poliglota_config.yaml \
  --device cuda \
  --text "Olá, mundo!" \
  --source pt_BR --target en_US
```

### 2.2 Nova Camada: DeviceAwareModelRegistry

```python
# poliglota/core/device_model_registry.py (pseudocódigo)

class DeviceModelConfig:
    """Configuração de modelo para um dispositivo específico."""
    device: str              # 'cpu', 'cuda', 'mps'
    model_name: str          # model identifier (HF, local path)
    engine_name: str         # 'pytorch', 'marian'
    max_batch_size: int      # batch size limit
    max_memory_mb: int       # memory limit
    fallback_on_oom: bool    # CRÍTICO: nunca true para device explícito

class DeviceAwareModelRegistry:
    """Gerencia modelos independentes para CPU e GPU."""
    
    def load_for_device(self, device: str) -> EngineInstance:
        """Carrega o modelo apropriado para o dispositivo.
        
        - Se device='auto': seleciona e carrega melhor disponível
        - Se device='cuda/mps/cpu': carrega modelo específico ou erro se não disponível
        - Nunca faz fallback silencioso para device != 'auto'
        """
        config = self.get_config(device)  # lookup na config
        engine = self._create_engine(config.engine_name, config.model_name)
        engine.load_model(device=config.device)
        return engine
    
    def get_config(self, device: str) -> DeviceModelConfig:
        """Retorna config para o dispositivo (do YAML/env/API)."""
        # Lógica de fallback para encontrar config:
        # 1. Buscar em dict carregado do YAML
        # 2. Buscar em env vars (POLIGLOTA_MODEL_{CPU|GPU})
        # 3. Usar defaults (M2M100 + facebook/m2m100_418M)
        pass
```

### 2.3 Modificações Mínimas ao PyTorchTranslationEngine

**CRÍTICO: Mudar `_move_model_to_device()` para NUNCA fazer fallback silencioso**

```python
# poliglota/engines/pytorch_engine.py:251 (modificado)

def _move_model_to_device(self, model: _ModelProtocol, device: str) -> None:
    """Move modelo para device. NUNCA faz fallback silencioso.
    
    Args:
        model: Instância do modelo
        device: Device target ('cpu', 'cuda', 'mps')
    
    Raises:
        RuntimeError: Se device não está disponível ou OOM ocorre
    """
    try:
        model.to(device)
    except RuntimeError as exc:
        if self._is_cuda_oom_error(exc) or "out of memory" in str(exc).lower():
            # MUDANÇA: Lançar erro em vez de silenciosamente fazer fallback
            msg = (
                f"Out-of-memory while moving model to {device}. "
                f"Model {self.model_name} requires more VRAM than available. "
                f"Reduce batch size or use a smaller model."
            )
            logger.error(msg)
            raise RuntimeError(msg) from exc
        raise
```

### 2.4 CLI Integration

**Novo flag: `--config` (opcional)**

```bash
# Sem config: usa defaults + device auto
poliglota translate --device auto \
  --text "Olá, mundo!" \
  --source pt_BR --target en_US

# Com config externa: carrega modelos CPU/GPU da config
poliglota translate --config ./poliglota_config.yaml \
  --device auto \
  --text "Olá, mundo!" \
  --source pt_BR --target en_US

# Force device específico: carrega modelo CPU ou GPU conforme config
poliglota translate --config ./poliglota_config.yaml \
  --device cuda \
  --text "Olá, mundo!" \
  --source pt_BR --target en_US
```

**Lógica de seleção:**

1. Ler config se `--config` fornecido
2. Se `--device` fornecido: usar device específico + modelo correspondente na config
3. Se `--device auto` ou não fornecido: auto-select CUDA > MPS > CPU, carregando modelo correspondente
4. **NUNCA fazer fallback silencioso** a menos que `--device auto` e config permita

---

## 3. Exemplo: CPU vs. GPU com Modelos Diferentes

### Cenário: CPU usa M2M100 small, GPU usa M2M100 418M (maior, mais preciso)

```yaml
# poliglota_config.yaml
models:
  cpu:
    engine: pytorch
    model_name: facebook/m2m100_418M    # CPU: modelo menor (80 MB)
    max_batch_size: 2
    device: cpu
    fallback_on_oom: false              # OBRIGATÓRIO
  
  gpu:
    engine: pytorch
    model_name: facebook/m2m100_418M    # GPU: modelo maior (840 MB, melhor qualidade)
    max_batch_size: 8
    device: cuda
    fallback_on_oom: false              # OBRIGATÓRIO
```

**Execução:**

```bash
# CPU: carrega M2M100 small
poliglota translate --config ./poliglota_config.yaml --device cpu \
  --text "Olá, mundo!" --source pt_BR --target en_US

# GPU: carrega M2M100 418M
poliglota translate --config ./poliglota_config.yaml --device cuda \
  --text "Olá, mundo!" --source pt_BR --target en_US
```

---

## 4. Fluxo de Inicialização (Novo)

```
User invoca: poliglota translate --config cfg.yaml --device cuda --text "..."
                    ↓
            CLI carrega config do arquivo YAML
                    ↓
            Lookup modelo para device='cuda' → DeviceModelConfig
                    ↓
            DeviceAwareModelRegistry.load_for_device('cuda')
                    ↓
            Cria engine (pytorch) + modelo (facebook/m2m100_418M)
                    ↓
            Chama engine.load_model(device='cuda')
                    ↓
            PyTorchTranslationEngine.__init__(model_name, device='cuda')
                    ↓
            _resolve_device('cuda') → valida VRAM, retorna 'cuda'
                    ↓
            load_model() → carrega model + tokenizer
                    ↓
            _move_model_to_device(model, 'cuda')
                    ↓
            SE ERRO (OOM): LANÇA RuntimeError (nunca fallback silencioso)
                    ↓
            Tradução executada em cuda:0
```

---

## 5. Impacto em Casos de Uso Existentes

### Caso 1: CLI simples (sem config)
```bash
poliglota translate --device auto "Olá, mundo!"
```
✅ Continua funcionando: auto-seleciona CUDA > MPS > CPU, usa modelos defaults.

### Caso 2: CLI com device explícito (sem config)
```bash
poliglota translate --device cuda "Olá, mundo!"
```
⚠️ **MUDANÇA:** Se CUDA indisponível e `--device cuda` fornecido, agora **erro** (antes: fallback silencioso).  
✅ **Razão:** Honra "explicit device selection honored" (Rule of Gold).

### Caso 3: Programmatic API (Python)
```python
from poliglota.engines.pytorch_engine import PyTorchTranslationEngine
engine = PyTorchTranslationEngine("facebook/m2m100_418M", device="cuda")
engine.load_model()  # Device já fixo; sem mudança
result = engine.translate("Olá, mundo!", "pt", "en")
```
✅ Compatível: API existente preservada.

### Caso 4: Config externa (novo)
```bash
poliglota translate --config ./cfg.yaml --device gpu
```
✅ **Novo:** Permite diferentes modelos para CPU vs. GPU.

---

## 6. Testes Necessários (Spec Apenas)

| Teste | Descrição | Status Atual |
|-------|-----------|--------------|
| `test_device_model_registry_load_cpu` | Carrega modelo CPU com config | ❌ Não existe |
| `test_device_model_registry_load_gpu` | Carrega modelo GPU com config | ❌ Não existe |
| `test_device_model_registry_load_different_models` | CPU usa modelo A, GPU usa modelo B | ❌ Não existe |
| `test_pytorch_engine_no_fallback_on_explicit_cuda_oom` | OOM em CUDA → erro (nunca fallback) | ❌ Não existe |
| `test_pytorch_engine_no_fallback_on_explicit_mps_oom` | OOM em MPS → erro (nunca fallback) | ❌ Não existe |
| `test_cli_translate_with_config` | CLI com `--config` carrega config corretamente | ❌ Não existe |
| `test_cli_translate_device_mismatch_error` | `--device cuda` sem CUDA → erro (não fallback) | ⚠️ Pode existir parcialmente |

---

## 7. Cronograma Sugerido (Fases)

### Fase 1: DeviceAwareModelRegistry (1–2 dias)
- Criar `poliglota/core/device_model_registry.py`
- Implementar leitura de config YAML (via PyYAML)
- Lookup de modelo por device
- Testes unitários

### Fase 2: Modificações ao PyTorchTranslationEngine (1 dia)
- Remover fallback silencioso de `_move_model_to_device()`
- Adicionar testes que validam erro em OOM (não fallback)
- Garantir `load_model(device=X)` honra device explícito

### Fase 3: CLI Integration (1 dia)
- Adicionar `--config` flag ao parser
- Integrar DeviceAwareModelRegistry no CLI
- Testes E2E com config

### Fase 4: Corpus Validation & CPU Recovery (2 dias)
- SHA-256 manifest do corpus isolado
- Venv CPU + PyTorch CPU + Transformers compatível
- Testes CPU vs. GPU latency/modelo

### Fase 5: Consolidação & Docs (1 dia)
- Atualizar README com multi-device architecture
- Documentar config schema
- Exemplos de uso (CPU vs. GPU)

---

## 8. Restrições (Poliglota Rule of Gold)

✅ **Offline:** Config define modelos locais; URLs externas apenas para download inicial (controlado pelo user)  
✅ **Local:** Modelos salvos fora do Git; user controla paths  
✅ **User-controlled:** Config é um arquivo YAML/JSON editável  
✅ **No silent fallback:** Erro em device/modelo indisponível (a menos que `--device auto`)  
✅ **Explicit device honored:** `--device cuda` → ou cuda ou erro  
✅ **CPU ≠ GPU models:** Cada pode usar modelo diferente  
✅ **Resource-aware:** Config permite tuning de batch_size, memory_mb  

---

## 9. Decisões Arquiteturais

| Decisão | Alternativa | Razão |
|---------|-------------|-------|
| **Config externo (YAML)** | In-code defaults | Permite user customization offline |
| **DeviceAwareModelRegistry** | Extend PyTorchTranslationEngine | Separation of concerns: config lookup ≠ engine logic |
| **No silent fallback** | Auto-fallback GPU→CPU | Honra Rule of Gold; força user a resolver OOM explicitamente |
| **Per-device model** | Força model único | GPU pode precisar modelo maior; CPU precisa modelo menor |
| **CLI --config flag** | Env vars only | YAML é humano-legível; env vars ainda suportadas como override |

---

## 10. Compatibilidade com FASE 2/3 Existente

- ✅ Testes FASE 2 (221 PASSED + 8 SKIPPED) — não quebrados
- ✅ GPU recovery (ETAPA A–D) — evidência JSON validada, modelos funcionando
- ✅ CLI `translate --device auto` — continua funcionando
- ⚠️ CLI `translate --device cuda` — comportamento muda (erro em vez de fallback)
- ✅ Corpus isolado — utilizado em validação posterior (SHA-256)

---

## Próximas Ações (Após Aprovação)

1. **Verificar corpus isolado** com SHA-256 manifest
2. **Implementar DeviceAwareModelRegistry** (sem modificar engines ainda)
3. **Testes unitários** para registry + config loading
4. **Modificar PyTorchTranslationEngine** para remover fallback silencioso
5. **Integrar registry + config** no CLI
6. **CPU recovery** com modelo CPU independente
7. **Documentação** finalizada + exemplos

---

