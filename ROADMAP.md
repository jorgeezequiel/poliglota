# ROADMAP do Poliglota

**Versão do documento:** 2.1
**Versão do produto:** `0.0.1` (inalterada)
**Data de referência:** 2026-10-26
**Natureza deste documento:** análise e planejamento. Não descreve código que ainda não existe como se existisse, não autoriza implementação e não altera a versão do projeto.
**Revisão 2.1:** corrige três afirmações da versão 2.0 refutadas na reauditoria — (a) a árvore de trabalho não estava limpa; (b) `--device gpu` é estrito no código **e** na documentação pública; (c) o defeito de cache offline deixou de ser hipótese e passou a fato verificado. Acrescenta defeitos encontrados na reauditoria (sync multiarquivo em JSON/YAML/XML, duplicação de placeholders no Marian, whitelist de modelos, conflitos internos da documentação) e atualiza o escopo das Fases 0 e 2.

---

## Regras de evidência usadas neste documento

Toda afirmação sobre o estado do projeto é classificada em uma das três categorias abaixo. Nenhuma fase pode ser aprovada com base em inferência, relatório não versionado ou expectativa.

| Classificação | Significado |
|---|---|
| **Fato verificado** | Comprovado por arquivo versionado, comando executado ou teste reproduzível nesta data. |
| **Hipótese** | Indício forte em código ou documentação, ainda sem reprodução controlada. Não pode fundamentar aprovação. |
| **Pendente** | Não foi possível verificar nesta análise. Exige validação antes de ser usado como critério. |

Fonte de evidência preferencial: repositório versionado (`git`), comandos reproduzíveis no ambiente do projeto e resultados de teste com saída registrada. Relatórios em `reports/` são **ignorados pelo Git** (`.gitignore`), não fazem parte do artefato distribuído e não podem ser a única prova de aprovação de uma fase.

**Comandos executados na revisão 2.1 (saída literal resumida):**

| Comando | Resultado |
|---|---|
| `python -m pytest -q --no-header` | `238 passed, 8 skipped in 1.80s` (Python 3.13.11) |
| `python -m ruff check poliglota tests` | `All checks passed!` |
| `python -m ruff format --check poliglota tests` | `47 files already formatted` |
| Inspeção do cache HF real | `models--Helsinki-NLP--opus-mt-en-es` presente em `~/.cache/huggingface/hub` |
| `_verify_offline_capability(..., HF_HUB_OFFLINE=1)` | `RuntimeError: Model cache not available for offline mode` |

Os 8 skips vêm de `tests/test_pytorch_engine.py` (torch ausente no interpretador usado). Nenhum teste falhou.

---

## A. Visão e escopo

### A.1 Problema

Projetos de software acumulam arquivos de localização em formatos diferentes (ARB, JSON, YAML, XML, Gettext, CSV). Validar chaves, preservar placeholders, sincronizar locales e traduzir conteúdo sem perder estrutura é um trabalho repetitivo, sujeito a erro e normalmente resolvido com ferramentas fragmentadas ou serviços remotos.

O Poliglota ataca esse problema de forma local: uma ferramenta que lê arquivos de localização, valida sua integridade estrutural, sincroniza chaves e traduz conteúdo com motores locais, mantendo o formato e o motor desacoplados da aplicação consumidora.

### A.2 Público-alvo

- Pessoas técnicas que mantêm repositórios com múltiplos locales e precisam de automação reprodutível.
- Pessoas não técnicas que precisam traduzir arquivos de localização sem editar JSON/YAML manualmente.
- Equipes que exigem execução offline, sem enviar conteúdo para serviços de terceiros.

### A.3 O que o produto deve ser

- Gratuito e de código aberto.
- Leve: consumo de disco, RAM, CPU e VRAM proporcional ao necessário.
- Focado em tradução de arquivos de localização, não em conteúdo genérico.
- Melhor do que substituição literal: deve preservar estrutura, placeholders, glossário e contexto de interface.
- Capaz de operar offline quando o modelo já estiver no ambiente do usuário.
- Utilizável por CLI e, em etapa posterior, por uma interface gráfica complementar.
- Modular por formato, sem prometer cobertura universal.
- Transparente sobre modelos, recursos, limitações e alterações que pode causar em arquivos.

### A.4 Fora de escopo

- Tradução em nuvem, assinatura, cobrança por uso e backend remoto.
- Gestão de projetos, colaboração multiusuário e fluxo editorial corporativo.
- Download automático de modelos ou dependência de rede para funcionar.
- Substituir a CLI pela GUI: a CLI permanece interface oficial.
- Suporte a todos os formatos do mercado sem necessidade real e manutenção contínua.

### A.5 Princípio de sequenciamento

A ordem das fases é deliberada: **qualidade linguística e confiabilidade do núcleo vêm antes da GUI**. Uma interface amigável sobre um fluxo de tradução que não preserva placeholders, não traduz arquivos e não tem qualidade medida apenas amplia o impacto do erro.

---

## B. Estado atual do projeto

### B.1 Estágio geral

**Fato verificado:** a versão oficial é `0.0.1`, declarada em `pyproject.toml`, espelhada em `poliglota/__init__.py` e no arquivo `VERSION`, com teste dedicado de consistência (`tests/test_version_consistency.py`). O projeto está em pré-1.0 e não garante estabilidade de API.

**Fato verificado:** o repositório está na branch `main`, com histórico de dois commits. A árvore de trabalho **não** está limpa: `git status --porcelain` retorna ` M ROADMAP.md`, porque este próprio documento foi modificado. Nenhum outro arquivo versionado aparece alterado. A afirmação da versão 2.0 de que a árvore estava limpa era incorreta.

### B.2 Arquitetura e organização do código

**Fato verificado:**

