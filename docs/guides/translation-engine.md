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

## 2. Motores e modelos disponíveis

A CLI aceita `--engine marian` e `--engine pytorch`.

### `marian`

O adaptador suporta estes checkpoints e direções conforme o catálogo:

- `Helsinki-NLP/opus-mt-en-es`: en↔es;
- `Helsinki-NLP/opus-mt-en-fr`: en↔fr;
- `Helsinki-NLP/opus-mt-tc-big-en-pt`: en↔pt;
- `facebook/m2m100_418M`: 22 direções de idiomas, configurando o idioma-fonte no tokenizer e forçando o token do idioma-alvo.

### `pytorch`

O caminho PyTorch suporta `facebook/nllb-200-distilled-600M`, `facebook/mbart-large-50-many-to-many-mmt`, T5 compatível e `facebook/m2m100_418M`. Para M2M100, a origem é configurada no tokenizer e o idioma de destino é definido com `forced_bos_token_id`.

### Direções declaradas para M2M100

O catálogo do Poliglota limita o modelo a en↔es, en↔fr, en↔pt, pt↔es, pt↔fr, pt↔de, pt↔ja, pt↔ko, pt↔it, pt↔ru e pt↔pl. Essas 22 direções foram exercitadas com o adaptador Marian em inferência local; cinco direções representativas também passaram em CPU. Uma amostra real passou pelo caminho PyTorch. Isso valida a configuração técnica dessas chamadas, não certifica a qualidade linguística de todos os pares.

## 3. Seleção automática de modelo

O catálogo atual define a prioridade em runtime:

1. `Helsinki-NLP/opus-mt-en-es`
2. `Helsinki-NLP/opus-mt-en-fr`
3. `Helsinki-NLP/opus-mt-tc-big-en-pt`
4. `facebook/nllb-200-distilled-600M`
5. `facebook/m2m100_418M`

Quando `--model` é omitido, o runtime percorre o catálogo compartilhado em ordem de prioridade e escolhe o primeiro modelo compatível. Em modo offline, considera apenas referências presentes no cache. `supports()`, validação do adaptador e catálogo retornam as direções do modelo selecionado; pares ausentes falham com mensagem clara.

## 4. Dispositivos suportados

As opções principais da GUI e CLI são `Automático (recomendado)`, `cpu` e `gpu`. A GUI exibe nomes amigáveis de hardware. A CLI mantém também `cuda[:index]` e `mps` como opções técnicas compatíveis. `auto` prefere CUDA, depois MPS e usa CPU como fallback; `gpu` exige um backend de GPU compatível e falha se não estiver disponível; `cpu` força CPU.

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
