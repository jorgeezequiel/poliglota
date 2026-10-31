# Visão geral da arquitetura

Poliglota separa três pontos principais: formatos, motores de tradução e interface de execução. Essa divisão permite evoluir cada camada sem misturar o contrato de arquivo de localização com a lógica de inferência local.

## 1. Camadas do projeto

```text
poliglota/
├── core/
│   ├── locale.py
│   ├── translation.py
│   ├── engine.py
│   ├── format.py
│   └── quality.py
├── formats/
│   ├── arb.py
│   ├── json.py
│   ├── yaml.py
│   ├── xml.py
│   └── registry_init.py
├── engines/
│   ├── marian.py
│   ├── pytorch_engine.py
│   ├── response_cache.py
│   └── request_queue.py
├── quality/
│   ├── glossary.py
│   ├── placeholders.py
│   └── validation.py
├── cli.py
├── gui.py
├── gui_app.py
├── gpu.py
├── config.py
└── model_catalog.py
```

## 2. `core`

O pacote `poliglota/core` guarda contratos e estruturas genéricas. Ele não depende de ARB ou de qualquer engine específico. Esse desenho foi pensado para que os adapters novos e os motores novos possam evoluir sem acoplar a infraestrutura central a um único formato.

## 3. `formats`

Os adapters concretos vivem em `poliglota/formats`:

- `arb.py` — adapter de referência com suporte mais completo;
- `json.py` — leitura/escrita genérica de arquivos JSON;
- `yaml.py` — leitura/escrita genérica de arquivos YAML;
- `xml.py` — leitura/escrita genérica com `defusedxml`.

O registry em `registry_init.py` registra os adapters disponíveis no runtime.

## 4. `engines`

A parte de tradução local fica em `poliglota/engines`.

- `marian.py` é o path de motor local para modelos Marian/Opus-MT;
- `pytorch_engine.py` é o path alternativo com PyTorch;
- `response_cache.py` estabelece um cache opcional em memória;
- `request_queue.py` é uma utilidade adicional, mas não faz parte do caminho principal da CLI.

## 5. `quality`

A camada `quality` reúne verificações de domínio:

- glossário;
- placeholders;
- validação de estrutura e chaves.

## 6. `cli`

A CLI é a interface pública atual do projeto. Ela chama a camada de registros, adapters e engines para executar operações reais. Os comandos públicos do código atual são:

- `validate`
- `sync`
- `list-locales`
- `translate`
- `translate-project`
- `prepare-model`
- `gui`

## 7. `gpu` e catálogo de modelos

A detecção de dispositivos e o catálogo de compatibilidade fica separado em:

- `poliglota/gpu.py` — validação de dispositivo e geração de contexto de execução;
- `poliglota/model_catalog.py` — compatibilidade por par de idiomas e prioridade de modelos.

Esse desenho ajuda a manter a lógica de hardware e a lógica de escolha de modelo separadas da leitura/escrita de arquivos.

## 8. Limitações da arquitetura atual

- a lógica de locale depende do nome dos arquivos e do padrão do projeto;
- o modelo e a cache local continuam sendo requisitos de entorno do usuário;
- a CLI é a referência real, e a GUI é um wrapper visual em cima dela;
- o suporte a formatos genéricos tende a ser mais leve do que o suporte especializado de ARB.

## 9. Referências

- [docs/guides/usage.md](../guides/usage.md)
- [docs/guides/translation-engine.md](../guides/translation-engine.md)
- [docs/LIMITATIONS.md](../LIMITATIONS.md)
- [poliglota/cli.py](../../poliglota/cli.py)