- Pacote `poliglota` com camadas separadas: `core`, `formats`, `engines`, `quality`, `gpu`, `config` e `cli`.
- `poliglota/core` contém contratos independentes de formato e motor (`Locale`, `TranslationRequest`, `TranslationResult`, `TranslationIssue`, protocolos de engine, formato e qualidade). Um teste (`tests/test_core_contracts.py`) impede importação de módulos de formato dentro de `core`.
- `poliglota/formats` contém adaptadores ARB, JSON, YAML e XML, além de registry.
- `poliglota/engines` contém motor Marian, motor PyTorch, cache de respostas e uma fila de requisições.
- `poliglota/quality` contém glossário, proteção de placeholders e validadores.
- Compatibilidade retroativa mantida por módulos de reexportação (`arb_reader.py`, `models.py`, `validator.py`, `syncer.py`).
- `poliglota/cli.py` é a camada de ligação e concentra a lógica de seleção de motor, dispositivo e verificação offline.

**Leitura crítica:** a separação de camadas é real e testada. Isso não implica maturidade funcional do fluxo completo de tradução.

### B.3 Formatos e maturidade

**Fato verificado:**

| Formato | Estado |
|---|---|
| ARB | Implementação de referência: parsing, descoberta, inferência de locale, validação de chaves e placeholders, sincronização com dry-run e round-trip. |
| JSON | Adaptador genérico registrado; validação específica limitada. |
| YAML | Adaptador genérico registrado; validação específica limitada. |
| XML | Adaptador genérico registrado, com leitura segura via `defusedxml`; validação específica limitada. |
| CSV | Sem adaptador. |
| Gettext (.po/.pot) | Sem adaptador. |

**Fato verificado:** `docs/supported-formats.md` e `docs/architecture/overview.md` declaram explicitamente que JSON, YAML e XML têm validação específica inferior ao ARB e que CSV/Gettext não têm adaptador.

**Consequência:** a matriz de formatos atual é suficiente para provar o desenho modular, mas não para afirmar cobertura de produção.

**Defeito verificado por inspeção de código (JSON/YAML/XML):** `sync_with_adapter` e `validate_with_adapter` correlacionam recursos de origem e destino por `resource.attributes.get("module")`. Os adaptadores JSON, YAML e XML registram apenas `attributes={"directory": ...}`, portanto `module` é `None` em todos os recursos. Com um único arquivo por locale o efeito é invisível; com dois ou mais arquivos por locale, todo arquivo de origem "casa" com todo arquivo de destino: a validação reporta chaves ausentes falsas e o sync copia chaves do arquivo errado. Os testes atuais usam um arquivo por locale e não cobrem o cenário. Reprodução em runtime ainda pendente.

### B.4 Motores e modelos

**Fato verificado:**

- Motores disponíveis: `marian` (padrão) e `pytorch`.
- O motor padrão é configurável por `POLIGLOTA_DEFAULT_MOTOR`; `POLIGLOTA_ENGINE` também é documentado.
- Seleção automática de modelo segue prioridade explícita no código, com `Helsinki-NLP/opus-mt-en-es`, `Helsinki-NLP/opus-mt-en-fr` e `Helsinki-NLP/opus-mt-tc-big-en-pt`. Na prática, a seleção automática cobre pares entre `en`, `es`, `fr` e `pt`; outros pares exigem `--model` ou `POLIGLOTA_DEFAULT_MOTOR`.
- O projeto não empacota modelos nem inclui pesos; o cache é responsabilidade do usuário. O código do Marian, porém, não força `local_files_only` (ver B.8).
- O caminho offline depende de `HF_HOME`/cache do Hugging Face e de `HF_HUB_OFFLINE=1`.
- Cache de respostas é opcional, em memória, desativado por padrão (`POLIGLOTA_ENABLE_TRANSLATION_CACHE`).
- `RequestQueue` existe como utilitário, mas **não está integrado ao caminho síncrono da CLI**.

**Fato verificado:** o motor PyTorch não aplica proteção de placeholders nem glossário durante a tradução; esses recursos existem na camada de qualidade e são usados em validação, mas não no fluxo de tradução desse motor. O motor Marian possui tratamento próprio de placeholders.

**Limite verificado (PyTorch):** `_SUPPORTED_PAIRS` restringe o motor a oito pares entre `en`, `pt`, `es` e `fr`. A afirmação de `docs/LIMITATIONS.md` de que ele aceita "qualquer modelo compatível" não corresponde ao código. O caminho PyTorch usa `local_files_only` quando `HF_HUB_OFFLINE` está ativo (comportamento correto), mas a CLI não executa a verificação preventiva de cache para esse motor.

**Defeitos e limites verificados por inspeção de código no motor Marian:**

- `MariansNMTAdapter.translate()` restaura os placeholders duas vezes: `_restore_known_placeholders()` já reinsere as tags e o laço seguinte (`if positions:`) reinsere as mesmas posições. Textos com `<en>`, `<pt>`, `<es>` ou `<fr>` produzem tags duplicadas. O fluxo da CLI mascara placeholders ARB antes de chamar o adaptador, o que oculta o defeito no caminho padrão, mas a API pública do motor está incorreta.
- `_SUPPORTED_MODELS` aceita apenas quatro identificadores (`opus-mt-tc-big-en-pt`, `opus-mt-en-es`, `opus-mt-en-fr`, `facebook/m2m100_418M`). Modelos citados nos benchmarks internos (`mBART-50`, `NLLB-200`) não podem ser selecionados por `--model` no motor Marian.
- `_SUPPORTED_PAIRS` declara `pt→de/ja/ko/pl/ru/it` via M2M100, mas `translate()` não força o token de idioma de destino (`forced_bos_token_id`/`get_lang_id`) e `_strip_known_placeholders` só reconhece tags en/pt/es/fr. O suporte multilíngue é nominal, não comprovado.

**Fato verificado:** os testes que exigem PyTorch são marcados como `skipped` quando a stack opcional não está instalada. No ambiente desta revisão (Python 3.13.11 no interpretador do sistema), a execução resultou em **238 passed, 8 skipped in 1.80s**, com os 8 skips vindos de `tests/test_pytorch_engine.py` por ausência de `torch`.

### B.5 Qualidade linguística

**Fato verificado:**

