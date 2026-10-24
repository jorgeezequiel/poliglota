# Guia do motor de tradução offline

## Visão geral

O Marian-NMT é uma família de modelos de tradução neural offline desenvolvida pela equipe de pesquisa do Helsinki-NLP, especialmente por meio dos modelos Opus-MT. Em vez de depender de serviços externos, o Poliglota pode usar esse motor localmente para traduzir texto em ambientes sem internet ou com custos altos por requisição. Essa abordagem é útil para fluxos de desenvolvimento, validação de arquivos de localização e automação interna em projetos que precisam de previsibilidade e privacidade.

A vantagem principal do uso offline é a redução da dependência de APIs de terceiros e a possibilidade de rodar traduções em ambientes controlados. Isso mantém o processo reprodutível e reduz risco de limites de uso, latência externa e exposição de conteúdo sensível. O motor implementado no projeto segue esse princípio e usa um adaptador específico para encapsular a lógica de carregamento, validação e inferência do modelo.

## Arquitetura

O protocolo `MariansNMTTranslationEngine` define a superfície mínima esperada de um motor Marian: nome do engine, conversão de locale, suporte por par de idiomas, carregamento do modelo, tradução simples ou em lote, metadados e encerramento de recursos. Esse contrato permite trocar implementações sem afetar o restante da CLI ou do código de integração.

O adaptador `MariansNMTAdapter` aplica esse contrato e centraliza validações como pares suportados, dispositivos (`cpu`, `cuda`, `mps`) e preservação de placeholders. A CLI `poliglota translate` usa esse adaptador e converte os locales do projeto (`pt_BR`, `en_US`, etc.) para os códigos de idioma esperados pelo modelo, mantendo a interface de usuário simples.

## Modelos suportados

A implementação atual lista modelos Helsinki-NLP/Opus-MT conhecidos, incluindo:

- `Helsinki-NLP/opus-mt-tc-big-en-pt` — inglês → português
- `Helsinki-NLP/opus-mt-en-es` — inglês → espanhol
- `Helsinki-NLP/opus-mt-en-fr` — inglês → francês

Esses modelos variam de tamanho e custo de memória. Em geral, os modelos maiores demandam mais RAM e melhor suporte de GPU, enquanto variantes menores podem ser mais adequadas para ambientes de desenvolvimento com CPU limitado.

## Instalação

Para usar tradução neural local, instale as dependências opcionais do projeto:

```bash
pip install poliglota[ml]
```

Ou manualmente:

```bash
pip install torch>=2.0 transformers>=4.35 huggingface_hub>=0.20
```

Essas bibliotecas são opcionais porque o restante do projeto pode funcionar sem tradução offline. A instalação explícita evita que o ambiente de desenvolvimento precise baixar modelos ou executar inferência pesada em testes automatizados sem mocks.

## Uso

Exemplo de uso pela CLI:

```bash
poliglota translate --source en_US --target pt_BR --text "Hello, World!"
```

Também é possível chamar o adaptador em Python:

```python
from poliglota.engines.marian import MariansNMTAdapter

adapter = MariansNMTAdapter("Helsinki-NLP/opus-mt-en-es")
adapter.load_model(device="cpu")
print(adapter.translate("Hello, World!", "en", "es"))
```

## Performance

A inferência em CPU costuma exigir mais memória e tempo. Estimativas gerais: modelos pequenos podem funcionar com alguns gigabytes de RAM, enquanto variantes maiores podem exigir mais de 2–4 GB em uso real dependendo do batch size e do hardware. Em GPU, a latência pode cair significativamente, mas o uso de memória ainda precisa ser ajustado para evitar picos de consumo.

## Default Motor Selection

A seleção padrão do motor de tradução foi definida com base na análise de Phase D, em `reports/PHASE_D_ENGINE_SELECTION_CRITERIA.json` e `reports/PHASE_D_BENCHMARKS.json`. O motor recomendado como padrão econômico é `facebook/m2m100_418M` (M2M-100-418M), com score `9.85/10` na Phase D. Esse valor considera a combinação de licença permissiva, pegada de recursos reduzida, suporte offline e desempenho aceitável para uso em CLI e workflows de localização.

O critério dominante da Phase D foi o princípio de "Economic default, offline-capable, low-resource, useful quality > high-resource professional translation". Nesse contexto, o M2M-100-418M vence por equilibrar melhor qualidade útil, licença permissiva e footprint compacto, sem depender de infraestrutura externa. O padrão atual do Poliglota é, portanto, usar M2M-100-418M como motor primário e preferencial para traduções locais.

> Default Motor Selection: `M2M-100-418M` is the default engine in Phase E (score 9.85/10 in Phase D). It is the preferred offline option for production-friendly, low-resource workflows.

Se o par de idiomas não for suportado pelo M2M-100-418M, o sistema tenta automaticamente o `facebook/mbart-50-many-to-many-mmt` (mBART-50). A cadeia de fallback documentada é: `M2M-100-418M -> mBART-50 -> error`. A escolha do mBART-50 foi validada na Phase D como fallback secundário com score `9.0/10`, mantendo licença MIT e oferecendo suporte adequado para pares de idioma que o M2M não cobre.

