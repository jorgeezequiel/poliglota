# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota SemVer para os metadados do pacote.

> A versão `0.0.1` ainda não possui tag nem release publicada; por isso não há data de lançamento associada.

## [0.0.1]

### Adicionado

- Pacote Python `poliglota` com CLI para validação, sincronização, descoberta de locales e tradução local.
- Adaptadores de formato para ARB, JSON, YAML e XML, registrados em um registry extensível.
- Motores de tradução opcionais Marian (padrão) e PyTorch, com seleção de dispositivo `auto`, `cpu`, `cuda`, `mps` e `gpu`.
- Seleção automática de modelo padrão por par de idiomas, com substituição por `POLIGLOTA_DEFAULT_MOTOR`.
- Cache de respostas opcional em memória, habilitado por `POLIGLOTA_ENABLE_TRANSLATION_CACHE`.
- Validação de glossário e proteção de placeholders no fluxo de tradução.
- Comando `validate` com verificações de chaves, placeholders e glossário.

### Alterado

- Versão alinhada entre `pyproject.toml`, `poliglota/__init__.py` e o arquivo `VERSION`.
- CI reescrito como matriz real de Windows, Ubuntu e macOS com Python 3.11, 3.12 e 3.13, incluindo lint, formatação, consistência de versão e relatórios JUnit.
- Documentação pública (README e guias) reescrita em português do Brasil com comandos verificados.

### Corrigido

- Comandos de exemplo da CLI que usavam a opção inexistente `--text` foram substituídos pelo argumento posicional `text`.
- Documentação corrigida para refletir a seleção real de modelo padrão (`Helsinki-NLP/opus-mt-*`), os formatos efetivamente registrados (ARB, JSON, YAML e XML) e a ausência de um comando de download de modelos.
- Anotação de tipo indefinida no adaptador XML (`Element`), que não afetava a execução por causa de `from __future__ import annotations`, mas era um erro de lint.
- O pacote `poliglota.quality` era declarado em `[tool.setuptools] packages` mas não possuía `__init__.py`; o arquivo foi adicionado para manter instalação e imports consistentes.

### Observações

- Nenhum modelo, peso ou tokenizer é distribuído neste repositório.
- A stack de ML permanece opcional por meio do extra `[gpu]`.

## [Não lançado]

- Sem mudanças pendentes no momento.
