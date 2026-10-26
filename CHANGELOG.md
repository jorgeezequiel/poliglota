# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota SemVer para os metadados do pacote.

> A versão `0.0.1` ainda não possui tag nem release publicada; por isso não há data de lançamento associada.

## [0.0.1]

### Adicionado

- Pacote Python `poliglota` com CLI para validação, sincronização, descoberta de locales e tradução local.
- Adaptadores de formato para ARB, JSON, YAML e XML, registrados em um registry extensível.
- **Motores de tradução opcionais:**
  - **Marian** (padrão) — Helsinki-NLP, suporta pares `en↔es`, `en↔fr`, `en↔pt`.
  - **PyTorch** — Transformers/Hugging Face com dois backends:
    - **mBART** (`facebook/mbart-large-50-many-to-many-mmt`) — GPU (CUDA/MPS), 50+ idiomas, PT-BR incluído.
    - **NLLB** (`facebook/nllb-200-distilled-600M`) — CPU/GPU, 200 idiomas via ISO 639-3 (region-code normalization automática para `en-rGB` → `en`, etc.).
- Seleção de dispositivo `auto`, `cpu`, `cuda`, `mps` e `gpu` com fallback CPU explícito (sem fallback GPU→CPU silencioso).
- Seleção automática de modelo padrão por par de idiomas, com substituição por `POLIGLOTA_DEFAULT_MOTOR`.
- Cache de respostas opcional em memória, habilitado por `POLIGLOTA_ENABLE_TRANSLATION_CACHE`.
- Validação de glossário via `validate --check-glossary`.
- Proteção de placeholders em ambos motores Marian e PyTorch (mBART/NLLB).
- Comando `validate` com verificações de chaves, placeholders e glossário.
- **Processamento de corpus YAML** — tradução paralela mBART GPU + NLLB CPU com preservação de estrutura, UTF-8, placeholders e non_translatable.

### Alterado

- Versão alinhada entre `pyproject.toml`, `poliglota/__init__.py` e o arquivo `VERSION`.
- CI reescrito como matriz real de Windows, Ubuntu e macOS com Python 3.11, 3.12 e 3.13, incluindo lint, formatação, consistência de versão e relatórios JUnit.
- Documentação pública (README e guias) reescrita em português do Brasil com comandos verificados.

### Corrigido

- Comandos de exemplo da CLI que usavam a opção inexistente `--text` foram substituídos pelo argumento posicional `text`.
- Documentação corrigida para refletir a seleção real de modelo padrão (`Helsinki-NLP/opus-mt-*`), os formatos efetivamente registrados (ARB, JSON, YAML e XML) e a ausência de um comando de download de modelos.
- Anotação de tipo indefinida no adaptador XML (`Element`), que não afetava a execução por causa de `from __future__ import annotations`, mas era um erro de lint.
- O pacote `poliglota.quality` era declarado em `[tool.setuptools] packages` mas não possuía `__init__.py`; o arquivo foi adicionado para manter instalação e imports consistentes.
- Diagnóstico e correção documentados para o caso real do Windows: instalação do PyTorch quebrada por DLL de CUDA/cuDNN em ambiente global, resolvido com virtualenv limpo e reinstalação explícita do wheel CUDA compatível.
- **Motor PyTorch mBART**: Correção de atribuição `tokenizer.src_lang = source_lang_code` (atributo, não kwarg); validação 6/6 idiomas completada (GPU CUDA 100% funcional, UTF-8 confirmado).
- **Motor PyTorch NLLB**: Implementação de mapa ISO 639-3 (`eng_Latn` ao invés de `en_Latn`) e normalização de region-code (`en-rGB` → `en`, `en-rAU` → `en`, `pt-rPT` → `pt`) — ambos validados 100% com traduções semanticamente corretas.

### Observações

- Nenhum modelo, peso ou tokenizer é distribuído neste repositório.
- A stack de ML permanece opcional por meio do extra `[gpu]`.

## [Não lançado]

- Sem mudanças pendentes no momento.