- Existe infraestrutura de qualidade testada: glossário (JSON/CSV, com fronteira de palavra), proteção de placeholders ARB (máscara/restauração/validação), validadores de chave, placeholder, glossário e estrutura composta.
- Existem testes dedicados: `test_quality_glossary.py`, `test_quality_placeholders.py`, `test_quality_validation.py`.
- Placeholders são detectados e protegidos **apenas no formato ARB**; formatos customizados exigem implementação própria.
- O glossário é aplicado por correspondência exata, com fronteira de palavra, sem tratamento de plural, gênero ou variação morfológica.

**Pendente / não comprovado:**

- Não há, no repositório versionado, corpus de avaliação linguística com revisão por falante nativo.
- Não há limiar formal de qualidade (adequação, fluência, terminologia) definido e aplicado como gate.
- Não há teste de regressão de qualidade de tradução com conjunto dourado versionado.

**Evidência interna disponível, porém insuficiente:** `reports/stress-test/results/FASE3_FINAL_REPORT.md` descreve 792 traduções (396 CUDA + 396 CPU), 100% de identidade entre dispositivos e avaliação heurística de 45 amostras com score agregado de 99,4%. O próprio relatório declara que a avaliação foi heurística/baseada em LLM, **não** por linguista independente. Além disso, `reports/stress-test/results/translation_quality_assessment.json` apresenta valores desalinhados entre chave e tradução e marca todos os critérios como aprovados de forma indiscriminada, o que impede tratá-lo como prova. Esses artefatos não são versionados (`reports/` está no `.gitignore`).

**Conclusão:** a qualidade linguística é o principal risco aberto do projeto e o principal bloqueio para a GUI.

### B.6 CPU e GPU

**Fato verificado (benchmark local, `reports/GPU_CPU_BENCHMARK_RESULTS.md`):**

| Item | Valor |
|---|---|
| GPU | NVIDIA GeForce GTX 1050 Ti |
| PyTorch | 2.7.0+cu128 |
| Transformers | 5.20.2 |
| Modelo do benchmark | `t5-small` (via caminho PyTorch) |
| Carga do modelo | ~2,83 s |
| small_batch1 | 429,61 ms; 2,33 textos/s; RAM ~1.143 MB; VRAM ~244 MB |
| small_batch4 | 431,13 ms; 9,28 textos/s; VRAM ~244 MB |
| medium_batch4 | 884,49 ms; 4,52 textos/s; VRAM ~251 MB |
| large_batch4 | 2.966,30 ms; 1,35 textos/s; VRAM ~324 MB |

**Leitura correta:** o benchmark comprova que o caminho PyTorch funciona em CUDA nessa máquina e mede custo de inferência de `t5-small`. Ele **não** comprova qualidade de tradução nem desempenho do motor Marian.

**Fato verificado:** existe fallback para CPU em erro de VRAM/OOM e redução adaptativa de batch no motor PyTorch.

**Fato verificado (reproduzido nesta revisão):** o fluxo de verificação offline não localiza modelos no cache real do Hugging Face. `_verify_offline_capability()` e `_select_default_motor._model_in_cache()` procuram `hub/<org>--<nome>`, mas o cache real usa `hub/models--<org>--<nome>`. Nesta máquina, `models--Helsinki-NLP--opus-mt-en-es` existe; ainda assim o predicado retorna `False` e, com `HF_HUB_OFFLINE=1`, a função levanta `RuntimeError("Model cache not available for offline mode")` mesmo com o modelo presente. Consequência: o modo offline do motor Marian é inutilizável na prática, e a seleção automática com `HF_HUB_OFFLINE=1` não encontra nenhum candidato. Correção obrigatória na Fase 2, com teste nos dois cenários (cache presente e ausente).

### B.7 Testes e CI

**Fato verificado:**

- Suíte sem rede: **238 passed, 8 skipped in 1.80s**, executada nesta revisão com Python 3.13.11 no interpretador do sistema (`C:\Users\Jorge\AppData\Local\Programs\Python\Python313\python.exe`). O `.venv` existe no repositório, mas não foi o interpretador usado.
- 15 arquivos de teste cobrindo CLI, contratos, formatos, motores (com mocks), dispositivos, qualidade e versão.
- `.github/workflows/ci.yml` define **2 jobs** (`quality` e `tests`); o job `tests` é uma matriz de 9 combinações (Ubuntu/Windows/macOS × Python 3.11/3.12/3.13). Contando as pernas da matriz, são **10 execuções**: 1 de qualidade (Ubuntu, Python 3.13: `ruff check`, `ruff format --check`, teste de consistência de versão) e 9 de teste. A expressão "10 jobs" do README é aceitável nessa contagem, mas imprecisa quanto à definição do YAML.
- A stack de ML não é instalada no CI; testes dependentes dela ficam `skipped`.

**Pendente:** a afirmação do README de que as 10 execuções estão aprovadas no GitHub Actions não foi verificada nesta sessão (sem acesso à rede). Deve ser confirmada por link do provedor antes de ser usada como evidência de fase.

### B.8 CLI e instalação

**Fato verificado:**

- Entry point `poliglota`, com quatro comandos: `validate`, `sync`, `list-locales`, `translate`.
- `translate` recebe o texto como argumento posicional e devolve a tradução de **um texto**, não de um arquivo de localização.
- Requisitos: Python `>=3.11`; dependências de runtime `defusedxml>=0.7.1` e `pyyaml>=6.0`; extra `[gpu]` com `torch>=2.7.0`, `transformers>=5.20.0`, `huggingface-hub>=0.20.0`, `sacremoses>=0.1.0`; extra `[dev]` com `pytest>=8.0` e `ruff`.
- A instalação documentada é `python -m pip install -e .`, sem download de modelos.

**Lacunas verificadas no código:**