> Fallback chain: If source-target pair not supported by M2M-100-418M, automatically tries mBART-50 (score 9.0/10). If no compatible path exists, the engine returns an error instead of silently degrading the translation.

### Comparativo dos motores atuais

| Motor | Licença | Parâmetros | Idiomas | Disco | RAM | Velocidade | Caso de uso |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M2M-100-418M | MIT | 418M | ~100 | ~840 MB | ~1.2 GB | ~1.5 textos/s | Padrão recomendado para CLI, workflows locais e localizações de produto |
| mBART-50 | MIT | ~610M | ~50 | ~1.5 GB | ~2.0 GB | ~1.2 textos/s | Fallback automático para pares fora do escopo do M2M |
| NLLB-200 | CC-BY-NC | 600M distilado | 200+ | ~2.4 GB | ~1.57 GB | ~1.09 textos/s | Pesquisa e uso pessoal; não recomendado para uso comercial |

A tabela acima reflete os dados da Phase D, onde as métricas foram ponderadas por licença, pegada de recursos, qualidade útil, capacidade offline e velocidade. A partir dessa comparação, o M2M-100-418M permanece o melhor equilíbrio econômico para o uso do Poliglota.

### Quando usar cada motor

- `M2M-100-418M`: padrão do projeto, com aproximadamente 100 linguagens, licença MIT e melhor custo-benefício. Recomendado para tradução local de arquivos de localização e para uso geral em CLI.
- `mBART-50`: fallback automático, com cerca de 50 idiomas e licença MIT. Útil quando o par de idiomas solicitado não é coberto pelo M2M-100-418M.
- `NLLB-200`: não recomendado para uso do Poliglota em cenários comerciais. `NLLB-200 uses CC-BY-NC license (research/personal use only, not commercial)`. O uso deve ficar restrito a pesquisas ou contextos pessoais, sem fins comerciais.

### Exemplos de CLI

O comportamento padrão deve seguir a seleção automática do modelo mais adequado:

```bash
poliglota translate --source pt_BR --target en_US "Olá mundo"
# usa M2M-100-418M automaticamente
```

Quando o usuário precisa forçar um motor específico, o comando aceita `--model`:

```bash
poliglota translate --source pt_BR --target en_US --model facebook/mbart-50-many-to-many-mmt "Texto"
# força mBART para esse par de idiomas
```

Para uso explícito em outros casos, a CLI também pode receber modelos em formato Hugging Face, desde que o driver do motor e o cache local estejam disponíveis. A recomendação do projeto é: usar auto-selection por padrão e empregar `--model` apenas quando for necessário controlar a escolha manualmente.

## Offline Capability

A operação offline depende do cache do Hugging Face e da presença do modelo a ser carregado localmente. O comportamento esperado é seguir o padrão do Hub em modo offline, exigindo a variável `HF_HUB_OFFLINE=1` quando o ambiente não deve consultar a internet para resolver pesos, arquivos de tokenizer ou metadados.

```bash
HF_HUB_OFFLINE=1 poliglota translate --source pt_BR --target en_US "Olá mundo"
```

Isso garante que a inferência não tente acessar o Hub em execução. Em ambiente sem rede, o download inicial do modelo precisa ter ocorrido em um momento anterior, ou a execução do comando vai falhar com erro de modelo ausente no cache local. A Phase D considera essa funcionalidade como requisito obrigatório para qualquer motor de tradução offline.

## Resource Footprint

Os motores escolhidos para a implementação atual têm consumo de disco e memória que precisa ser observado antes da execução em ambientes limitados.

- `M2M-100-418M`: cerca de `840 MB` em disco e `~1.2 GB` de RAM carregada; é a opção mais econômica.
- `mBART-50`: cerca de `1.5 GB` em disco e `~2.0 GB` de RAM; ainda aceitável, mas exige mais atenção.
- `NLLB-200`: cerca de `2.4 GB` em disco e `~1.57 GB` de RAM; o consumo mais alto entre os 3 e a recomendação de uso é restrita.

Avisos de uso:

- Modelos acima de `2 GB` exigem atenção explícita antes de execução, especialmente em laptops, CI ou containers com pouca memória disponível.
- Em ambientes de CPU comum, o overhead de inferência pode exceder o consumo nominal do modelo em términos de memória ativa.
- O uso em lote grande ou em vários processos simultâneos deve ser evitado para não causar oom ou queda de desempenho severa.
- Para execução em produção, o ideal é garantir RAM suficiente e controles de caching para evitar carga repetida no modelo.

## Limitações conhecidas

- O tamanho do batch deve ser ajustado com cuidado para evitar uso excessivo de memória.
- `cuda` e `mps` são aceitos apenas quando o runtime suporta o dispositivo solicitado.
- Tags e placeholders conhecidos precisam ser tratados com atenção para evitar perda de variáveis como `{name}`.
- O carregamento de modelos continua dependendo de arquivos locais ou do cache do Hugging Face, e não é um ambiente totalmente offline sem a presença do modelo instalado.

Em resumo, o motor Marian oferece uma forma prática de tradução local, mas exige disciplina na configuração do ambiente e no gerenciamento de memória e placeholders.
