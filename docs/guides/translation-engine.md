# Guia do motor de tradução local

## Visão geral

A parte de tradução local do Poliglota usa modelos Hugging Face e um path de execução local. O comportamento implementado é explícito: o código busca um modelo compatível, valida o dispositivo e falha com erro claro quando a referência não existe no ambiente.

A CLI atual expõe `translate` e `translate-project`, e ambos dependem de um modelo local já preparado. A ferramenta não faz download automático nem substitui a presença do cache do usuário.

## 1. Dependências e stack suportada

Para usar tradução local, o ambiente precisa da stack opcional declarada em `pyproject.toml`:

```bash
python -m pip install -e ".[gpu]"
```

Essa stack inclui:

- `torch`
- `transformers`
- `huggingface-hub`
- `sacremoses`

O restante do pacote pode funcionar sem essa pilha, mas o caminho de tradução local depende dela.

## 2. Motores disponíveis

A CLI aceita `--engine` com valores `marian` e `pytorch`.

### `marian`

É o path tradicional do projeto para modelos do tipo Marian/Opus-MT. O código atual usa modelos como:

- `Helsinki-NLP/opus-mt-en-es`
- `Helsinki-NLP/opus-mt-en-fr`
- `Helsinki-NLP/opus-mt-tc-big-en-pt`

### `pytorch`

Também existe um caminho com PyTorch, por exemplo usando modelos como:

- `facebook/nllb-200-distilled-600M`
- `facebook/m2m100_418M`

O catálogo compartilhado do projeto define compatibilidade por par de idiomas e favorece alguns modelos por prioridade.

## 3. Seleção automática de modelo

O catálogo atual define a prioridade em runtime:

1. `Helsinki-NLP/opus-mt-en-es`
2. `Helsinki-NLP/opus-mt-en-fr`
3. `Helsinki-NLP/opus-mt-tc-big-en-pt`
4. `facebook/nllb-200-distilled-600M`
5. `facebook/m2m100_418M`

Quando `--model` é omitido, o runtime tenta usar esse catálogo para encontrar um modelo compatível com o par `source -> target`. Se o par não for suportado, a execução falha com mensagem clara.

## 4. Dispositivos suportados

A CLI aceita:

- `auto`
- `cpu`
- `cuda`
- `mps`
- `gpu`

### Regras reais

- `auto`: tenta CUDA > MPS > CPU
- `cpu`: usa CPU exclusivamente
- `cuda`: exige CUDA disponível
- `mps`: exige MPS disponível
- `gpu`: funciona como alias permissivo de auto em nível de helper, mas a CLI continua validando explicitamente o pedido do usuário

Em outras palavras, `auto` é permissivo; pedidos explícitos são estritos.

## 5. Offline e cache local

O fluxo de execução real exige que o modelo já esteja em cache local. O projeto não promete download automático durante a execução.

Para forçar modo offline:

```bash
export HF_HUB_OFFLINE=1
```

Se o modelo não estiver disponível localmente, a execução falha em vez de tentar ocultar a ausência do recurso.

## 6. Tradução de projeto

O comando `translate-project` percorre uma árvore e gera o resultado em uma pasta de saída. O default real do código é um diretório chamado `.poliglota_translated` dentro da raiz do projeto.

```bash
poliglota translate-project --root . --source pt_BR --target en_US --format json --output-dir .poliglota_translated
```

## 7. Limitações importantes

- não há garantia de qualidade profissional para qualquer idioma ou par
- modelos compatíveis dependem da plataforma e do ambiente local
- a seleção automática é limitada ao catálogo do projeto
- o contexto de tradução local vazio ou mal preparado vai falhar explicitamente

## 8. Referências internas

- [docs/guides/usage.md](usage.md)
- [docs/guides/gpu-devices.md](gpu-devices.md)
- [docs/LIMITATIONS.md](../LIMITATIONS.md)
- [poliglota/cli.py](../../poliglota/cli.py)
- [poliglota/model_catalog.py](../../poliglota/model_catalog.py)
