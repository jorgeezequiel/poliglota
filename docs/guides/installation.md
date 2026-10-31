# Instalação

Poliglota requer Python 3.11 ou superior. O ambiente de referência usado na validação local foi Python 3.13 no Windows, mas o pacote declara suporte para 3.11+.

## 1. Criar um ambiente virtual

Windows (PowerShell):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Ajuste a versão da linguagem para qualquer intérprete que esteja dentro da faixa suportada.

## 2. Instalar o pacote

### Runtime base

```bash
python -m pip install -e .
```

Esse passo instala as dependências do runtime e expõe o entrypoint `poliglota`.

### Ferramentas de desenvolvimento

```bash
python -m pip install -e ".[dev]"
```

Esse extra inclui `pytest` e `ruff`, usados pelo workflow do repositório.

### Stack opcional para tradução local

```bash
python -m pip install -e ".[gpu]"
```

Esse extra inclui `torch`, `transformers`, `huggingface-hub` e `sacremoses`. Ele é opcional e não instala modelos ou pesos de tradução automaticamente.

## 3. Verificar a instalação

```bash
python --version
poliglota --help
python -c "import poliglota; print(poliglota.__version__)"
```

A versão atual declarada no projeto é `0.0.2`.

## 4. Preparar modelos para uso local

A tradução local depende de um modelo compatível já disponível no cache do usuário. O projeto não faz download automático em fluxo normal.

Para reforçar a execução offline:

```bash
export HF_HUB_OFFLINE=1
```

No PowerShell:

```powershell
$env:HF_HUB_OFFLINE = "1"
```

Se o modelo não estiver em cache, o comando falha de forma explícita.

### Preparar um modelo específico

```bash
poliglota prepare-model --model facebook/nllb-200-distilled-600M --device auto
```

A ideia do comando é baixar ou preparar o recurso no cache do Hugging Face antes da tradução sem depender de um processo automático durante a execução diária.

## 5. Problemas comuns

### `poliglota: command not found`

Confirme que o ambiente virtual está ativo e que o pacote foi instalado com `python -m pip install -e .`.

Alternativa direta:

```bash
python -m poliglota.cli --help
```

### `ModuleNotFoundError: No module named 'torch'`

O comando `translate` exige o extra `[gpu]` no mesmo ambiente em que a CLI está sendo executada.

```bash
python -m pip install -e ".[gpu]"
```

Comandos de validação, sincronização e descoberta não dependem de PyTorch.

### Modelo não disponível localmente

A mensagem indica que a biblioteca não encontrou o modelo requisitado no cache local. Esse é um cenário esperado em ambientes offline: o modelo precisa estar preparado antes da execução.

### Instalação offline em ambiente virtual novo

Ambientes virtuais recém-criados com Python 3.12+ podem vir apenas com `pip` instalado. Nesses casos, instale `setuptools>=77` e `wheel` a partir de uma fonte local antes de repetir a instalação em modo offline.

### Divergência de versão

Se `python -c "import poliglota; print(poliglota.__version__)"` não retornar `0.0.2`, reinstale o pacote em modo editável. O projeto valida a consistência da versão em `pyproject.toml`, `poliglota/__init__.py` e `VERSION`.

## 6. Observações importantes

- O CI executa Windows, Ubuntu e macOS com Python 3.11, 3.12 e 3.13.
- A stack de ML não é instalada automaticamente no CI; testes que dependem dela podem aparecer como `skipped`.
- Consulte também [docs/guides/usage.md](usage.md) e [docs/guides/gui.md](gui.md) para os fluxos reais da CLI e da interface desktop.

## 7. Compatibilidade do ambiente

A tradução local é um recurso opcional e dependente do ambiente do usuário. Em uso real, o projeto exige:

- Python 3.11+
- `torch` compatível com o runtime
- `transformers` compatível com o modelo escolhido
- cache local do modelo pronto antes da execução

O Poliglota não promete que qualquer par de idioma ou qualquer dispositivo funcione automaticamente em toda máquina. O comportamento real depende do hardware e do modelo disponível.
