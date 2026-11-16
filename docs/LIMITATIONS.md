# Limitações conhecidas do Poliglota

Este documento descreve o estado real do projeto, com foco em compatibilidade, comportamento local e escopo atual.

## 1. Formatos suportados

| Formato | Status |
| --- | --- |
| ARB | implementado e referência principal |
| JSON | implementado via adapter genérico |
| YAML | implementado via adapter genérico |
| XML | implementado via adapter genérico |
| CSV | não implementado |
| gettext | não implementado |

## 2. Tradução local

A tradução local só funciona quando o ambiente tiver:

- `torch` compatível com o runtime;
- `transformers` compatível com o modelo selecionado;
- modelo já presente no cache local do usuário;
- configuração correta do dispositivo.

O projeto não faz download automático do modelo nem promete funciona a partir de rede não preparada.

## 3. Modelos e catálogo

O catálogo declara direções por modelo e é usado pelos adaptadores e pela seleção padrão da CLI/GUI. Para `facebook/m2m100_418M`, o Poliglota expõe 22 direções: en↔es, en↔fr, en↔pt, pt↔es, pt↔fr, pt↔de, pt↔ja, pt↔ko, pt↔it, pt↔ru e pt↔pl. O checkpoint cobre mais idiomas, mas o Poliglota não declara esse suporte adicional.

As 22 direções M2M foram exercitadas com inferência local CUDA pelo adaptador Marian; cinco também foram executadas em CPU. O caminho PyTorch foi exercitado em amostras reais en→es e pt→es, em CPU e CUDA. Isso verifica configuração e execução do tokenizer/modelo, não qualidade profissional em cada par. Compatibilidade no catálogo não é garantia semântica. As traduções dos corpora QuestLog e PazCall continuam exigindo revisão, conforme os relatórios locais.

A resolução automática considera o par e a prioridade dos modelos. No modo offline, só escolhe candidatos presentes no cache. Pares não catalogados falham com mensagem explícita.

## 4. Dispositivo e GPU

### Opções da interface

A GUI mostra `Automático (recomendado)`, `CPU (nome do processador)` e `GPU (nome da placa)` quando há uma GPU compatível. Identificadores CUDA/MPS ficam internos. Se uma GPU física não puder ser usada pelo runtime, a interface a identifica como indisponível.

### CLI e resolução

- `auto` (padrão) tenta CUDA, depois MPS e usa CPU se nenhum desses backends estiver disponível;
- `cpu` força CPU;
- `gpu` exige uma GPU suportada e prefere CUDA a MPS;
- `cuda`, `cuda:N` e `mps` continuam disponíveis como seleções técnicas explícitas.

Pedidos explícitos de GPU falham com erro se o backend não estiver disponível. Não fazem fallback silencioso para CPU. Use `python -m poliglota devices` para ver os nomes detectados.

## 5. Offline

A execução em modo offline exige que a cache local contenha o modelo. Quando não houver cache, significa falha direta, não fallback silencioso.

## 6. Arquitetura atual

- a GUI é um wrapper sobre a CLI
- a CLI é a referência de comportamento
- formatos genéricos são menos completos que ARB
- suporte a locale depende de convenções de nome de arquivo e estrutura de diretório

## 7. Status do projeto

Poliglota está na versão `0.0.3`, com CLI, GUI e tradução local condicionada aos extras e modelos preparados pelo usuário. A qualidade varia por modelo, idioma, par e contexto; traduções produzidas automaticamente devem ser revisadas antes de uso público.

## 8. Referências

- [docs/guides/usage.md](guides/usage.md)
- [docs/guides/translation-engine.md](guides/translation-engine.md)
- [docs/guides/gpu-devices.md](guides/gpu-devices.md)
- [docs/supported-formats.md](supported-formats.md)
