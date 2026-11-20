# GitHub Actions Workflows — Poliglota CI/CD

## Visão Geral

O projeto Poliglota utiliza cinco jobs no workflow:

1. **quality** — Lint, formatação de código e verificação de versão (Ubuntu, Python 3.13)
2. **unit-tests** — Testes unitários isolados (Ubuntu/Windows/macOS × Python 3.11/3.12/3.13)
3. **integration-cpu** — Testes de integração com motores PyTorch rodando em CPU (Ubuntu/Windows/macOS × Python 3.11/3.12/3.13)
4. **integration-gpu** — Smoke test CUDA real (self-hosted, somente `workflow_dispatch`)
5. **summary** — Confere os jobs e exige JUnit válido por combinação obrigatória

## Justificativa de Desacoplamento

### Antes
- Todos os testes em um único job `tests` (27 combinações: 3 OS × 3 Python).
- Sem separação clara entre testes que exigem PyTorch e testes que não exigem.
- Cache de modelos Hugging Face desnecessário: a suíte não baixa modelos.
- GPU como "eventually consistent" (faltava runner self-hosted).

### Depois
- **unit-tests**: Executam `-m unit` com apenas `[dev]`.
- **integration-cpu**: Executa somente `not gpu and not unit`; inclui testes sem marcador e usa PyTorch CPU e Transformers reais.
- **integration-gpu**: Executa `-m gpu` somente por `workflow_dispatch`, em runner self-hosted CUDA.
- A qualidade coleta marcadores e falha se faltar o teste GPU ou houver sobreposição unit/GPU.
- Cache pip separado por perfil unitário e CPU; pesos de modelo não são cacheados.
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

Matriz: Ubuntu/Windows/macOS × Python 3.11/3.12/3.13; perfil `.github/requirements-ci-cpu.txt`. Windows/Linux instalam PyTorch pelo índice oficial CPU; macOS usa o wheel sem CUDA. O cache pip é separado do perfil unitário.

### Integration GPU (1 job)
| Tipo | Configuração | Timeout | Dependências | Cache |
|------|--------------|---------|--------------|-------|
| self-hosted | CUDA | 60 min | `[dev,gpu]` | cache pip local do runner; sem modelos |

**Condicional**: Solicitado somente por `workflow_dispatch`. Em push/PR, skipped significa não executado, não aprovado.

## Cache de dependências e modelos

### Estratégia
- `setup-python` cacheia o cache global do pip; a chave considera `pyproject.toml` e os perfis.
- Unit e CPU têm chaves distintas, evitando levar a stack CUDA aos jobs unitários.
- O job GPU não cria um cache Actions com wheels CUDA de vários GB.
- Os testes CI usam `HF_HUB_OFFLINE=1`; pesos de modelo não são baixados nem cacheados.

### Offline Mode
- **CI**: `HF_HUB_OFFLINE=1`; a suíte não depende de pesos nem de acesso ao Hub.
- **Produto**: modelos são preparados explicitamente pelo usuário.

## Marcadores de Testes (`@pytest.mark`)

### Marcadores Disponíveis
```python
@pytest.mark.unit        # Testes unitários isolados
@pytest.mark.gpu         # Teste que exige GPU/CUDA real
@pytest.mark.gui         # Teste que exige display Tk real
```

### Lógica de Seleção
- **unit-tests job**: `-m unit` (apenas testes unitários)
- **integration-cpu job**: `-m "not gpu and not unit"` e ignora apenas a versão, coberta em quality. Testes sem marcador pertencem explicitamente à integração CPU.
- **integration-gpu job**: `-m gpu` (smoke test com módulo/tensor CUDA real, sem baixar modelo)
- **Partição**: `python scripts/ci_reporting.py validate-selection` falha se houver sobreposição unit/GPU ou se a cobertura GPU desaparecer.

### Exemplo: Marcar um Teste
```python
import pytest

@pytest.mark.unit
def test_simple_validation():
    """Teste unitário, sem dependências."""
    assert True

@pytest.mark.gpu
def test_cuda_tensor_on_gpu():
    """Teste GPU/CUDA real, requer runner com PyTorch CUDA."""
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
python -m pytest -q -m "not gpu and not unit" --ignore=tests/test_version_consistency.py
```

**Verificar a partição do CI:**
```bash
python scripts/ci_reporting.py validate-selection
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
- **Solicitação**: `workflow_dispatch`; requer runner self-hosted CUDA.
- **Interpretação**: `skipped` em push/PR significa GPU não executada, não aprovada.

### Summary
- **Falha se**: Job obrigatório falhar/cancelar, JUnit faltar/duplicar/ser inválido, uma matriz não coletar testes ou houver falhas/erros. No dispatch, o JUnit GPU também é obrigatório.
- **Impacto**: Falha visual no workflow (badge vermelha).

## Limitações Conhecidas

### Perfis de dependências
- **unit-tests** usa apenas `[dev]`; **integration-cpu** instala PyTorch CPU e Transformers; **integration-gpu** usa `[dev,gpu]`.
- Testes que usam PyTorch, mas não precisam de hardware GPU, permanecem no conjunto CPU.

### Sem downloads de modelos no CI
- Pesos não são pre-carregados nem cacheados. `HF_HUB_OFFLINE=1` faz downloads acidentais falharem claramente.

### GPU Runner manual
- **integration-gpu** requer runner self-hosted com CUDA.
- É solicitado por `workflow_dispatch`; em eventos comuns aparece skipped e não conta como aprovação.
- Documentar em `CONTRIBUTING.md` como configurar runner.

### Sem Compilação de Wheels
- Workflow não compila/publica distribuições (wheels, sdists).
- Apenas lint, testes e artefatos de teste.

## Manutenção

### Adicionar Novo Teste
1. Marque com `@pytest.mark.unit` (sem PyTorch) ou `@pytest.mark.gpu` (com PyTorch).
2. Coloque em `tests/`.
3. Re-execute localmente: `python -m pytest -q` e `python scripts/ci_reporting.py validate-selection`.
4. Push; workflow roda automaticamente.

### Adicionar Nova Versão Python
1. Edite matriz em **unit-tests** e **integration-cpu** (`python-version: ["3.11", "3.12", "3.13", "3.14"]`).
2. Confirme `requires-python = ">=3.11"` em `pyproject.toml`.
3. Teste localmente se possível.
4. Push.

### Configurar GPU Runner
1. Instale Actions runner em máquina com CUDA.
2. Registre como self-hosted com labels `gpu`, `cuda`.
3. Solicite `workflow_dispatch`; o job não é executado automaticamente em push.

### Desabilitar GPU Job (Temporário)
Mantenha a condição `workflow_dispatch` para não executar GPU em eventos comuns.

## Visualização na UI do GitHub

- **Actions tab**: Clique em workflow → visualize status de cada job em tempo real.
- **Badges**: `![CI](https://github.com/jorgeezequiel/poliglota/actions/workflows/ci.yml/badge.svg?branch=main)` no README.
- **Artefatos**: Download de JUnit XMLs após conclusão.

## Próximos Passos

- [ ] Configurar runner self-hosted com CUDA para **integration-gpu**.
- [ ] Documentar em `CONTRIBUTING.md` como executar testes localmente.
- [ ] Adicionar badges por job (quality, unit, integration-cpu, integration-gpu).
- [ ] Monitorar tempos de execução; otimizar cache ou parallelização conforme necessário.
