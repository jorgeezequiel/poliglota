# Dispositivos e execução local

Este guia descreve como o Poliglota resolve CPU e GPU na parte de tradução local. Ele reflete o comportamento implementado no código atual, não uma promessa genérica de hardware.

## 1. Modelo de seleção

A resolução de dispositivo fica em `poliglota/gpu.py` e a CLI valida a escolha em `poliglota/cli.py`.

### Modo automático

```bash
poliglota translate --source pt_BR --target en_US --device auto "Olá, mundo!"
```

O comportamento real é:

- tenta CUDA primeiro;
- cai para MPS quando disponível;
- usa CPU como última opção.

### Dispositivo específico

```bash
poliglota translate --source pt_BR --target en_US --device cpu "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --device cuda "Olá, mundo!"
poliglota translate --source pt_BR --target en_US --device mps "Olá, mundo!"
```

Regras implementadas:

- `cpu` sempre usa CPU e não faz fallback para GPU;
- `cuda` exige CUDA disponível;
- `mps` exige MPS disponível;
- valores inválidos geram erro explícito.

## 2. Regras de erro

O projeto evita ocultar falhas de backend. Se a máquina não suportar o dispositivo solicitado, a execução falha com mensagem clara, em vez de trocar silenciosamente para algum outro backend.

## 3. Exemplos práticos

### Desenvolvimento flexível

```bash
poliglota translate --source pt_BR --target en_US "Olá, mundo!"
```

Esse é o fluxo padrão, que usa `auto`.

### Verificação estrita de GPU

```bash
poliglota translate --source pt_BR --target en_US --device cuda "Olá, mundo!"
```

Se CUDA não estiver disponível, o comando falha de forma explícita.

### CPU-only

```bash
poliglota translate --source pt_BR --target en_US --device cpu "Olá, mundo!"
```

Esse modo não tenta alternar para GPU.

## 4. Configuração de ambiente

Para executar offline após preparação do modelo:

```bash
export HF_HUB_OFFLINE=1
```

No PowerShell:

```powershell
$env:HF_HUB_OFFLINE = "1"
```

## 5. Limitações

- o resultado depende da disponibilidade real do hardware;
- a velocidade depende do modelo, do lote e da máquina;
- o projeto não promete suporte universal para todos os pares de idioma;
- a presença do modelo local em cache continua sendo requisito real.

## 6. Documentação relacionada

- [docs/guides/translation-engine.md](translation-engine.md)
- [docs/LIMITATIONS.md](../LIMITATIONS.md)
- [poliglota/gpu.py](../../poliglota/gpu.py)
- [poliglota/cli.py](../../poliglota/cli.py)