1. **Não existe fluxo ponta a ponta de tradução de arquivos.** `validate`, `sync` e `list-locales` operam sobre recursos; `translate` opera sobre uma string. O produto ainda não traduz um arquivo ARB/JSON/YAML/XML preservando estrutura e gravando saída.
2. **Flags de validação não podem ser desativadas pela CLI.** `--preserve-placeholders`, `--check-keys` e `--check-placeholders` usam `action="store_true"` com `default=True`; o usuário não consegue obter `False` pela linha de comando.
3. **O motor PyTorch não preserva placeholders nem aplica glossário na tradução**, apesar de o CHANGELOG descrever proteção de placeholders no fluxo de tradução. O glossário também não é aplicado na tradução do Marian: só é validado em `validate --check-glossary`.
4. **O README promete ausência de download automático que o código não garante.** `AutoTokenizer.from_pretrained()`/`AutoModelForSeq2SeqLM.from_pretrained()` no Marian são chamados sem `local_files_only`; sem `HF_HUB_OFFLINE=1`, a biblioteca pode baixar o modelo. `docs/LIMITATIONS.md` reconhece isso ("Offline mode is NOT automatic"), mas o README afirma o contrário.
5. **Sync/validate multiarquivo em JSON/YAML/XML está incorreto** (ver B.3): a correlação por `module` é sempre `None` nesses adaptadores.
6. **`--device gpu` é estrito no código e na documentação** (`README.md` e `docs/guides/gpu-devices.md` dizem que dispositivos explícitos falham quando indisponíveis). Não há divergência a corrigir; a versão 2.0 deste roadmap estava errada nesse ponto. A decisão pendente é de produto: manter `gpu` estrito ou torná-lo alias permissivo.

### B.9 GUI

**Fato verificado:** não existe interface gráfica no repositório. Não há código de GUI, dependência de GUI, ponto de entrada gráfico nem testes de interface.

**Consequência:** a GUI é escopo futuro, não estado atual. Qualquer texto que a descreva como existente é impreciso.

### B.10 Documentação e limitações

**Fato verificado:** existem `README.md`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `LICENSE`, `docs/architecture/`, `docs/development/`, `docs/guides/`, `docs/supported-formats.md` e `docs/LIMITATIONS.md`.

**Divergências verificadas entre documentação e código:**

| Documento | Afirmação | Realidade verificada |
|---|---|---|
| `SECURITY.md` | "At this stage it has no runtime dependencies" | `pyproject.toml` declara `defusedxml` e `PyYAML` como dependências de runtime. |
| `CHANGELOG.md` | "Validação de glossário e proteção de placeholders no fluxo de tradução" | Glossário é validado apenas em `validate --check-glossary`; não é aplicado na tradução. Placeholders são protegidos no Marian, não no PyTorch. |
| `README.md` | "Nenhum modelo é baixado automaticamente... o comando falha com mensagem explícita" | Sem `HF_HUB_OFFLINE=1`, o Marian chama `from_pretrained` sem `local_files_only` e pode baixar. Além disso, o predicado de cache offline está errado (B.6), então com `HF_HUB_OFFLINE=1` o comando falha mesmo com o modelo presente. |
| `README.md` | Ferramenta traduz recursos de localização | `translate` traduz apenas um texto posicional; não há tradução de arquivo. |
| `docs/LIMITATIONS.md` | `--device gpu` é "alias for auto" e "never fails" | Código e `docs/guides/gpu-devices.md` tratam `gpu` como explícito e estrito. O próprio conjunto de docs se contradiz. |
| `docs/LIMITATIONS.md` | Marian suporta `fr → de`; PyTorch aceita "qualquer modelo compatível" | `_SUPPORTED_PAIRS` do Marian não contém `fr→de`; o PyTorch restringe a oito pares entre en/pt/es/fr. |
| `docs/architecture/overview.md` | Lista `json_adapter.py`, `yaml_adapter.py`, `xml_adapter.py` | Os arquivos reais são `json.py`, `yaml.py` e `xml.py`. |
| `docs/ARCHITECTURE_MULTIDEVICE_DESIGN.md` | Documento de design | O próprio arquivo declara "DESIGN APENAS (sem código implementado)"; não é estado atual. |
| Relatório `PHASE_D_EXECUTIVE_SUMMARY_FINAL.md` | M2M-100-418M como motor padrão | Código verificado usa `marian` com modelos `opus-mt` como padrão. |
| Relatório `FASE3_FINAL_REPORT.md` | `ResponseCache` e `RequestQueue` ausentes (design-only) | `poliglota/engines/response_cache.py` e `request_queue.py` existem e têm testes; o cache é opcional e a fila não está ligada à CLI. |

**Consequência:** a documentação pública precisa ser corrigida antes de ser usada como contrato de comportamento.

---

## C. Fases

As fases abaixo são sequenciais. Uma fase só começa quando a anterior for aprovada com evidência reproduzível. Nenhuma fase altera a versão `0.0.1`; mudança de versão é decisão separada, fora deste roadmap.

### Fase 0 — Linha de base verificável

**Objetivo:** estabelecer uma linha de base reproduzível do que existe hoje, corrigir divergências documentais e criar o gate mínimo de evidência.

**Escopo:**

- Congelar o estado atual: comando de teste, lint, formatação e versão, com saída registrada.
- Corrigir afirmações falsas ou desatualizadas em `SECURITY.md`, `CHANGELOG.md`, `README.md` e `docs/LIMITATIONS.md` (dependências de runtime, escopo real de `translate`, download automático, contrato de `--device gpu`, pares suportados por motor, proteção de placeholders por motor).
- Corrigir nomes de arquivos citados em `docs/architecture/overview.md` (`json_adapter.py` → `json.py`, etc.).
- Definir e documentar um protocolo único de evidência para aprovação de fase.
- Registrar explicitamente o que é fato, hipótese e pendência.

**Fora de escopo:** novas funcionalidades, mudança de comportamento, GUI, novos formatos.

**Dependências:** nenhuma.

**Evidências exigidas:**

- Saída literal de `python -m pytest -q` com contagem de aprovados/skips.
- Saída literal de `python -m ruff check poliglota tests` e `python -m ruff format --check poliglota tests`.
- Confirmação de que `VERSION`, `pyproject.toml` e `poliglota/__init__.py` permanecem em `0.0.1`.
- Link ou captura das 10 execuções de CI (1 job de qualidade + 9 pernas da matriz), ou declaração explícita de que não foi verificado.

**Critérios objetivos de aprovação:**

