# Uso da CLI

A CLI do Poliglota concentra validação, sincronização, descoberta de locales, tradução de texto e tradução de projetos.

```bash
poliglota --help
```

## 1. Validar recursos

```bash
poliglota validate --root . --source pt_BR --format arb
```

Parâmetros principais:

| Opção | Descrição |
| --- | --- |
| `--root` | raiz do projeto a ser varrida |
| `--source` | locale de origem usado como referência |
| `--format` | `arb`, `yaml`, `json` ou `xml` |
| `--glossary` | arquivo de glossário em JSON ou CSV |
| `--locale` | locale alvo para validação de glossário |
| `--check-keys` | valida presença de chaves |
| `--check-placeholders` | valida placeholders |
| `--check-glossary` | valida cobertura do glossário |

Exemplo com glossário:

```bash
poliglota validate --root . --source pt_BR --format arb --glossary glossario.csv --check-glossary --locale en_US
```

## 2. Sincronizar chaves ausentes

Simular sem gravar:

```bash
poliglota sync --root . --source pt_BR --dry-run --format arb
```

Aplicar as mudanças:

```bash
poliglota sync --root . --source pt_BR --format arb
```

## 3. Listar locales descobertos

```bash
poliglota list-locales --root . --format arb
```

O argumento `--format` escolhe o adaptador de leitura (`arb`, `yaml`, `json`, `xml`); ele não é um formato de saída.

## 4. Traduzir texto

O texto é passado como argumento posicional; a opção `--text` não existe no código atual.

```bash
poliglota translate --source pt_BR --target en_US "Olá, mundo!"
```

### Opções principais

| Opção | Descrição |
| --- | --- |
| `--source` | locale de origem |
| `--target` | locale de destino |
| `--engine` | `marian` ou `pytorch` |
| `--model` | modelo do Hugging Face; opcional |
| `--device` | `auto`, `cpu`, `cuda`, `mps` ou `gpu` |
| `--batch-size` | tamanho do lote de inferência |
| `--json-output` | saída em JSON |
| `--preserve-placeholders` | preserva placeholders antes/depois da tradução |

Exemplos:

```bash
poliglota translate --source pt_BR --target en_US --device auto "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --engine pytorch --batch-size 4 "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --model facebook/nllb-200-distilled-600M "Olá, mundo!"
```

Se `--model` não for informado, a CLI tenta escolher um modelo padrão para o par de idiomas a partir do catálogo implementado. Pares não suportados falham com uma mensagem clara.

## 5. Traduzir um projeto

```bash
poliglota translate-project --root . --source pt_BR --target en_US --format json --output-dir .poliglota_translated
```

Esse comando percorre recursos de localização dentro da raiz do projeto e grava o resultado em um diretório de saída. Se `--output-dir` for omitido, o padrão é `.poliglota_translated` dentro da raiz.

## 6. Preparar modelo para uso offline

```bash
poliglota prepare-model --model facebook/nllb-200-distilled-600M --device auto
```

Esse fluxo prepara o modelo e o tokenizer para uso local. O projeto não tenta baixar modelos automaticamente em cada tradução.

## 7. Comportamento offline

O projeto limita a execução local à disponibilidade do modelo em cache:

```bash
export HF_HUB_OFFLINE=1
```

Se o modelo não estiver em cache, o comando falha com erro explícito.

## 8. Cache de tradução opcional

O cache em memória pode ser habilitado manualmente por variáveis de ambiente:

Shell POSIX:

```bash
export POLIGLOTA_ENABLE_TRANSLATION_CACHE=1
export POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES=256
```

PowerShell:

```powershell
$env:POLIGLOTA_ENABLE_TRANSLATION_CACHE = "1"
$env:POLIGLOTA_TRANSLATION_CACHE_MAX_ENTRIES = "256"
```

Ele é desativado por padrão, não persiste entre execuções e não substitui a presença do modelo local.

## 9. Códigos de saída

| Código | Significado |
| --- | --- |
| `0` | sucesso |
| `1` | erro de execução, argumento inválido ou ausência de recurso |

## 10. Testes

```bash
python -m pytest -q
```

A suíte não usa rede e não baixa modelos automaticamente. Testes que dependem do extra `[gpu]` são controlados no projeto e podem aparecer como `skipped` quando a stack de ML não está disponível.

## 11. Fluxo recomendado

1. instalar o pacote e as ferramentas de desenvolvimento;
2. validar a árvore de recursos;
3. simular sincronização e revisar as diferenças;
4. aplicar a sincronização;
5. preparar o modelo local quando for usar tradução;
6. executar a tradução em ambiente local com `HF_HUB_OFFLINE=1` quando a intenção for deferir para cache pronto.

Para detalhes de motores e dispositivos, consulte [translation-engine.md](translation-engine.md) e [gpu-devices.md](gpu-devices.md).
