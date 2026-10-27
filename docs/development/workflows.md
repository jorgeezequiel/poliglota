# GitHub Actions Workflows — Poliglota CI/CD

## Visão Geral

O projeto Poliglota utiliza um workflow CI moderno desacoplado em quatro jobs independentes:

1. **quality** — Lint, formatação de código e verificação de versão (Ubuntu, Python 3.13)
2. **unit-tests** — Testes unitários isolados (Ubuntu/Windows/macOS × Python 3.11/3.12/3.13)
3. **integration-cpu** — Testes de integração com motores PyTorch rodando em CPU (Ubuntu/Windows/macOS × Python 3.11/3.12/3.13)
4. **integration-gpu** — Testes de integração com GPU/CUDA (self-hosted, main branch only)
5. **summary** — Compilação de resultados e falha clara se houver rejeições

## Justificativa de Desacoplamento

### Antes
- Todos os testes em um único job `tests` (27 combinações: 3 OS × 3 Python).
- Sem separação clara entre testes que exigem PyTorch e testes que não exigem.
- Cache de modelos Hugging Face implícito; sem documentação.
- GPU como "eventually consistent" (faltava runner self-hosted).

### Depois
- **unit-tests**: Rodamapenas com `[dev]` (pytest/ruff), nenhuma dependência PyTorch.
- **integration-cpu**: Com `[dev,gpu]` (PyTorch/Transformers), força CPU via `POLIGLOTA_TEST_CPU_ONLY=1`.
- **integration-gpu**: Separado, self-hosted, condicional (main branch only).
- Cache explícito de modelos Hugging Face com chaves por OS/Python.
- Timeouts apropriados: 10min (quality), 15min (unit), 30min (integration-cpu), 60min (integration-gpu).

## Matriz de Testes

### Quality (1 job)
| Sistema | Python | Timeout | Cache |
|---------|--------|---------|-------|
| Ubuntu  | 3.13   | 10 min  | pip   |

### Unit Tests (9 jobs)
| Sistema | Python | Timeout | Deps      | Cache |
|---------|--------|---------|-----------|-------|
| Ubuntu  | 3.11   | 15 min  | [dev]     | pip   |
| Ubuntu  | 3.12   | 15 min  | [dev]     | pip   |
| Ubuntu  | 3.13   | 15 min  | [dev]     | pip   |
| Windows | 3.11   | 15 min  | [dev]     | pip   |
| Windows | 3.12   | 15 min  | [dev]     | pip   |
| Windows | 3.13   | 15 min  | [dev]     | pip   |
| macOS   | 3.11   | 15 min  | [dev]     | pip   |
| macOS   | 3.12   | 15 min  | [dev]     | pip   |
| macOS   | 3.13   | 15 min  | [dev]     | pip   |

### Integration CPU (9 jobs)
| Sistema | Python | Timeout | Deps       | Cache HF                                    |
|---------|--------|---------|------------|---------------------------------------------|
| Ubuntu  | 3.11   | 30 min  | [dev,gpu]  | hf-models-cpu-Linux-py3.11                  |
| Ubuntu  | 3.12   | 30 min  | [dev,gpu]  | hf-models-cpu-Linux-py3.12                  |
| Ubuntu  | 3.13   | 30 min  | [dev,gpu]  | hf-models-cpu-Linux-py3.13                  |
| Windows | 3.11   | 30 min  | [dev,gpu]  | hf-models-cpu-Windows-py3.11                |
| Windows | 3.12   | 30 min  | [dev,gpu]  | hf-models-cpu-Windows-py3.12                |
| Windows | 3.13   | 30 min  | [dev,gpu]  | hf-models-cpu-Windows-py3.13                |
| macOS   | 3.11   | 30 min  | [dev,gpu]  | hf-models-cpu-Darwin-py3.11                 |
| macOS   | 3.12   | 30 min  | [dev,gpu]  | hf-models-cpu-Darwin-py3.12                 |
| macOS   | 3.13   | 30 min  | [dev,gpu]  | hf-models-cpu-Darwin-py3.13                 |

### Integration GPU (1 job)
| Tipo | Configuração | Timeout | Deps       | Cache HF                |
|------|--------------|---------|------------|-------------------------|
| self-hosted | CUDA | 60 min  | [dev,gpu]  | hf-models-gpu-cuda-py3.13 |

**Condicional**: Executado apenas em `push` para `main` (não em PRs nem `develop`).

## Cache de Modelos Hugging Face

### Estratégia
- **Chave primária**: `hf-models-{cpu|gpu}-{OS}-py{VERSION}` (ex: `hf-models-cpu-Linux-py3.13`)
- **Fallback**: `hf-models-{cpu|gpu}-{OS}-`, depois `hf-models-`
- **Caminho**: `~/.cache/huggingface` (padrão HF Hub)
- **Modelos pré-carregados**: Nenhum. A primeira execução baixa; execuções subsequentes restauram do cache.

### Modelos Utilizados em Testes
- **NLLB**: `facebook/nllb-200-distilled-600M` (CPU-friendly, ~1.2 GB)
- **mBART**: `facebook/mbart-large-50-many-to-many-mmt` (GPU-preferred, ~2.6 GB)

### Offline Mode
- **Default**: `HF_HUB_OFFLINE=0` (acessa Hub se modelo não estiver em cache)
- **Falha clara**: Se modelo não está em cache e modo offline está ativado, erro explícito
- **CI**: Sempre online (pode fazer download inicial)