- Todos os comandos acima executados sem erro, ou cada falha preexistente documentada com causa e escopo.
- Nenhuma divergência documental conhecida permanece sem correção ou sem registro formal como pendência.
- Relatório de linha de base versionado (não apenas em `reports/`).

**Condições impeditivas:**

- Qualquer documento público descrevendo funcionalidade inexistente sem marcação de plano futuro.
- Uso de relatório não versionado como única prova.
- Alteração de versão.

**Resultado esperado:** um retrato confiável e reproduzível do estado real, aceito como ponto de partida por qualquer avaliador externo.

---

### Fase 1 — Qualidade da tradução

**Objetivo:** provar, com método verificável, que a tradução produzida é adequada para arquivos de localização — antes de investir em GUI.

**Escopo:**

- Definir corpus de avaliação versionado, representativo de UI (rótulos curtos, instruções, mensagens de erro, plurais, placeholders, termos técnicos, textos longos).
- Definir conjunto dourado com tradução de referência e critérios de aceitação.
- Implementar avaliação reproduzível offline (script versionado, sem rede), com métricas automáticas para estrutura e placeholders, e protocolo de avaliação humana para adequação/fluência/terminologia.
- Garantir que glossário e placeholders sejam aplicados **no fluxo de tradução**, não apenas na validação, em todos os motores suportados.
- Comparar motores e modelos candidatos sob o mesmo corpus e o mesmo ambiente.
- Documentar limites conhecidos: idiomas não latinos, plurais, gênero, morfologia, termos ambíguos.

**Fora de escopo:** GUI, novos formatos, tradução em nuvem, ajuste fino de modelos.

**Dependências:** Fase 0 aprovada; modelos disponíveis localmente para os pares avaliados.

**Evidências exigidas:**

- Corpus e conjunto dourado versionados, com licença compatível.
- Script de avaliação versionado e executável offline.
- Resultados brutos por par de idiomas, por motor e por modelo.
- Relatórios de revisão humana com identificação do revisor, idioma, quantidade avaliada e escala usada.
- Prova de que a execução não acessou a rede.

**Critérios objetivos de aprovação:**

- Zero perda de chave e zero perda/alteração de placeholder em 100% do corpus avaliado.
- Aderência de 100% aos termos obrigatórios do glossário no corpus.
- Média de adequação e fluência ≥ 4,0/5,0 por idioma avaliado, com nenhuma amostra crítica abaixo de 3,0.
- Nenhuma tradução vazia, truncada ou idêntica ao idioma de origem sem justificativa registrada.
- Resultado reproduzível: mesma entrada, mesmo modelo, mesmo dispositivo → mesma saída (ou divergência explicada e documentada).
- Relatório final com riscos remanescentes e recomendação explícita de avançar ou não.

**Condições impeditivas:**

- Avaliação apenas heurística ou feita pelo próprio autor do código sem revisão independente.
- Corpus pequeno, não versionado ou não representativo.
- Qualquer placeholder perdido ou qualquer chave ausente.
- Ausência de medição para idiomas não latinos.
- Uso de relatório em `reports/` como única evidência.

**Resultado esperado:** decisão fundamentada sobre qualidade, com limites claros, que autorize ou bloqueie a GUI.

---

### Fase 2 — Confiabilidade do núcleo

**Objetivo:** transformar a capacidade atual em um fluxo de tradução de arquivos seguro, previsível e integrável.

**Escopo:**

- Fluxo ponta a ponta: ler arquivo de localização, traduzir entradas, preservar estrutura/metadados e gravar saída.
- Escrita segura: nunca sobrescrever em caso de falha parcial; gravação atômica; modo dry-run; relatório de alterações.
- Correção das flags de validação que não podem ser desativadas.
- Decisão e documentação do contrato de `--device` (manter `gpu` estrito ou tratá-lo como alias), com fallback explícito.
- Verificação offline correta contra o layout real do cache do Hugging Face (`models--<org>--<nome>`).
- Proteção de placeholders e aplicação de glossário em todos os motores, com validação antes de gravar.
- Correção da duplicação de placeholders em `MariansNMTAdapter.translate()`, com teste dedicado.
- Correção da correlação de arquivos no sync/validate de JSON/YAML/XML (usar `directory`/caminho real em vez do `module` inexistente).
- Alinhamento entre whitelist de modelos, matriz de pares declarada e capacidade real de cada motor (ou redução da declaração).
- Códigos de saída e mensagens de erro estáveis, documentados e testados.
- Testes de regressão para cada correção, incluindo casos de falha.

**Fora de escopo:** GUI, novos formatos, mudanças de modelo, redesenho de arquitetura.

**Dependências:** Fase 1 aprovada.

**Evidências exigidas:**

- Testes automatizados cobrindo o fluxo de arquivo, falhas e escrita atômica.
- Execução manual reproduzível em pelo menos um projeto de exemplo versionado.
- Confirmação de comportamento offline com cache real e com cache ausente.
- Matriz de códigos de saída e mensagens.

**Critérios objetivos de aprovação:**

- Tradução de arquivo ARB ponta a ponta com estrutura, ordem de chaves, metadados e placeholders preservados.
- Nenhuma escrita parcial em cenário de erro induzido.
- Flags de validação configuráveis nos dois sentidos, com testes.
- `--device gpu`, `auto`, `cpu`, `cuda` e `mps` com comportamento igual ao documentado.
- Detecção offline correta nos dois cenários (modelo presente e ausente).
- Sync e validate de JSON/YAML/XML corretos com múltiplos arquivos por locale, cobertos por teste.
- Placeholders preservados sem duplicação na API do Marian e também no caminho PyTorch.
- Nenhum modelo ou par declarado sem suporte efetivo, ou declaração reduzida ao que é entregue.
- Suíte completa aprovada, sem novos skips injustificados.

**Condições impeditivas:**

- Qualquer caminho que possa corromper ou sobrescrever arquivo do usuário sem confirmação.
- Divergência entre comportamento e documentação.
- Correção aplicada apenas ao motor padrão, deixando outro motor inconsistente.

