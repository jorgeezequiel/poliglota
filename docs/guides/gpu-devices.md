# CPU e GPU na tradução local

## GUI

O seletor mostra `Automático (recomendado)`, o nome do processador em `CPU (...)` e o nome da placa em `GPU (...)` quando ela é utilizável pelo PyTorch instalado. O identificador técnico do backend não aparece como opção principal. Uma placa detectada, mas incompatível com o runtime, aparece como indisponível.

## CLI

Veja os dispositivos descobertos:

```text
python -m poliglota devices
```

Escolha processamento automático, CPU ou GPU:

```bash
poliglota translate --source pt_BR --target en_US --device auto "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --device cpu "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --device gpu "Olá, mundo!"
```

- `auto` prefere CUDA, depois MPS, e usa CPU se nenhum estiver disponível;
- `cpu` força CPU;
- `gpu` exige um backend de GPU compatível e prefere CUDA a MPS.

Os identificadores técnicos continuam disponíveis para diagnóstico e scripts existentes:

```bash
poliglota translate --source pt_BR --target en_US --device cuda:0 "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --device mps "Olá, mundo!"
```

Uma solicitação explícita de GPU indisponível falha com mensagem clara. O Poliglota não troca silenciosamente essa escolha por CPU. Use `auto` para permitir a seleção automática e o fallback previsto.

## Offline

Após preparar o modelo local, o modo offline pode ser forçado com `HF_HUB_OFFLINE=1`. A seleção do dispositivo não baixa modelos; a tradução exige que pesos e tokenizer já estejam no cache.

## Limitações

- a disponibilidade do backend depende do runtime PyTorch instalado, não apenas da presença física da placa;
- velocidade e memória dependem do modelo, do lote e do hardware;
- `auto` pode escolher CPU quando não houver GPU compatível;
- nem todo modelo do catálogo foi validado em hardware Apple ou AMD.

## Documentação relacionada

- [docs/guides/translation-engine.md](translation-engine.md)
- [docs/LIMITATIONS.md](../LIMITATIONS.md)
- [poliglota/hardware.py](../../poliglota/hardware.py)
- [poliglota/gpu.py](../../poliglota/gpu.py)
