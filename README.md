# Poliglota

[![CI](https://github.com/jorgeezequiel/poliglota/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jorgeezequiel/poliglota/actions/workflows/ci.yml)

Poliglota é uma ferramenta leve para validar, sincronizar e traduzir recursos de localização sem acoplar o projeto a um único formato ou a um único fluxo de interface.

A proposta do projeto é simples e direta: descobrir arquivos de locale, validar chaves e placeholders, copiar entradas ausentes a partir de uma fonte de referência e, quando necessário, traduzir texto ou coleções de arquivos usando modelos locais preparados pelo usuário.

## Navegação rápida

- [Instalação](docs/guides/installation.md)
- [Uso da CLI](docs/guides/usage.md)
- [GUI desktop](docs/guides/gui.md)
- [Formatos suportados](docs/supported-formats.md)
- [Arquitetura](docs/architecture/overview.md)
- [Limitações conhecidas](docs/LIMITATIONS.md)

## Visão geral

O Poliglota hoje entrega funcionalidade confirmada em código e testes para:

- validar recursos de localização contra um locale de origem
- sincronizar chaves ausentes a partir do locale de referência
- listar locales descobertos em uma árvore de projeto
- traduzir texto individual com modelo local
- traduzir um projeto completo para um ou mais destinos
- preparar modelos locais para uso offline
- operar por interface desktop guiada, sobre a mesma lógica da CLI

O projeto é intencionalmente conservador:

- não baixa modelos automaticamente durante o uso normal
- exige que o modelo esteja disponível localmente no cache do usuário
- não garante qualidade profissional de tradução em todos os pares e textos
- trata a stack de ML como dependência opcional para a parte de tradução local

## Formatos atualmente suportados

Os formatos efetivamente registrados no runtime atual são:

- ARB
- JSON
- YAML
- XML

CSV e gettext não têm adapter implementado no código atual. Para detalhes do estado real, consulte [docs/supported-formats.md](docs/supported-formats.md).

## Requisitos

- Python 3.11+
- dependências de runtime declaradas em `pyproject.toml`
- tradução local exige a stack opcional de ML (`.[gpu]`)

Instalação do pacote base:

```bash
python -m pip install -e .
```

Ferramentas de desenvolvimento:

```bash
python -m pip install -e ".[dev]"
```

Stack opcional para tradução local:

```bash
python -m pip install -e ".[gpu]"
```

Importante: esse extra inclui `torch`, `transformers`, `huggingface-hub` e `sacremoses`, mas não instala pesos de modelo automaticamente.

## Primeiros passos

Verifique a ajuda da CLI:

```bash
poliglota --help
```

Os comandos disponíveis no código atual são:

- `interactive`
- `guiado`
- `gui`
- `validate`
- `sync`
- `list-locales`
- `translate`
- `translate-project`
- `prepare-model`

## Validar recursos

```bash
poliglota validate --root . --source pt_BR --format arb
```

Esse comando compara os arquivos do projeto contra o locale origem e valida chaves, placeholders e, quando aplicável, termos de glossário.

## Sincronizar chaves ausentes

Modo de simulação:

```bash
poliglota sync --root . --source pt_BR --dry-run --format arb
```

Aplicar mudanças:

```bash
poliglota sync --root . --source pt_BR --format arb
```

## Listar locales descobertos

```bash
poliglota list-locales --root . --format arb
```

O argumento `--format` seleciona o adaptador (`arb`, `yaml`, `json`, `xml`); ele não é uma opção de saída.

## Traduzir texto

O texto é passado como argumento posicional:

```bash
poliglota translate --source pt_BR --target en_US "Olá, mundo!"
```

Exemplos adicionais:

```bash
poliglota translate --source pt_BR --target en_US --device auto "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --engine pytorch --batch-size 4 "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --model facebook/nllb-200-distilled-600M "Olá, mundo!"
```

Se `--model` não for informado, o runtime tenta resolver um modelo padrão para o par de idiomas. Pares não cobertos pelo catálogo falham de forma explícita e exigem uma escolha manual.

## Traduzir um projeto inteiro

```bash
poliglota translate-project --root . --source pt_BR --target en_US --format json --output-dir .poliglota_translated
```

Esse fluxo percorre arquivos de recursos em um diretório e escreve a saída em uma pasta de destino. Quando `--output-dir` não é informado, a pasta padrão é `.poliglota_translated` dentro da raiz do projeto.

## Preparar modelo para uso offline

```bash
poliglota prepare-model --model facebook/nllb-200-distilled-600M --device auto
```

Esse comando prepara o modelo e o tokenizer no cache local do Hugging Face. A ideia é deixar o ambiente pronto para execução offline sem depender de download automático em cada chamada.

## GUI desktop

A GUI também está disponível:

```bash
poliglota gui
```

ou:

```bash
poliglota-gui
```

A GUI é uma camada visual sobre a mesma lógica da CLI. Ela é útil para usuários que preferem um formulário visual em vez de escrever comandos no terminal. Ainda assim, a CLI segue sendo a referência de comportamento e validação.

Detalhes do fluxo da interface estão em [docs/guides/gui.md](docs/guides/gui.md).

## Modelo local e execução offline

O comportamento real do código é este:

- não há download automático de modelos durante a execução normal
- a tradução local depende de um modelo já disponível no cache do usuário
- `HF_HUB_OFFLINE=1` força o modo offline estrito
- pares ou dispositivos incompatíveis falham de forma clara em vez de cair silenciosamente em um backend não verificado

Essa decisão mantém o comportamento previsível e transparente para o usuário.

## Arquitetura em alto nível

O projeto tem uma divisão clara entre camadas:

- `poliglota/core` — contratos de formato e engine
- `poliglota/formats` — adapters para ARB, JSON, YAML e XML
- `poliglota/engines` — motores de tradução e cache opcional
- `poliglota/quality` — placeholders, glossário e validação
- `poliglota/cli.py` — interface da linha de comando
- `poliglota/gui.py` e `poliglota/gui_app.py` — camada desktop

Para uma visão mais detalhada, veja [docs/architecture/overview.md](docs/architecture/overview.md).

## Desenvolvimento e testes

Execute a suíte de testes:

```bash
python -m pytest -q
```

A versão do projeto também é validada para manter consistência entre:

- `pyproject.toml`
- `poliglota/__init__.py`
- `VERSION`

## Estrutura do repositório

```text
poliglota/
├── poliglota/
│   ├── cli.py
│   ├── gui.py
│   ├── gui_app.py
│   ├── gui_view.py
│   ├── core/
│   ├── formats/
│   ├── engines/
│   ├── quality/
│   └── ...
├── docs/
│   ├── architecture/
│   ├── guides/
│   ├── supported-formats.md
│   ├── LIMITATIONS.md
│   └── ...
├── tests/
├── pyproject.toml
├── VERSION
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── ROADMAP.md
└── scripts/
```

## Limitações e status

O Poliglota está em estado pré-1.0, mas com funcionalidade real. As principais limitações confirmadas no código são:

- a tradução depende de um modelo compatível em cache local
- suporte a GPU depende do ambiente local e do PyTorch instalado
- alguns formatos usam adapters genéricos e não possuem validação específica tão rica quanto ARB
- o projeto não inclui serviço de tradução em nuvem nem download automático de modelos

A matriz completa de compatibilidade e restrições está em [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Contribuição

Contribuições são bem-vindas, desde que sigam a política do projeto e as validações de comportamento. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para o fluxo de desenvolvimento e as regras de qualidade.

## Licença

Este projeto é distribuído sob a licença MIT. Veja [LICENSE](LICENSE).
