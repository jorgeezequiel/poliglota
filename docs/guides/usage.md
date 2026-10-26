# Uso da CLI

A CLI do Poliglota concentra validação, sincronização, descoberta de locales e tradução local.

```bash
poliglota --help
```

## Validar recursos

```bash
poliglota validate --root . --source pt_BR --format arb
```

Opções:

| Opção | Descrição |
|---|---|
| `--root` | Raiz do projeto a ser varrida (padrão: diretório atual) |
| `--source` | Locale de origem usado como referência |
| `--format` | `arb` (padrão), `yaml`, `json` ou `xml` |
| `--glossary` | Arquivo de glossário em JSON ou CSV |
| `--locale` | Locale de destino para validar o glossário (padrão: todos) |
| `--check-keys` | Valida presença de chaves (ativo por padrão) |
| `--check-placeholders` | Valida consistência de placeholders (ativo por padrão) |
| `--check-glossary` | Valida cobertura de termos do glossário (requer `--glossary`) |

Exemplo com glossário:

```bash
poliglota validate --root . --source pt_BR --format arb \
  --glossary glossario.csv --check-glossary --locale en_US
```

## Sincronizar chaves ausentes

Simular sem gravar:

```bash
poliglota sync --root . --source pt_BR --dry-run --format arb
```

Aplicar as alterações:

```bash
poliglota sync --root . --source pt_BR --format arb
```

## Listar locales descobertos

```bash
poliglota list-locales --root . --format arb
```

`--format` seleciona o **adaptador** de formato (`arb`, `yaml`, `json` ou `xml`); não é uma opção de saída JSON. Por exemplo, `--format json` lista arquivos JSON de localização.

## Traduzir texto

O texto é um argumento **posicional**. A opção `--text` não existe.

```bash
poliglota translate --source pt_BR --target en_US "Olá, mundo!"
```

### Opções

| Opção | Descrição |
|---|---|
| `--source` | Locale de origem (padrão: `pt_BR`) |
| `--target` | Locale de destino (padrão: `en_US`) |
| `--engine` | `marian` (padrão) ou `pytorch`; o padrão resolve `POLIGLOTA_ENGINE` |
| `--model` | Modelo Hugging Face; se omitido, o motor padrão é auto-selecionado |
| `--device` | `auto` (padrão), `cpu`, `cuda`, `mps` ou `gpu` |
| `--preserve-placeholders` | Protege placeholders ARB antes e depois da tradução |
| `--batch-size` | Tamanho do lote de inferência (padrão: 8) |
| `--json-output` | Emite JSON em vez de texto puro |

Exemplos:

```bash
# Escolha explícita de dispositivo
poliglota translate --source pt_BR --target en_US --device cpu "Olá, mundo!"

# Motor PyTorch com lote menor
poliglota translate --source pt_BR --target en_US --engine pytorch --batch-size 4 "Olá, mundo!"

# Modelo específico
poliglota translate --source pt_BR --target en_US \
  --model Helsinki-NLP/opus-mt-tc-big-en-pt "Olá, mundo!"

# Preservação de placeholders e saída JSON
poliglota translate --source pt_BR --target en_US \
  --preserve-placeholders --json-output "Olá, {nome}!"
```

### Seleção automática de modelo

Quando `--model` não é informado, o motor padrão é escolhido para o par de idiomas. A ordem é:

1. `Helsinki-NLP/opus-mt-en-es`
2. `Helsinki-NLP/opus-mt-en-fr`
3. `Helsinki-NLP/opus-mt-tc-big-en-pt`

O primeiro modelo cujo conjunto de idiomas contém **origem e destino** é usado. Na prática, a seleção automática cobre pares entre `en`, `es`, `fr` e `pt`; qualquer outro par falha com erro explícito e exige `--model` ou `POLIGLOTA_DEFAULT_MOTOR`.

A variável `POLIGLOTA_DEFAULT_MOTOR` substitui completamente essa escolha:

```bash
export POLIGLOTA_DEFAULT_MOTOR="Helsinki-NLP/opus-mt-tc-big-en-pt"
```

No PowerShell:

```powershell
$env:POLIGLOTA_DEFAULT_MOTOR = "Helsinki-NLP/opus-mt-tc-big-en-pt"
```

Em modo offline (`HF_HUB_OFFLINE=1`), apenas modelos já presentes no cache local são aceitos.

## Cache de tradução (opcional)

O cache é desativado por padrão, vive apenas em memória e não persiste entre execuções:

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

- Valores habilitados: `1`, `true`, `yes`, `on`.
- O limite padrão é 256 entradas; valores inválidos ou menores que 1 geram aviso e voltam ao padrão.
- O cache considera engine, dispositivo, tamanho de lote e preservação de placeholders na chave.

## Comportamento offline

A tradução local só é válida quando o modelo necessário já está no cache local ou em um diretório configurado. O projeto não baixa arquivos de modelo automaticamente durante a execução.

```bash
export HF_HUB_OFFLINE=1
```

Se o cache estiver ausente, o comando falha com erro explícito em vez de continuar silenciosamente.

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | Comando concluído com sucesso (inclui `validate` sem problemas e `sync --dry-run` sem alterações) |
| `1` | Falha de validação, erro de argumento, recurso ausente ou erro de execução (por exemplo, modelo não disponível localmente) |

Os códigos `0` e `1` são os únicos usados pela CLI. Em scripts, trate qualquer código diferente de `0` como falha.

## Executar os testes

```bash
python -m pytest -q
```

A suíte não usa rede nem baixa modelos. Testes que exigem PyTorch são marcados como `skipped` quando o extra `[gpu]` não está instalado.

## Fluxo típico

1. instalar o pacote e as ferramentas de desenvolvimento;
2. validar a árvore de locales;
3. simular a sincronização e revisar o resultado;
4. aplicar a sincronização;
5. revisar traduções e o estado do cache de modelos;
6. manter os artefatos de modelo fora do repositório Git.

Para detalhes de motores e dispositivos, consulte `docs/guides/translation-engine.md` e `docs/guides/gpu-devices.md`.