**Resultado esperado:** núcleo confiável o suficiente para ser operado por usuários não técnicos por meio de uma GUI.

---

### Fase 3 — GUI

**Objetivo:** oferecer interface gráfica local, amigável, sem remover nem reduzir a CLI.

**Escopo:**

- Aplicação desktop local, sem backend remoto e sem telemetria obrigatória.
- Fluxo guiado: selecionar raiz, detectar formatos/locales, escolher origem e destino, revisar prévia, traduzir, validar e gravar.
- Exibição clara de placeholders, glossário, avisos e erros.
- Revisão e edição antes da gravação; desfazer; dry-run visível.
- Acessibilidade: navegação por teclado, foco visível, contraste adequado, rótulos e leitura por tela.
- A GUI consome o núcleo, sem duplicar regra de negócio.

**Fora de escopo:** colaboração em nuvem, contas, sincronização remota, edição colaborativa.

**Dependências:** Fases 1 e 2 aprovadas.

**Evidências exigidas:**

- Demonstração reproduzível do fluxo completo em projeto de exemplo.
- Testes de interface para caminhos críticos e testes do núcleo reaproveitados.
- Checklist de acessibilidade com itens verificados.
- Prova de que a CLI continua funcionando de forma independente.

**Critérios objetivos de aprovação:**

- Fluxo completo executável sem terminal.
- Nenhuma regra de tradução/validação duplicada na GUI.
- Nenhuma operação destrutiva sem confirmação explícita e possibilidade de reverter.
- Checklist de acessibilidade aprovado.
- Paridade funcional: toda operação da GUI existe na CLI ou é explicitamente justificada.

**Condições impeditivas:**

- GUI que dependa de serviço remoto.
- GUI que bloqueie, substitua ou degrade a CLI.
- Funcionalidade presente apenas na GUI, sem caminho equivalente no núcleo/CLI.
- Fase 1 ou 2 não aprovada.

**Resultado esperado:** interface utilizável por público não técnico, apoiada em núcleo já validado.

---

### Fase 4 — Experiência completa

**Objetivo:** fechar o ciclo de trabalho do usuário, da configuração inicial à entrega dos arquivos traduzidos.

**Escopo:**

- Gestão de glossário pela interface e pela CLI, com importação/exportação.
- Perfis de projeto (origem, destinos, formato, modelo, dispositivo) persistidos localmente.
- Retomada de trabalho interrompido, com estado explícito.
- Relatórios de execução: alterações, avisos, itens não traduzidos, pendências.
- Empacotamento e instruções de instalação para os sistemas suportados.
- Onboarding e mensagens de erro orientadas à ação.
- Documentação de usuário revisada e alinhada ao comportamento real.

**Fora de escopo:** colaboração, nuvem, cobrança, marketplace de modelos.

**Dependências:** Fase 3 aprovada.

**Evidências exigidas:**

- Cenário ponta a ponta documentado e reproduzido.
- Testes de retomada e de relatório.
- Instalação verificada nos sistemas declarados.
- Documentação revisada contra o comportamento executado.

**Critérios objetivos de aprovação:**

- Fluxo completo executado por alguém sem conhecimento do código, seguindo apenas a documentação.
- Nenhuma perda de dados em retomada ou interrupção.
- Relatório final suficiente para auditar o que foi alterado.
- Instalação reproduzível nos sistemas suportados.

**Condições impeditivas:**

- Dependência de conhecimento interno não documentado.
- Instalação não reproduzível.
- Relatório que não permita reconstruir as alterações.

**Resultado esperado:** produto utilizável de ponta a ponta por público técnico e não técnico.

---

### Fase 5 — Expansão de formatos

**Objetivo:** ampliar a cobertura de formatos com o mesmo rigor, sem degradar o que já funciona.

**Escopo:**

- Gettext (.po/.pot) e CSV, se houver necessidade real comprovada.
- Estratégias de placeholder por formato (printf, ICU, chaves nomeadas), com testes dedicados.
- Tratamento de plural e gênero conforme o formato permitir.
- Documentação da matriz de suporte atualizada e honesta.
- Migração de formatos hoje genéricos (JSON/YAML/XML) para validação específica quando aplicável.

**Fora de escopo:** formatos sem necessidade comprovada; promessa de cobertura universal.

**Dependências:** Fases 1–4 aprovadas, ou decisão explícita de priorizar formatos antes da Fase 4, com registro do motivo.

**Evidências exigidas:**

- Especificação do formato e da estratégia de placeholder.
- Casos de teste de round-trip, validação, sync e tradução.
- Corpus de qualidade específico do formato.
- Documentação atualizada.

**Critérios objetivos de aprovação:**

- Round-trip sem perda para cada novo formato.
- Placeholders do formato preservados em 100% dos casos testados.
- Suíte existente sem regressão.
- Matriz de suporte coerente com o código.

**Condições impeditivas:**

- Novo formato sem estratégia de placeholder definida.
- Regressão em formatos já suportados.
- Documentação prometendo suporte não validado.

**Resultado esperado:** cobertura crescente e sustentável, guiada por necessidade real.

---

## D. Critérios de aprovação por fase

A tabela consolida o gate. Nenhuma fase pode ser marcada como concluída sem todos os itens aplicáveis.

