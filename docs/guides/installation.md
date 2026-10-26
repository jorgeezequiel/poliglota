# Instalação

Poliglota requer **Python 3.11 ou superior**. O ambiente de referência usado na validação local é Python 3.13 no Windows.

## 1. Criar o ambiente virtual

Windows (PowerShell), selecionando o interpretador com o launcher `py`:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Ajuste a versão (`-3.13`) para qualquer interpretador dentro da faixa suportada.

## 2. Instalar o pacote

### Pacote base (runtime)

```bash
python -m pip install -e .
```

Instala as dependências de runtime `defusedxml` e `PyYAML` e expõe o entrypoint `poliglota`.

### Com ferramentas de desenvolvimento

```bash
python -m pip install -e ".[dev]"
```

Inclui `pytest` e `ruff`, usados pelo workflow de CI.

### Stack opcional de tradução local

```bash
python -m pip install -e ".[gpu]"
```

Inclui PyTorch, Transformers, Hugging Face Hub e sacremoses. É opcional e não altera a versão do pacote. Pesos, tokenizers e caches permanecem fora do repositório e precisam ser preparados localmente.

### Windows + CUDA: instalação quebrada do PyTorch

Se o ambiente tiver uma instalação corrompida do PyTorch (por exemplo, erro de DLL do CUDA/cuDNN como `cudnn_adv64_9.dll` ou a importação falhar com `OSError: [WinError 126]`), primeiro remova a instalação problemática do ambiente e recrie um virtualenv limpo antes de reinstalar a stack opcional.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install --index-url https://download.pytorch.org/whl/cu126 "torch==2.7.1+cu126" "torchaudio==2.7.1+cu126" "torchvision==0.22.1+cu126"
python -m pip install "transformers==5.20.2" "huggingface-hub>=1.31.0,<3" "tokenizers==0.23.3" "sacremoses==0.1.0"
python -m pip install -e ".[dev,gpu]"
```

Essa sequência evita depender de um ambiente Python global já corrompido. O projeto mantém o extra `[gpu]` opcional, mas a instalação real do PyTorch precisa seguir a combinação compatível do runtime e da GPU disponível no Windows.

### Instalação sem rede

Com `setuptools>=77` e `wheel` já disponíveis no ambiente:

```bash
python -m pip install -e . --no-build-isolation --no-index
```

Em ambientes virtuais novos criados com Python 3.12+ apenas o `pip` vem instalado; nesse caso a instalação offline falha até que `setuptools` e `wheel` estejam presentes.

## 3. Verificar o ambiente

```bash
python --version
poliglota --help
python -c "import poliglota; print(poliglota.__version__)"
```

A versão atual do pacote é `0.0.1`.

## 4. Preparar modelos (opcional)

A tradução local só funciona com um modelo compatível já disponível no cache. O projeto **não baixa modelos automaticamente**. Para uso estritamente offline:

```bash
export HF_HUB_OFFLINE=1
```

No PowerShell:

```powershell
$env:HF_HUB_OFFLINE = "1"
```

Sem o modelo em cache, o comando falha com mensagem explícita.

## 5. Problemas comuns

### `poliglota: command not found` / `'poliglota' não é reconhecido`

O entrypoint é instalado pelo `pip`. Confirme que o ambiente virtual está ativado e que a instalação foi feita com `python -m pip install -e .`. Alternativa sem entrypoint:

```bash
python -m poliglota.cli --help
```

### `ModuleNotFoundError: No module named 'torch'`

O comando `translate` exige o extra `[gpu]`. Instale-o no mesmo interpretador usado para executar a CLI:

```bash
python -m pip install -e ".[gpu]"
```

Comandos de validação, sincronização e descoberta **não** precisam de PyTorch.

### Modelo não disponível localmente

A mensagem indica que o modelo não está no cache local. Prepare o cache do Hugging Face (`HF_HOME`) ou informe `--model` apontando para um modelo já disponível. O projeto não baixa modelos automaticamente; com `HF_HUB_OFFLINE=1`, qualquer tentativa de download falha.

### `ruff` ou `pytest` ausentes

As ferramentas de desenvolvimento vêm do extra `[dev]`:

```bash
python -m pip install -e ".[dev]"
```

Sem esse extra, lint e testes não podem ser executados; isso é uma limitação de ambiente, não um resultado de qualidade.

### Instalação offline falha em ambiente virtual novo

Ambientes criados com Python 3.12+ trazem apenas `pip`. Instale `setuptools>=77` e `wheel` a partir de uma fonte local antes de repetir `--no-build-isolation --no-index`.

### Divergência de versão

Se `python -c "import poliglota; print(poliglota.__version__)"` não retornar `0.0.1`, reinstale o pacote em modo editável. O teste `tests/test_version_consistency.py` detecta divergências entre `pyproject.toml`, `poliglota/__init__.py`, `VERSION` e os metadados instalados.

## Observações

- O CI executa Windows, Ubuntu e macOS com Python 3.11, 3.12 e 3.13.
- A stack de ML não é instalada no CI; testes que dependem dela são reportados como `skipped`.
- Consulte `docs/guides/usage.md` para os comandos da CLI.
