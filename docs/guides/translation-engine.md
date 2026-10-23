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

## Limitações conhecidas

- O tamanho do batch deve ser ajustado com cuidado para evitar uso excessivo de memória.
- `cuda` e `mps` são aceitos apenas quando o runtime suporta o dispositivo solicitado.
- Tags e placeholders conhecidos precisam ser tratados com atenção para evitar perda de variáveis como `{name}`.
- O carregamento de modelos continua dependendo de arquivos locais ou do cache do Hugging Face, e não é um ambiente totalmente offline sem a presença do modelo instalado.

Em resumo, o motor Marian oferece uma forma prática de tradução local, mas exige disciplina na configuração do ambiente e no gerenciamento de memória e placeholders.