| Fase | Objetivo | Escopo mínimo | Dependência | Evidência obrigatória | Critério objetivo | Condição impeditiva | Resultado esperado |
|---|---|---|---|---|---|---|---|
| 0 | Linha de base verificável | Testes, lint, versão, correção documental, protocolo de evidência | — | Saídas literais dos comandos; confirmação de versão; status de CI | Comandos executados; divergências corrigidas ou registradas; baseline versionado | Documento público descrevendo funcionalidade inexistente; prova baseada só em `reports/`; mudança de versão | Retrato confiável do estado atual |
| 1 | Qualidade da tradução | Corpus e conjunto dourado versionados; avaliação automática e humana; glossário/placeholders no fluxo | Fase 0 | Corpus, script, resultados brutos, relatórios de revisão, prova de execução offline | 0 perda de chave/placeholder; 100% de termos obrigatórios; adequação/fluência ≥ 4,0/5,0; nenhuma amostra crítica < 3,0; reprodutibilidade | Avaliação só heurística; corpus não versionado; qualquer placeholder perdido; ausência de idiomas não latinos | Decisão fundamentada que libera ou bloqueia a GUI |
| 2 | Confiabilidade do núcleo | Tradução de arquivo ponta a ponta; escrita atômica; flags; device; offline; sync multiarquivo; placeholders; erros | Fase 1 | Testes novos e de falha; execução manual em projeto de exemplo; matriz de erros | Estrutura/metadados/placeholders preservados; nenhuma escrita parcial; flags simétricas; device e offline conforme documentado; sync multiarquivo e placeholders corretos; suíte aprovada | Risco de corrupção/sobrescrita; comportamento divergente da documentação; correção só no motor padrão | Núcleo seguro para GUI |
| 3 | GUI | Fluxo completo sem terminal; revisão; acessibilidade; reaproveitamento do núcleo | Fases 1 e 2 | Demonstração reproduzível; testes de interface; checklist de acessibilidade; prova de CLI intacta | Fluxo completo sem terminal; zero duplicação de regra; operações destrutivas com confirmação; acessibilidade aprovada; paridade CLI/GUI | Dependência de serviço remoto; GUI que degrade a CLI; funcionalidade exclusiva da GUI; fases anteriores não aprovadas | Interface para público não técnico |
| 4 | Experiência completa | Glossário, perfis, retomada, relatórios, empacotamento, onboarding | Fase 3 | Cenário documentado; testes de retomada; instalação verificada; documentação revisada | Uso por terceiro só com a documentação; nenhuma perda em retomada; relatório auditável; instalação reproduzível | Conhecimento interno não documentado; instalação não reproduzível; relatório insuficiente | Produto de ponta a ponta |
| 5 | Expansão de formatos | Gettext/CSV e placeholders por formato; plurais quando aplicável | Fases 1–4 (ou repriorização registrada) | Especificação; testes de round-trip/validação/sync/tradução; corpus por formato | Round-trip sem perda; 100% de placeholders preservados; zero regressão; matriz coerente | Formato sem estratégia de placeholder; regressão; documentação não validada | Cobertura sustentável guiada por necessidade |

**Regra transversal:** toda fase exige suíte completa aprovada, lint/format aprovados, versão `0.0.1` preservada e nenhuma regressão em formatos ou motores já suportados.

---

## E. Marco de qualidade linguística

Este marco é **condição de entrada** para a GUI completa. Ele não é um relatório; é um gate.

### E.1 Objetivo do marco

Demonstrar, com evidência independente e reproduzível, que a saída do Poliglota é utilizável em interface real, e não apenas estruturalmente correta.

### E.2 Requisitos do marco

1. **Corpus versionado** com, no mínimo, 200 entradas por par de idiomas avaliado, cobrindo: rótulos curtos, frases completas, mensagens de erro, plurais, termos técnicos, placeholders, textos com pontuação e textos longos.
2. **Conjunto dourado** com tradução de referência revisada, armazenado no repositório, com licença compatível.
3. **Idiomas mínimos:** um latino próximo da origem, um latino distante e um não latino (por exemplo, `pt→es`, `pt→de`, `pt→ja`).
4. **Revisão humana independente:** pelo menos um revisor por idioma, sem participação na implementação avaliada, com escala explícita e amostragem registrada.
5. **Avaliação automática de estrutura:** chaves, placeholders, vazios, truncamento, idioma de saída e aderência ao glossário.
6. **Reprodutibilidade:** comando único documentado, ambiente declarado, modelo e versão registrados, execução sem rede.

### E.3 Limiares de aprovação

| Dimensão | Limiar |
|---|---|
| Integridade de chaves | 100% |
| Preservação de placeholders | 100% |
| Aderência a termos obrigatórios do glossário | 100% |
| Traduções vazias ou truncadas | 0 |
| Média de adequação (escala 1–5) | ≥ 4,0 |
| Média de fluência (escala 1–5) | ≥ 4,0 |
| Amostras críticas abaixo de 3,0 | 0 |
| Divergência entre execuções idênticas | 0, ou explicada e aceita formalmente |

### E.4 O que não conta como aprovação

- Score heurístico gerado pelo mesmo modelo que traduziu.
- Amostra sem revisão humana.
- Relatório em `reports/` sem versão no Git.
- Resultado de um único idioma.
- Corpus criado após a avaliação para justificar o resultado.

### E.5 Consequência

Enquanto o marco não for aprovado:

- a Fase 3 (GUI) não começa;
- nenhuma fase pode ser declarada concluída por “funcionar na prática”;
- o produto permanece em `0.0.1` com status de qualidade não comprovado.

---

## F. Critérios para avaliação externa

Um avaliador externo deve conseguir repetir a avaliação sem acesso privilegiado ao ambiente do autor.

### F.1 Reprodutibilidade

- Commit exato avaliado, identificado por hash.
- Instruções de ambiente: sistema operacional, versão de Python, dependências e extras.
- Comandos únicos para teste, lint, versão e avaliação de qualidade.
- Nenhuma dependência de rede, de cache oculto ou de arquivo fora do repositório.
- Modelos necessários descritos com origem, licença e forma de obtenção pelo avaliador.

### F.2 Evidência

- Saídas brutas dos comandos, com data e ambiente.
- Corpus, conjunto dourado e script de avaliação versionados.
- Relatórios de revisão humana com identificação, idioma, escala e quantidade.
- Matriz de resultados por par de idiomas e por motor.

### F.3 Critérios de aceitação externa

- O produto faz o que a documentação diz, sem interpretação.
- O fluxo de arquivo funciona ponta a ponta e não corrompe dados.
- Placeholders e chaves são preservados em 100% dos casos testados.
- A qualidade linguística atende aos limiares da seção E.
- A CLI funciona de forma independente da GUI.
- O comportamento offline é demonstrável nos dois cenários (modelo presente e ausente).
- Licenças de código e de modelos são compatíveis com o uso declarado.

### F.4 Critérios de rejeição

