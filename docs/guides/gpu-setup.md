# Guia Setup GPU Poliglota

> Aviso: suporte GPU no Poliglota é experimental e o comportamento padrão é tentar usar GPU primeiro e cair para CPU automaticamente quando a GPU não estiver disponível, não for compatível ou não houver memória suficiente.

## O que é GPU Acceleration?

O suporte a GPU no Poliglota acelera a inferência de tradução local usando PyTorch em dispositivos NVIDIA, AMD ROCm e Apple MPS quando disponíveis. Em cenários reais, o ganho de desempenho está na faixa de 4x a 10x em comparação com CPU para modelos pequenos e médios, especialmente em lotes de texto repetidos ou em pipelines de localização.

A auditoria do projeto com `t5-small` mostrou que a GPU manteve latência muito menor com lotes pequenos:

- batch 1: 428 ms
- batch 4: 431 ms
- aceleração observada no mesmo benchmark: 3.98x a 4.82x em comparação com CPU
- uso de VRAM: cerca de 244 MB em batches pequenos e até ~324 MB em cenários maiores

Isso significa que, para desenvolvimento e validação locais, a GPU pode reduzir bastante o tempo de tradução de arquivos de localização e a espera na iteração de correções.

Para contexto de arquitetura e contratos do projeto, veja:

- [Arquitetura do projeto](../architecture/overview.md)
- [Guia do motor de tradução](translation-engine.md)
- [README do projeto](../../README.md)

## Requisitos

### Requisitos mínimos

- Python 3.10+
- PyTorch 2.7.0+
- Transformers 4.35+
- NVIDIA GPU com compute capability 3.5+
- CUDA 12.8+
- cuDNN compatível com a versão do CUDA
- espaço em disco para cache de modelos do Hugging Face
- RAM suficiente para o modelo e o batch atual

### Requisitos por plataforma

| Plataforma | Suporte | Recomendação |
| --- | --- | --- |
| Windows + NVIDIA | ✅ recomendado | NVIDIA driver + CUDA 12.8 + cuDNN |
| Linux + NVIDIA | ✅ recomendado | CUDA 12.8 + cuDNN + driver NVIDIA |
| Linux + AMD ROCm | ⚠️ experimental | ROCm habilitado no kernel e PyTorch ROCm |
| macOS + Apple Silicon | ⚠️ experimental | MPS via PyTorch Metal |
| CPU-only | ✅ obrigatório | fallback automático quando GPU não estiver disponível |

### Importante sobre GPU

- O suporte a NVIDIA é o mais maduro e mais bem validado.
- O Poliglota faz detecção automática do dispositivo e tenta GPU primeiro.
- Se o modelo exigir mais VRAM do que está disponível, o sistema recua para CPU para não quebrar a execução.
- O suporte experimental não é garantia de desempenho igual em todos os hardwares.

## Instalação

### Instalação rápida

```bash
pip install poliglota[gpu]
```

Se você estiver trabalhando no repositório localmente:

```bash
python -m pip install -e ".[gpu]"
```

### Windows

1. Instale o driver NVIDIA mais recente.
2. Instale CUDA 12.8+ e cuDNN compatíveis com o seu driver.
3. Instale o pacote com suporte a GPU:

```powershell
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install "poliglota[gpu]"
```

