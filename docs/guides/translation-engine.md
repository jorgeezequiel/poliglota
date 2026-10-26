# Guia do motor de tradução local

## Visão geral

O projeto inclui uma camada de tradução local baseada em modelos Hugging Face e em um adapter Marian, com suporte para execução em CPU, CUDA e MPS quando o runtime e o modelo estiverem disponíveis.

A documentação deste repositório deve ser lida com cuidado: o código implementado confirma a existência de um fluxo local de inferência, mas não garante que qualquer modelo ou qualquer par de idiomas funcione automaticamente em todo ambiente. O comportamento real depende do modelo disponível no cache local, dos recursos instalados (`torch`, `transformers`, `huggingface-hub`) e da compatibilidade do hardware.

## Arquitetura

A CLI `poliglota translate` usa um caminho de resolução de engine e de dispositivo definido em `poliglota/cli.py`:

- `engine` pode ser `marian` ou `pytorch`
- a seleção de `device` usa `auto`, `cpu`, `cuda`, `mps` ou `gpu`
- a verificação offline verifica a presença do modelo no cache local do Hugging Face
- o carregamento do modelo falha claramente quando o cache esperado está ausente em modo offline

O adapter Marian real está em `poliglota/engines/marian.py`. Ele implementa uma interface de motor local e exige uma stack específica de dependências para funcionar.

## Dependências e stack suportada

Para usar a engine local, o ambiente precisa ter as dependências opcionais declaradas em `pyproject.toml`:

```bash
python -m pip install -e ".[gpu]"
```

A stack opcional inclui:

- `torch>=2.7.0`
- `transformers>=5.20.0`
- `huggingface-hub>=0.20.0`

O restante do projeto pode funcionar sem essa stack, mas a parte de tradução local exige a presença dessas dependências e do modelo correto em cache.

## Modelos e seleção padrão

O código atual não afirma um único modelo universal como padrão definitivo para todos os casos. Em vez disso, a CLI define uma prioridade explícita de modelos em `poliglota/cli.py`:

```python
_DEFAULT_MOTOR_PRIORITY = (
    "Helsinki-NLP/opus-mt-en-es",
    "Helsinki-NLP/opus-mt-en-fr",
    "Helsinki-NLP/opus-mt-tc-big-en-pt",
)
```

Esses modelos são usados conforme o par de idiomas suportado e podem ser sobrescritos pela variável `POLIGLOTA_DEFAULT_MOTOR` ou por `--model` na CLI.

Isso significa:

- o projeto expõe modelos do tipo OPUS-MT como caminhos concretos implementados
- a seleção automática depende do par de idiomas solicitado
- não há garantia de que todos os pares de idioma sejam cobertos por um único modelo genérico
- o código admite customização por usuário e por modelo local compatível

## Uso pela CLI

Exemplos reais do comportamento atual:

```bash
poliglota translate --source pt_BR --target en_US "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --model Helsinki-NLP/opus-mt-tc-big-en-pt "Olá, mundo!"
```

Quando `--model` não é informado, o runtime tenta selecionar um modelo padrão a partir do par de idiomas. Se o par não for suportado, a execução falha com uma mensagem clara em vez de degradar em silêncio.

## Dispositivo de execução

A decisão de dispositivo segue a regra documentada no código real:

- `auto`: CUDA > MPS > CPU
- `cpu`: força CPU e não alterna para GPU
- `cuda`: falha explicitamente se CUDA não estiver disponível
- `mps`: falha explicitamente se MPS não estiver disponível
- `gpu`: caminho permissivo equivalente a seleção automática em nível de helper, mas a CLI aplica validação estrita para pedidos explícitos

Essa distinção é importante: a biblioteca de detecção pode escolher automaticamente um backend disponível, mas a interface da CLI não deve esconder casos em que o usuário pediu um dispositivo específico e ele não está presente.

## Offline capability

A operação offline depende do cache local do Hugging Face. O fluxo real em `poliglota/cli.py` verifica a cache do modelo antes de tentar inferência:

```bash
export HF_HUB_OFFLINE=1
```

Quando `HF_HUB_OFFLINE=1` é definido, o projeto exige que o modelo já esteja em cache local. Se o cache estiver ausente, a execução falha com uma mensagem clara.

Em outras palavras:

- offline não é um garantido universal
- a presença do modelo local é um requisito real
- downloads e preparação do modelo continuam sendo responsabilidade do usuário

## Modelos locais e recursos externos

Os modelos de tradução, pesos, tokenizers, caches e recursos similares são tratados como recursos externos e fora do repositório Git, salvo que o usuário escolha explicitamente um diretório local de armazenamento.

Isso significa que Poliglota:

- não empacota modelos no repositório
- não distribui pesos como parte do código-fonte
- não garante licenciamento automático para modelos de terceiros
- exige que o usuário valide origem, licença e compatibilidade do recurso usado

## Limitações importantes

O código confirma uma família útil de fluxos de tradução local, mas não há garantia de qualidade profissional universal, nem de suporte para todos os idiomas ou todos os pares de tradução.

Limitações do estado atual:

- o modelo precisa estar disponível localmente para execução offline
- o suporte depende do modelo e do idioma escolhido
- a qualidade pode variar muito entre pares e textos
- CPU/GPU/VRAM e performance continuam sendo dependentes do ambiente local
- a arquitetura e a camada de engine podem evoluir antes de uma versão estável 1.0

## Resumo prático

O estado real do projeto é mais conservador do que alguns relatórios antigos sugerem:

- há suporte real para tradução local com modelos Hugging Face e adaptação Marian
- a seleção automática e explícita de dispositivo é implementada e documentada no código
- o default de CLI é orientado por modelos concretos do repositório e não por um único benchmark universal
- o offline exige model cache e ambiente preparado
- o usuário continua sendo responsável por modelos, licenças, termos e recursos externos

Para uma visão completa de escopo e limitações, consulte:

- `docs/LIMITATIONS.md`
- `docs/third-party-resources.md`
- `docs/guides/gpu-devices.md`
- `poliglota/cli.py`
- `poliglota/engines/marian.py`
