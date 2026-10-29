# Poliglota

[![CI](https://github.com/jorgeezequiel/poliglota/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jorgeezequiel/poliglota/actions/workflows/ci.yml)

Poliglota é um pacote Python para validar, sincronizar e traduzir recursos de localização em múltiplos formatos de arquivo, sem acoplar a lógica de formato à aplicação.

Versão atual: **0.0.2** (pré-1.0, em desenvolvimento ativo).

## O que o projeto faz

- Valida chaves e placeholders entre o locale de origem e os locales de destino.
- Sincroniza chaves ausentes a partir do locale de origem, com modo de simulação.
- Descobre locales em uma árvore de recursos.
- Expõe adaptadores de formato para **ARB** (padrão), **JSON**, **YAML** e **XML**.
- Oferece tradução local opcional por motores Marian ou PyTorch, sem downloads automáticos de modelos.

O projeto é intencionalmente conservador: pesos de modelo, tokenizers e caches ficam **fora do repositório** e são responsabilidade do usuário.

## Requisitos

- Python **3.11 ou superior** (`requires-python = ">=3.11"`).
- As dependências de runtime são `defusedxml` (leitura segura de XML) e `PyYAML` (adaptador YAML), instaladas automaticamente.
- A tradução local exige o extra opcional `[gpu]` (PyTorch, Transformers e Hugging Face Hub).

## Sistemas operacionais-alvo

O projeto é desenvolvido no Windows 11 e declara suporte a **Windows**, **Linux** e **macOS**, sempre com Python 3.11+.

O workflow de CI executa lint, verificação de versão e a suíte completa nesses três sistemas em Python 3.11, 3.12 e 3.13. A execução real está comprovada no GitHub Actions (badge acima), com os 10 jobs aprovados. A validação manual desta versão continua restrita ao Windows; Linux e macOS são cobertos pelo CI.

## Instalação

Pacote base:

```bash
python -m pip install -e .
```

Ferramentas de desenvolvimento (`pytest` e `ruff`):

```bash
python -m pip install -e ".[dev]"
```

Stack opcional de tradução local:

```bash
python -m pip install -e ".[gpu]"
```

O extra `[gpu]` não baixa modelos nem inclui pesos no pacote. Consulte `docs/guides/installation.md` para instalação offline e detalhes de ambientes virtuais.

## Uso da CLI

Após a instalação, o entrypoint é `poliglota`:

```bash
poliglota --help
```

### Validar recursos

```bash
poliglota validate --root . --source pt_BR --format arb
```

Opções adicionais: `--glossary` (JSON ou CSV), `--locale`, `--check-keys`, `--check-placeholders` e `--check-glossary`.

### Sincronizar chaves ausentes

```bash
poliglota sync --root . --source pt_BR --dry-run --format arb
```

Remova `--dry-run` para gravar as alterações.

### Listar locales descobertos

```bash
poliglota list-locales --root . --format arb
```

`--format` escolhe o adaptador (`arb`, `yaml`, `json`, `xml`), não o formato de saída.

### Traduzir texto

O texto é um argumento **posicional** (não existe `--text`):

```bash
poliglota translate --source pt_BR --target en_US "Olá, mundo!"
```

Opções disponíveis:

```bash
poliglota translate --source pt_BR --target en_US --device auto "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --engine pytorch --batch-size 4 "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --preserve-placeholders --json-output "Olá, {nome}!"
```

Se `--model` for omitido, o motor padrão é escolhido automaticamente para o par de idiomas. A ordem atual é `Helsinki-NLP/opus-mt-en-es`, `Helsinki-NLP/opus-mt-en-fr` e `Helsinki-NLP/opus-mt-tc-big-en-pt`; o primeiro cujo conjunto de idiomas contém origem **e** destino é usado. Na prática, a seleção automática cobre pares entre `en`, `es`, `fr` e `pt`; qualquer outro par falha com erro explícito e exige `--model` ou `POLIGLOTA_DEFAULT_MOTOR`. A variável `POLIGLOTA_DEFAULT_MOTOR` substitui completamente essa escolha.

### Preparar modelo para uso offline

Para baixar e cachear um modelo **antes** de usar tradução, utilize o comando `prepare-model`:

```bash
poliglota prepare-model --model Helsinki-NLP/opus-mt-en-pt --device auto
```

Opções:

```bash
poliglota prepare-model --model facebook/nllb-200-distilled-600M --device cuda
poliglota prepare-model --model facebook/mbart-large-50-many-to-many-mmt --device cpu
```

O comando:
- Baixa o modelo e tokenizer do Hugging Face Hub.
- Cacheia os artefatos localmente em `$HF_HOME` (ou `~/.cache/huggingface` por padrão).
- Valida a integridade do modelo (carrega config.json e verifica pesos).
- Retorna código de saída 0 (sucesso) ou 1 (falha).

Após `prepare-model` completar com sucesso, o modelo fica disponível para tradução **sem acesso à rede**, mesmo com `HF_HUB_OFFLINE=1` definido.

## Tradução local, modelos e offline

### Motores disponíveis

Três motores de tradução estão disponíveis:

- **`marian`** (padrão) — Modelo Marian NMT via Helsinki-NLP. Rápido, leve, suporta pares `en↔es`, `en↔fr`, `en↔pt`.
- **`pytorch`** — Modelos PyTorch via Transformers/Hugging Face:
  - **mBART** (`facebook/mbart-large-50-many-to-many-mmt`) — GPU (CUDA/MPS), suporta 50+ idiomas, incluindo PT-BR.
  - **NLLB** (`facebook/nllb-200-distilled-600M`) — CPU/GPU, suporta 200 idiomas via ISO 639-3, inclui `en`, `pt`, `es`, `fr`, `de`, `it`, `ja`, `zh`, `ko`.

A variável `POLIGLOTA_ENGINE` define o motor padrão (`marian` ou `pytorch`). Se omitida, o motor é escolhido automaticamente para o par de idiomas.

### Processamento de corpus YAML

Exemplo: tradução completa de corpus PazCall (6 arquivos YAML, 11 idiomas-alvo, ambos mBART GPU + NLLB CPU):

```bash
# Script de exemplo (processamento bilíngue PT-BR → ES com ambos motores):
python translate_pazcall_corpus.py
```

**Resultado validado:**
- ✓ mBART GPU: 44/58 strings traduzidas (PT-BR → ES-ES); non_translatable preservados (app_name, app_version, 11× language_name_*).
- ✓ NLLB CPU: 44/58 strings traduzidas (PT-BR → ES); mesma estrutura, placeholders intactos.
- ✓ Tempo total: 283.77s (GPU load + ambos motores).
- ✓ UTF-8 + estrutura YAML validados.

### Configuração e offline

- Nenhum modelo é baixado automaticamente pelo repositório, pela instalação ou pela suíte de testes.
- **Offline obrigatório:** Para uso offline, prepare o cache local **antes** da execução e defina `HF_HUB_OFFLINE=1`. Sem o modelo em cache e com `HF_HUB_OFFLINE=0` (padrão), o Hugging Face Hub será contactado. Sem o modelo em cache, o comando falha com mensagem explícita em vez de continuar silenciosamente.
- O modo offline aceita apenas modelos já presentes no cache do Hugging Face (`HF_HOME` ou `~/.cache/huggingface`).
- **Nota sobre `translate`:** O comando `translate` aceita **texto posicional** (não arquivos de recursos). Ele traduz texto único ou em lotes; para sincronizar e traduzir arquivos de localização, use `sync` + `validate` após preparar o modelo.

### Dispositivos

`--device` aceita `auto`, `cpu`, `cuda`, `mps` e `gpu`:

- `auto` é permissivo e tenta CUDA > MPS > CPU.
- Dispositivos explícitos são estritos e falham de forma clara quando indisponíveis.
- A seleção de dispositivo depende do PyTorch instalado; qualquer uso de `translate` requer o extra `[gpu]`.

## Cache de tradução (opcional)

O cache de respostas é **desativado por padrão** e vive apenas em memória, por processo:

Shells POSIX:

```bash
export POLIGLOTA_ENABLE_TRANSLATION_CACHE=1
export POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES=256
```

Windows PowerShell:

```powershell
$env:POLIGLOTA_ENABLE_TRANSLATION_CACHE = "1"
$env:POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES = "256"
```

Windows CMD:

```bat
set POLIGLOTA_ENABLE_TRANSLATION_CACHE=1
set POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES=256
```

Valores aceitos em `POLIGLOTA_ENABLE_TRANSLATION_CACHE`: `1`, `true`, `yes` ou `on`. O limite padrão é 256 entradas; valores inválidos ou menores que 1 geram aviso e voltam ao padrão. O cache é mantido apenas em RAM, fica desativado por padrão e não é persistido entre execuções. Ele reduz inferências repetidas ao custo de memória adicional e não substitui modelos locais nem constitui tradução remota.

O `RequestQueue` (`poliglota/engines/request_queue.py`) é um utilitário opcional de serialização de chamadas. Ele **não** está integrado ao caminho síncrono da CLI e não é necessário para o uso normal.

## Desenvolvimento e validação

```bash
python -m pytest -q
python -m ruff check poliglota tests
python -m ruff format --check poliglota tests
```

A suíte não usa rede e cobre CLI, contratos de formato, motores (com mocks), dispositivos e consistência de versão. Testes que exigem PyTorch são marcados como `skipped` quando a stack opcional não está instalada.

O workflow `.github/workflows/ci.yml` executa, em **Windows, Ubuntu e macOS** com Python **3.11, 3.12 e 3.13**:

1. lint e verificação de formatação com Ruff;
2. consistência de versão entre `pyproject.toml`, `poliglota/__init__.py` e `VERSION`;
3. suíte completa de testes, com relatório JUnit publicado como artefato.

A stack de ML (PyTorch/Transformers) não é instalada no CI para evitar downloads pesados; por isso os testes que dependem dela aparecem como `skipped` nos relatórios.

## Versionamento

A versão oficial é declarada em `pyproject.toml` e espelhada em `poliglota/__init__.py` e no arquivo `VERSION`. O teste `tests/test_version_consistency.py` (executado também no CI) impede divergência entre essas fontes e os metadados da instalação.

## Estrutura do repositório

```
poliglota/
├── poliglota/            # pacote
│   ├── cli.py            # CLI (validate, sync, list-locales, translate, prepare-model)
│   ├── config.py         # padrões usados pela CLI
│   ├── gpu.py            # detecção/validação de dispositivo + cache de modelo
│   ├── core/             # contratos independentes de formato e motor
│   ├── formats/          # adaptadores ARB, JSON, YAML e XML + registry
│   ├── engines/          # motores Marian/PyTorch, cache e RequestQueue
│   └── quality/          # glossário, placeholders e validação
├── tests/                # suíte pytest (sem rede)
├── docs/                 # documentação pública
│   ├── architecture/     # visão de arquitetura
│   ├── development/      # testes e política de relatórios internos
│   └── guides/           # instalação, uso, motores e GPU
├── reports/              # relatórios internos (ignorados pelo Git)
├── pyproject.toml        # metadados, dependências extras e configuração
├── VERSION               # espelho da versão do pacote
└── CHANGELOG.md
```

## Contribuição

Contribuições seguem as diretrizes de `CONTRIBUTING.md` (princípios não negociáveis, fluxo de desenvolvimento e política de versão/release). Alterações de comportamento exigem testes; o CI precisa passar nos três sistemas operacionais.

## Documentação

- `docs/guides/installation.md` — instalação e verificação do ambiente
- `docs/guides/usage.md` — fluxos de uso da CLI
- `docs/guides/translation-engine.md` — motores e configuração de modelos
- `docs/guides/gpu-devices.md` — contrato de seleção de dispositivo
- `docs/supported-formats.md` — matriz de suporte por formato
- `docs/architecture/overview.md` — camadas e contratos
- `docs/development/testing.md` — ambiente de testes e lint
- `docs/LIMITATIONS.md` — limitações conhecidas e status pré-1.0

## Licença

Distribuído sob a licença MIT. Consulte `LICENSE`.

Artefatos de terceiros (modelos, tokenizers, pesos) permanecem regidos por suas próprias licenças e responsabilidades, fora deste repositório.