- Divergência entre documentação e comportamento.
- Evidência não reproduzível ou dependente de artefato não versionado.
- Qualquer perda de dados, chave ou placeholder.
- Dependência oculta de rede, telemetria ou serviço externo.
- Ausência de avaliação humana de qualidade.

---

## G. Riscos e limitações

### G.1 Fatos verificados

| Risco / limitação | Impacto | Estado |
|---|---|---|
| `translate` não traduz arquivos, apenas um texto posicional | Não existe fluxo de produto ponta a ponta; GUI não teria núcleo para consumir | Fato verificado |
| Motor PyTorch não preserva placeholders nem aplica glossário | Tradução pode quebrar interpolação e terminologia | Fato verificado |
| Flags de validação com `default=True` e `store_true` | Usuário não consegue desativar verificações pela CLI | Fato verificado |
| `--device gpu` é estrito no código e na documentação | Não é defeito; exige decisão de produto (manter estrito ou criar alias permissivo) | Fato verificado |
| Cache offline procura `hub/<org>--<nome>` em vez de `hub/models--<org>--<nome>` | Modo offline do Marian falha mesmo com modelo presente (reproduzido) | Fato verificado |
| `MariansNMTAdapter.translate()` reinsere placeholders duas vezes | Tags duplicadas na API pública do motor | Fato verificado por inspeção |
| Sync/validate JSON/YAML/XML correlacionam por `module` inexistente | Chaves erradas copiadas/reportadas com múltiplos arquivos por locale | Fato verificado por inspeção |
| Whitelist do Marian cobre 4 modelos; benchmarks citam mBART/NLLB | `--model` rejeita modelos usados nos relatórios internos | Fato verificado |
| Pares multilíngues do Marian (pt→de/ja/ko/pl/ru/it) sem token de destino | Alegação de suporte não comprovada | Fato verificado por inspeção |
| README nega download automático | `from_pretrained` sem `local_files_only` pode baixar | Fato verificado |
| `SECURITY.md` nega dependências de runtime | Informação de segurança incorreta | Fato verificado |
| Qualidade linguística sem avaliação humana versionada | Não há base para afirmar qualidade; bloqueia GUI | Fato verificado |
| Relatórios internos em `reports/` não versionados | Não servem como evidência de aprovação | Fato verificado |
| Relatórios internos divergem entre si e do código | Decisões podem ser tomadas sobre dados obsoletos | Fato verificado |
| Placeholders suportados apenas em ARB | Formatos genéricos não têm proteção equivalente | Fato verificado |
| Glossário sem plural/gênero/morfologia | Cobertura limitada para idiomas com flexão | Fato verificado |
| Sem CSV/Gettext | Cobertura de formatos incompleta | Fato verificado |
| Sem GUI | Público não técnico depende de terminal | Fato verificado |
| CI não instala stack de ML | Testes de PyTorch ficam `skipped` no CI | Fato verificado |
| Benchmarks cobrem `t5-small`, não o motor padrão | Desempenho do Marian não está medido | Fato verificado |

### G.2 Hipóteses a validar

| Hipótese | Consequência se confirmada | Como validar |
|---|---|---|
| M2M100 sem `forced_bos_token_id` pode gerar saída no idioma de origem | Pares pt→de/ja/ko/pl/ru/it declarados não funcionam | Executar cada par com `facebook/m2m100_418M` e verificar idioma de saída |
| `gpu` estrito é decisão de produto ainda não formalizada | Usuário pode esperar fallback; manutenção da documentação depende da decisão | Decidir e registrar o contrato; ajustar código ou docs |
| Relatórios de qualidade foram gerados com dados desalinhados | Conclusões de qualidade não são confiáveis | Refazer avaliação com corpus e script versionados |
| Pares fora de `en/es/fr/pt` declarados como suportados não produzem saída correta sem `--model` | Expectativa do usuário frustrada | Testar cada par declarado com modelo explícito e verificar idioma de saída |
| Performance em CPU é aceitável para arquivos grandes | Fluxo pode ser lento em máquinas sem GPU | Medir com corpus real e registrar tempo por 1.000 entradas |

### G.3 Limitações estruturais

- O projeto não empacota modelos; o usuário precisa providenciar cache e licenças. Sem `HF_HUB_OFFLINE=1`, a biblioteca Hugging Face pode baixar pesos, e o modo offline verificado está quebrado (B.6).
- A qualidade depende do modelo escolhido; o projeto não treina modelos.
- Idiomas não latinos exigem validação específica de tokenização e pontuação.
- A ausência de estabilidade de API em `0.0.1` significa que mudanças podem ocorrer entre versões.
- A GUI, quando existir, não pode se tornar dependência da CLI.

### G.4 Riscos de processo

- Declarar fase concluída com base em execução manual não registrada.
- Confundir “testes passando” com “produto validado”.
- Priorizar GUI antes de qualidade e confiabilidade.
- Aceitar relatório não versionado como prova.
- Corrigir documentação para coincidir com bug em vez de corrigir o bug (ou vice-versa) sem decisão explícita.

---

## Resumo executivo do roadmap

1. O projeto tem arquitetura coerente, testes verdes e base modular real.
2. O produto ainda **não traduz arquivos**: traduz um texto por vez.
3. A qualidade linguística **não está comprovada** por avaliação independente.
4. Existem divergências concretas entre documentação e código que precisam ser resolvidas na Fase 0.
5. A GUI é etapa posterior e só começa após qualidade (Fase 1) e confiabilidade (Fase 2).
6. A versão permanece `0.0.1`; nenhuma fase deste roadmap altera a versão.
7. Nenhuma fase pode ser aprovada sem evidência reproduzível e versionada.
8. A reauditoria de 2026-10-26 confirmou, por reprodução, que a verificação de cache offline está quebrada e encontrou defeitos adicionais no núcleo (duplicação de placeholders no Marian, sync multiarquivo em JSON/YAML/XML) e conflitos internos na documentação.
9. O caminho crítico permanece Fase 0 → Fase 1 → Fase 2; a Fase 0 já possui linha de base reproduzível registrada neste documento.