4. Confirme se o PyTorch reconhece a GPU:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA unavailable')"
```

### Linux

Para CUDA em Linux:

```bash
python -m pip install --upgrade pip
python -m pip install "poliglota[gpu]"
```

Certifique-se de que:

- o driver NVIDIA está instalado;
- o toolkit CUDA 12.8+ está disponível no PATH;
- o cuDNN está instalado e encontrado pelo runtime;
- o ambiente do Python usa a build correta do PyTorch para CUDA.

Para AMD/ROCm:

```bash
python -m pip install "poliglota[gpu]"
```

Mas em geral o suporte ROCm precisa de um ambiente PyTorch ROCm específico e pode exigir ajustes do sistema. Use isso apenas quando você souber o que está fazendo.

### macOS

Em macOS com Apple Silicon, o suporte usa MPS:

```bash
python -m pip install "poliglota[gpu]"
```

Se o PyTorch Metal não estiver funcional no ambiente, o Poliglota faz fallback para CPU. O MPS é útil para testes locais, mas nem sempre é o melhor caminho para batch grande ou modelos pesados.

## Configuração Básica

### Flags da CLI

Os principais argumentos da CLI são:

```bash
poliglota translate "Olá mundo" --source pt_BR --target en_US --device auto
poliglota translate "Olá mundo" --source pt_BR --target en_US --device cuda
poliglota translate "Olá mundo" --source pt_BR --target en_US --device cpu
poliglota translate "Olá mundo" --source pt_BR --target en_US --batch-size 8
```

Parâmetros relevantes:

- `--device auto|cuda|cpu`: define o dispositivo preferido.
- `--batch-size N`: controla o número de textos por lote.
- `--source` e `--target`: define o par de idiomas.
- `--engine pytorch` ou `POLIGLOTA_ENGINE=pytorch`: usa o engine PyTorch quando necessário.

### Variáveis de ambiente

Use as variáveis abaixo em ambientes de desenvolvimento ou CI:

```bash
export POLIGLOTA_ENGINE=pytorch
export HF_HUB_OFFLINE=1
```

Exemplos:

```bash
POLIGLOTA_ENGINE=pytorch poliglota translate "Olá mundo" --source pt_BR --target en_US --device auto
HF_HUB_OFFLINE=1 poliglota translate "Olá mundo" --source pt_BR --target en_US --device cuda
```

### Detecção automática de dispositivo

O Poliglota tenta resolver o melhor dispositivo em ordem de prioridade:

1. CUDA, quando disponível
2. MPS, quando disponível
3. CPU, como fallback obrigatório

Esse comportamento evita falhas em máquinas sem GPU e mantém o comando funcionando mesmo com hardware limitado.

## Verificação

Valide a instalação com um comando curto e simples:

```bash
poliglota translate --device auto "test" --source pt_BR --target en_US
```

Se a configuração estiver correta, o comando deve rodar sem erros, escolher a GPU quando disponível e cair para CPU quando não houver suporte adequado.

Também vale testar a sua configuração em Python:

```bash
python -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('device_count', torch.cuda.device_count())"
```

Se `torch.cuda.is_available()` sair como `True`, você está pronto para rodar inferência local em CUDA.

## Benchmarks

A auditoria do projeto foi executada com o modelo `t5-small` em um ambiente com `NVIDIA GeForce GTX 1050 Ti` e CUDA disponível.

### Resultados reais da auditoria

| Corpus | Batch | Tempo GPU | Throughput | VRAM pico | Observação |
| --- | ---: | ---: | ---: | ---: | --- |
| small | 1 | 429.61 ms | 2.33 textos/s | 244.20 MB | muito estável |
| small | 4 | 431.13 ms | 9.28 textos/s | 244.20 MB | boa eficiência em lote |
| medium | 1 | 899.15 ms | 1.11 textos/s | 251.32 MB | esperado para textos maiores |
| medium | 4 | 884.49 ms | 4.52 textos/s | 251.32 MB | batch útil |
| large | 1 | 3615.29 ms | 0.28 textos/s | 323.56 MB | maior custo por contexto |
| large | 4 | 2966.30 ms | 1.35 textos/s | 323.56 MB | melhor throughput em lote |

### Comparativo de aceleração

A auditoria também mediu a diferença de performance entre CPU e GPU. O resultado observado para `t5-small` foi:

- speedup de 3.98x a 4.82x em comparação com CPU no mesmo tipo de corpus
- latência em GPU mantida em ~428–431 ms para batch 1 e 4 em textos pequenos
- VRAM ocupada dentro de faixas moderadas, sem picos que bloqueiem a execução em uma GTX 1050 Ti 4 GB

### Interpretação prática

- Para textos curtos, GPU pode acelerar bastante a iteração local em CLI e scripts.
- Para textos longos ou lotes grandes, o custo de memória ainda precisa ser controlado.
- Em batches muito grandes, a GPU pode começar a estourar memória e o fallback para CPU ou redução do batch passa a ser necessário.

## Troubleshooting

### Problemas comuns e soluções

| Problema | Sintoma | Solução |
| --- | --- | --- |
| CUDA out of memory | O comando falha ao iniciar a inferência | reduza `--batch-size`, use `--device cpu`, ajuste o texto para batch menor |
| torch not installed | import error ou runtime sem PyTorch | `pip install poliglota[gpu]` ou `pip install torch transformers` |
| model not cached | erro ao carregar modelo localmente | faça download antes ou use `HF_HUB_OFFLINE=0` para baixar; em ambiente offline, use cache previamente validado |
| slow on GPU | GPU detectada, mas inferência parece lenta | verifique a VRAM, confirme se o modelo é compatível, reduza batch e escolha o modelo certo |
| unsupported device | `--device cuda` não funciona | confirme driver CUDA, compute capability e instalação correta do PyTorch com CUDA |
| GPU not detected | `torch.cuda.is_available()` retorna False | reinstale driver, CUDA e PyTorch com build CUDA correta |
| fallback to CPU | GPU existe, mas o Poliglota usou CPU | isso geralmente ocorre por VRAM insuficiente ou modelo incompatível; use `--device auto` e observe logs |

### Dicas de diagnóstico

```bash
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.device_count()); print(torch.version.cuda)"
```

Se `torch.cuda.is_available()` for `False`, o problema está no ambiente, no driver ou na build do PyTorch.

## Performance Tuning

### Seleção de batch size

Teste em ordem simples para encontrar o melhor ponto de equilíbrio:

```bash
poliglota translate "Olá mundo" --source pt_BR --target en_US --device auto --batch-size 8
poliglota translate "Olá mundo" --source pt_BR --target en_US --device auto --batch-size 16
poliglota translate "Olá mundo" --source pt_BR --target en_US --device auto --batch-size 32
```

Recomendação prática:

- batch 8: valor seguro para GPUs leves e laptops
- batch 16: normal em GPUs de entrada/média
- batch 32: útil em GPUs maiores, mas exige mais VRAM

Se o processo falhar com `CUDA out of memory`, reduza para 4, 2 ou 1.

### Seleção de modelo

- `t5-small`: melhor para ambientes com VRAM limitada e desenvolvimento local
- `mBART-50`: mais cobertura de idiomas, mas geralmente exige mais memória
- `M2M-100`/mBART em geral devem ser escolhidos com atenção ao tamanho do modelo e ao hardware disponível

Para uso diário em dispositivos menores:

```bash
POLIGLOTA_ENGINE=pytorch poliglota translate "Olá mundo" --source pt_BR --target en_US --device auto --batch-size 8
```

### Seleção de dispositivo

Use explicitamente o dispositivo quando quiser controlar comportamento:

```bash
poliglota translate "Olá mundo" --source pt_BR --target en_US --device cuda
poliglota translate "Olá mundo" --source pt_BR --target en_US --device cpu
```

Recomendação:

- `--device auto`: melhor para setup geral
- `--device cuda`: melhor quando você quer forçar GPU e saber que ela funciona
- `--device cpu`: útil para diagnóstico, modelos grandes e ambientes com VRAM insuficiente

## Exemplos

### 1) Texto único

```bash
poliglota translate "Olá mundo" --device cuda --source pt_BR --target en_US
```

### 2) Batch em shell

```bash
for text in "Olá mundo" "Atualização de perfil" "Erro de login" "Mensagem de boas-vindas"; do
  poliglota translate "$text" --source pt_BR --target en_US --device auto --batch-size 8
  echo "---"
