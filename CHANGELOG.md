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

## [0.0.2]

### Adicionado

- GUI desktop em Tkinter para uso local, exposta via comandos `poliglota gui` e `poliglota-gui`.
- Inicialização headless da GUI para CI e testes sem sessão gráfica, sem ocultar a interface oficial da CLI.
- Wrapper visual mínimo que delega para as mesmas ações da CLI existente, preservando o comportamento canônico do terminal.

### Alterado

- O fluxo principal continua sendo a CLI; a GUI é opcional e não duplica regras de negócio nem redesenha a lógica de tradução.
- A seleção de dispositivo e a validação de cache/modelo continuam explícitas, sem download automático nem telemetria.

### Corrigido

- Detecção de MPS no macOS em runners virtualizados: a advertência de Metal 2.0 incompatível foi tratada como "backend indisponível", mantendo fallback seguro para CPU em vez de elevar falha no fluxo.
- Arrumação final do wrapper GUI para startup em ambiente sem display e para `ruff format --check` em `poliglota/gui_app.py`.

### Observações

- Nenhuma release/tag pública foi publicada para `0.0.2`.
- O comportamento offline, sem download e sem telemetria permanece preservado; requisitos de CUDA/modelo continuam visíveis para o usuário.

## [Não lançado]

### Adicionado

- **P3: conforto e robustez da GUI** — presets nomeados, histórico de projetos recentes, arrasto de pasta/arquivo para o campo do projeto, separação real de `stderr` e `stdout` na saída e objeto de job do Windows para finalizar a árvore de processo do CLI em caso de cancelamento ou timeout.
- **Presets e histórico de projetos**: o formulário pode salvar combinações nomeadas de opções e reusar rapidamente, enquanto a pasta do projeto é lembrada em histórico e sugerida na combobox do campo de projeto.
- **Drag-and-drop de pasta**: arrastar uma pasta para o campo de projeto é aceito quando `tkinterdnd2` está instalado; sem a dependência, a GUI simplesmente continua funcionando sem quebrar o fluxo.
- **Separação real de stderr**: linhas de erro da CLI são surfadas em um canal de erro e renderizadas com destaque colorido, sem misturar com o stdout normal.
- **Job object no Windows**: o processo filho da GUI agora é colocado em um job object e encerrado como um conjunto, evitando que subprocessos filhos sobrevivam ao cancelamento.
- **Persistência do formulário da GUI**: pasta do projeto, formato, locales, motor, dispositivo, modelo e `dry-run` são restaurados na sessão seguinte. O estado é gravado em `%APPDATA%\poliglota\gui_state.json` (Windows), `~/Library/Application Support/poliglota/gui_state.json` (macOS) ou `$XDG_CONFIG_HOME/poliglota/gui_state.json` (Linux), com autosave de 600 ms e gravação imediata ao fechar a janela.
- Novas opções `--state-file` e variável de ambiente `POLIGLOTA_GUI_STATE_FILE` para escolher outro arquivo de estado.
- **Validação em tempo real na GUI**: linha de status abaixo do formulário com `✓ Configuração válida.` ou `✗ <Campo>: <motivo>`, foco automático no primeiro campo inválido e bloqueio do comando enquanto houver pendência. Cobre pasta do projeto, locales de origem/destino, nome do modelo e texto de tradução.
- **Erros acionáveis na GUI**: falhas da CLI passam a ser classificadas em categorias com título em linguagem simples, sugestão de próximo passo e detalhes técnicos preservados.
- Log rotativo da GUI em `gui.log` (1 MB, 3 backups), na mesma pasta do arquivo de estado, criado apenas ao abrir a janela.
- Testes unitários para persistência (`tests/test_gui_config.py`), validadores (`tests/test_gui_validators.py`) e categorização de erros (`tests/test_gui_errors.py`), além de testes de integração da GUI.
- **Destaque visual de campos inválidos na GUI**: entradas com problema recebem o estilo `Invalid.TEntry` e voltam ao normal assim que o valor fica válido.
- **Atalhos de teclado na GUI**: `Enter` e `F5` validam, `Ctrl+O` abre o seletor de pasta e `Esc` cancela a operação em andamento.
- **Botão `Cancelar`** para encerrar comandos longos, com mensagem explícita na saída.
- **Progresso e streaming na GUI**: barra indeterminada durante a execução e saída da CLI exibida linha a linha (stdout e stderr mesclados em UTF-8), em vez de esperar o término do processo.
- **Tema claro/escuro** na GUI, aplicado em tempo real e lembrado entre sessões.
- **Geometria da janela lembrada** entre sessões, com normalização de tamanho e posição para nunca reabrir fora da tela.
- Testes da camada de apresentação em `tests/test_gui_view.py` (temas, geometria, destaque de campos, progresso e atalhos) e novos casos de streaming/cancelamento em `tests/test_gui_app.py`.
- **Tooltips na GUI**: campos, comboboxes, botões e o seletor de tema exibem dicas curtas ao passar o mouse, sem dependência externa.
- **Tempo decorrido na GUI**: a linha de status mostra `Validando recursos... (3.2s)` durante a operação, atualizada a cada 200 ms.
- **Área de saída somente leitura** com ações `Copiar`, `Salvar` (arquivo `.txt` em UTF-8) e `Limpar`, disponíveis inclusive durante a execução de um comando.
- **Confirmação ao fechar durante uma operação**: a janela pede confirmação antes de encerrar o processo em andamento.
- **Campo `Texto` multilinha** na GUI, sincronizado com o formulário e validado em tempo real quando preenchido.
- **Botão `Restaurar padrões`** na GUI, que devolve os campos aos valores iniciais preservando o tema atual.
- **Alta densidade de pixels no Windows**: reconhecimento de DPI (`SetProcessDpiAwareness`/`SetProcessDPIAware`) e ajuste do fator de escala do Tk ao DPI do monitor.
- Novos testes de tooltips, tempo decorrido, cópia/salvamento/limpeza da saída, confirmação de fechamento, restauração de padrões, alta densidade de pixels e texto multilinha.

### Alterado

- A GUI foi separada em apresentação (`poliglota/gui_view.py`) e comportamento (`poliglota/gui_app.py`), mantendo a CLI como fonte de verdade.
- A área de resultados passou a ser somente leitura; toda escrita é feita pela própria GUI, que desbloqueia o widget apenas durante a atualização.
- Ao reabilitar o formulário após um comando, os comboboxes voltam ao estado `readonly` em vez de ficarem editáveis.
- Comandos da GUI passaram a ter leitura incremental com limite de 300 segundos, encerrando processos travados com mensagem de tempo limite.

### Corrigido

- O comando `translate` da CLI voltou a usar o dispatcher canônico, evitando `TypeError` na execução do subcomando.
- Formatação e lint de `_run_translate_project` (espaços em linhas vazias, f-string sem placeholders, seção de docstring).

