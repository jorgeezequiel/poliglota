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

O catálogo do projeto define compatibilidade por par de idiomas e prioridade de modelos. A resolução automática depende do par e do modelo que estiver disponível em cache. Pares fora do catálogo exigem definição explícita do usuário.

## 4. Dispositivo e GPU

### `auto`

Tenta CUDA → MPS → CPU.

### `cpu`

Usa CPU exclusivamente.

### `cuda` / `mps`

Requer disponibilidade do backend solicitado. Se ele não estiver presente, a execução falha com erro explícito.

## 5. Offline

A execução em modo offline exige que a cache local contenha o modelo. Quando não houver cache, significa falha direta, não fallback silencioso.

## 6. Arquitetura atual

- a GUI é um wrapper sobre a CLI
- a CLI é a referência de comportamento
- formatos genéricos são menos completos que ARB
- suporte a locale depende de convenções de nome de arquivo e estrutura de diretório

## 7. Status do projeto

Poliglota está em desenvolvimento inicial (`0.0.2`), com funcionalidade real e limites explícitos. Isso significa que o projeto pode evoluir antes da 1.0, principalmente em áreas de API, qualidade e suporte de modelos.

## 8. Referências

- [docs/guides/usage.md](guides/usage.md)
- [docs/guides/translation-engine.md](guides/translation-engine.md)
- [docs/guides/gpu-devices.md](guides/gpu-devices.md)
- [docs/supported-formats.md](supported-formats.md)