done
```

### 3) Python API

```python
from poliglota.engines.pytorch_engine import PyTorchTranslationEngine

engine = PyTorchTranslationEngine("t5-small", device="auto")
engine.load_model(device="auto")

result = engine.translate("Olá mundo", "pt", "en")
print(result)
```

### 4) Verificação de ambiente com PyTorch

```bash
python -c "import torch; import os; print('CUDA', torch.cuda.is_available()); print('device', 'cuda' if torch.cuda.is_available() else 'cpu'); print('torch', torch.__version__)"
```

## Hardware Suportado

A tabela abaixo resume dispositivos normalmente usados e o status esperado. A linha mais importante para a auditoria real do projeto é a GTX 1050 Ti, que foi validada funcionando com CUDA.

| Dispositivo | VRAM | Compute Capability | Status |
| --- | ---: | ---: | --- |
| NVIDIA GTX 1050 Ti | 4 GB | 6.1 | ✅ validado funcionando |
| NVIDIA RTX 3080 | 10 GB | 8.6 | ✅ recomendado para inferência local mais rápida |
| NVIDIA RTX 4090 | 24 GB | 8.9 | ✅ ideal para modelos maiores e batch mais alto |
| AMD Radeon / ROCm | variável | n/a | ⚠️ experimental |
| Apple Silicon MPS | variável | n/a | ⚠️ experimental |
| CPU-only | n/a | n/a | ✅ obrigatório como fallback |

## FAQ

### A GPU funciona automaticamente?

Sim. O Poliglota tenta usar GPU automaticamente e faz fallback explícito para CPU quando a GPU não está disponível ou quando a memória requerida excede o hardware atual.

### O que acontece se a GPU não tiver memória suficiente?

O comando reduz a pressão de memória usando batch menor ou recua para CPU, conforme a configuração e o ambiente.

### Posso forçar CPU se quiser?

Sim:

```bash
poliglota translate "Olá mundo" --source pt_BR --target en_US --device cpu
```

### Preciso baixar modelos manualmente?

Nem sempre. O fluxo padrão usa o cache do Hugging Face. Se o modelo ainda não estiver em cache, o download pode acontecer automaticamente. Quando `HF_HUB_OFFLINE=1` é definido, a execução só aceita modelos já disponíveis localmente.

### Qual dispositivo eu devo usar?

- use `auto` para a maioria dos setups;
- use `cuda` quando quiser forçar NVIDIA;
- use `cpu` quando o objetivo for estabilidade ou baixa memória.

### Isso é produtivo para projetos reais?

Sim, principalmente para workflows locais e de automação. O ganho real depende do modelo, do tamanho do texto, do batch e da VRAM disponível. Em geral, modelos pequenos e pipelines de localização se beneficiam bastante da aceleração em GPU.

## Resumo

Se você quer rodar o Poliglota com melhor performance, a sequência ideal é:

1. instalar `poliglota[gpu]`;
2. verificar driver CUDA / MPS / ROCm;
3. testar com `--device auto`;
4. ajustar `--batch-size` se houver uso excessivo de memória;
5. manter `HF_HUB_OFFLINE=1` ao trabalhar em ambientes sem rede;
6. usar CPU como fallback confiável quando o hardware não conseguir rodar o modelo.

Para um ambiente mais seguro e previsível, execute sempre em `--device auto` e revise os logs de `torch.cuda.is_available()` e `CUDA out of memory` antes de planejar um batch maior.

Se você quiser detalhes do projeto e do design de arquitetura, consulte `docs/architecture/overview.md`. Se quiser saber mais sobre motores de tradução e instruções de uso, veja `docs/guides/translation-engine.md`.