## Marcadores de Testes (`@pytest.mark`)

### Marcadores Disponíveis
```python
@pytest.mark.unit        # Testes unitários (sem PyTorch, sem rede)
@pytest.mark.gpu         # Testes que usam CUDA/GPU
```

### Lógica de Seleção
- **unit-tests job**: `-m unit` (apenas testes unitários)
- **integration-cpu job**: `-m "not gpu"` (tudo exceto GPU, com PyTorch CPU)
- **integration-gpu job**: `-m gpu` (testes GPU/CUDA)

### Exemplo: Marcar um Teste
```python
import pytest

@pytest.mark.unit
def test_simple_validation():
    """Teste unitário, sem dependências."""
    assert True

@pytest.mark.gpu
def test_mbart_translation():
    """Teste GPU/CUDA, requer PyTorch."""
    assert True
```

## Validação Local (Desenvolvimento)

### Instalar Dependências
```bash
# Desenvolvimento + GPU stack
python -m pip install -e ".[dev,gpu]"
```

### Executar Testes Localmente

**Todos os testes:**
```bash
python -m pytest -q
```

**Apenas unitários:**
```bash
python -m pytest -q -m unit
```

**Apenas integração (CPU):**
```bash
python -m pytest -q -m "not gpu" --ignore=tests/test_version_consistency.py
```

**Apenas GPU:**
```bash
python -m pytest -q -m gpu
```

### Lint e Formatação
```bash
# Verificar lint
python -m ruff check poliglota tests

# Verificar formatação
python -m ruff format --check poliglota tests

# Corrigir formatação (in-place)
python -m ruff format poliglota tests
```

### Validar Versão
```bash
python -m pytest tests/test_version_consistency.py -v
```

## Artefatos JUnit

Cada job publica resultados JUnit XML em `reports/test-results/`:

- `junit-unit-{os}-py{version}.xml` — Unit tests
- `junit-integration-cpu-{os}-py{version}.xml` — Integration CPU
- `junit-integration-gpu-cuda-py3.13.xml` — Integration GPU

**Retenção**: 7 dias.

## Políticas de Falha

### Quality
- **Falha se**: Lint falha, formatação diverge, versão diverge.
- **Impacto**: Bloqueia PR.

### Unit Tests
- **Falha se**: Qualquer teste falha ou não roda.
- **Impacto**: Bloqueia PR.

### Integration CPU
- **Falha se**: Qualquer teste falha ou não roda.
- **Impacto**: Bloqueia PR.

### Integration GPU
- **Falha se**: Qualquer teste falha ou não roda.
- **Impacto**: Bloqueia push para `main` (não bloqueia PR).

### Summary
- **Falha se**: Total de testes = 0 OU falhas > 0 OU erros > 0.
- **Impacto**: Falha visual no workflow (badge vermelha).

## Limitações Conhecidas

### CI não Instala GPU
- `[gpu]` stack (PyTorch/Transformers) é instalado apenas em **integration-cpu** e **integration-gpu**.
- **unit-tests** usa apenas `[dev]`, evitando download de 2+ GB do PyTorch em cada execução.
- Testes que exigem PyTorch são marcados `@pytest.mark.gpu` e pulados em **unit-tests**.

### Sem Pre-staging de Modelos
- Modelos não são pre-carregados no repositório ou no CI.
- Primeira execução de **integration-cpu** pode levar ~10 min (download + cache).
- Execuções subsequentes usam cache (~1-2 min).

### GPU Runner Opcional
- **integration-gpu** requer runner self-hosted com CUDA.
- Se não configurado, job é pulado (sem erro).
- Documentar em `CONTRIBUTING.md` como configurar runner.

### Sem Compilação de Wheels
- Workflow não compila/publica distribuições (wheels, sdists).
- Apenas lint, testes e artefatos de teste.

## Manutenção

### Adicionar Novo Teste
1. Marque com `@pytest.mark.unit` (sem PyTorch) ou `@pytest.mark.gpu` (com PyTorch).
2. Coloque em `tests/`.
3. Re-execute localmente: `python -m pytest -q`.
4. Push; workflow roda automaticamente.

### Adicionar Nova Versão Python
1. Edite matriz em **unit-tests** e **integration-cpu** (`python-version: ["3.11", "3.12", "3.13", "3.14"]`).
2. Confirme `requires-python = ">=3.11"` em `pyproject.toml`.
3. Teste localmente se possível.
4. Push.

### Configurar GPU Runner
1. Instale Actions runner em máquina com CUDA.
2. Registre como self-hosted com labels `gpu`, `cuda`.
3. Workflow automaticamente usará `runs-on: [self-hosted, gpu, cuda]`.

### Desabilitar GPU Job (Temporário)
Adicione `if: false` em `integration-gpu.steps[0]` para pular sem erro.

## Visualização na UI do GitHub

- **Actions tab**: Clique em workflow → visualize status de cada job em tempo real.
- **Badges**: `![CI](https://github.com/jorgeezequiel/poliglota/actions/workflows/ci.yml/badge.svg?branch=main)` no README.
- **Artefatos**: Download de JUnit XMLs após conclusão.

## Próximos Passos

- [ ] Configurar runner self-hosted com CUDA para **integration-gpu**.
- [ ] Documentar em `CONTRIBUTING.md` como executar testes localmente.
- [ ] Adicionar badges por job (quality, unit, integration-cpu, integration-gpu).
- [ ] Monitorar tempos de execução; otimizar cache ou parallelização conforme necessário.
