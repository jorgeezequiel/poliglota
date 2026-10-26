# ROADMAP do Poliglota

## 1. Visão e escopo

### Problema resolvido
O Poliglota resolve um problema específico de engenharia de localização: validar, sincronizar e traduzir arquivos de recursos de forma local, com arquitetura desacoplada entre formatos, engines e CLI. O projeto não tenta ser uma plataforma genérica de tradução; ele foca em arquivos de localização, mantendo a lógica de formato separada da aplicação consumidora.

### Público-alvo
O produto se destina a usuários técnicos e não técnicos que precisam lidar com recursos de localização em múltiplos idiomas, especialmente em projetos que exigem consistência entre chaves, placeholders e conteúdo estruturado. O foco é uso local e controle do ambiente, incluindo a possibilidade de trabalhar com modelos já disponíveis no ambiente do usuário.

### O que o produto pretende ser
O Poliglota pretende continuar sendo uma ferramenta:

- gratuita e de código aberto;
- leve, com consumo proporcional ao necessário;
- apropriada para tradução local de arquivos de localização;
- melhor do que simples substituição literal ou tradução mecânica;
- capaz de operar offline quando o modelo e os recursos necessários já estiverem disponíveis localmente;
- adequada à linha de comando e, em uma etapa posterior, a uma interface gráfica adicional;
- modular para admitir novos formatos quando houver necessidade real e manutenção adequada;
- econômica em armazenamento, RAM, CPU e memória de GPU, dando prioridade a modelos compactos quando a qualidade for satisfatória;
- transparente sobre modelos, recursos, limitações e efeitos que podem modificar arquivos.

### Fora de escopo
O escopo atual e previsto não inclui:

- serviços de tradução em nuvem;
- assinaturas ou cobrança por uso;
- backend remoto ou orquestração centralizada;
- gestão de projetos, colaboração em nuvem, conteúdo editorial ou processos empresariais fora da tradução de arquivos de localização;
- suporte genérico a todos os formatos de conteúdo do mercado, sem necessidade real e manutenção adequada;
- downloads automáticos de modelos, execução silenciosa em rede ou dependência de infraestrutura externa para funcionamento normal.

### Por que a CLI continua sendo uma interface oficial
A CLI é uma interface oficial porque ela é a base de funcionalidade que a aplicação já expõe em código e documentação: validação, sincronização e tradução local. A arquitetura do projeto separa contratos de formato e motor da camada de comando, e a CLI funciona como a superfície principal de uso, integração em scripts e automação de tarefas. A interface gráfica, quando surgir, deve ser complementar e não substituir a execução por terminal. Isso preserva compatibilidade, automação, reprodução em ambientes headless e uso em máquinas sem interface gráfica.

---

## 2. Estado atual do projeto

### Estágio geral
O repositório está em estágio experimental, correspondente à versão `0.0.1`. A versão atual explícita no projeto é 0.0.1 e o estado documental indica desenvolvimento ativo, sem release pública e sem estabilidade de API garantida. A arquitetura existente é funcional e estruturada, mas não deve ser considerada comprovadamente madura em qualidade de tradução ou robustez de produção.

### 2.1 Arquitetura e organização do código
Estado comprovado:

- O pacote `poliglota` possui módulos bem separados por responsabilidade: `core`, `formats`, `engines`, `quality`, `gpu`, `config` e `cli`.
- A arquitetura do código segue o conceito de contratos independentes de formato e motor, com interfaces e protocolos centrais em `poliglota/core`.
- O projeto implementa adaptadores para ARB, JSON, YAML e XML, além de uma estrutura de registro de adaptadores em `poliglota/formats`.
- A CLI expõe comandos `validate`, `sync`, `list-locales` e `translate` e realiza a ligação entre adaptadores, validação e motor de tradução.
- O pacote inclui utilitários de qualidade para checklist de placeholders e glossário, além de validação funcional de chaves e conteúdos.

O que isso significa:

- O núcleo do projeto está organizado de forma coerente e modular.
- A separação de camadas é claramente um objetivo implementado, mas isso não equivale a maturidade funcional ou a qualidade de tradução validada.

### 2.2 Formatos de arquivos e maturidade
Estado comprovado:

- ARB é a implementação de referência e a mais completa: há suporte explícito para parsing, validação, sincronização e tradução.
- JSON, YAML e XML são suportados por adaptadores registrados, mas têm maturidade inferior ao ARB e operações genéricas em alguns fluxos.
- CSV e Gettext não têm adaptadores implementados.
- A documentação e as limitações do repositório indicam que YAML, JSON e XML estão em estágio experimental ou parcialmente validado, não como formatos maduros de produção.

Conclusão:

- A base de formatos é viável e útil.
- O suporte não é uniforme entre formatos.
- A expansão de formatos deve seguir necessidade real e validação, não uma promessa de cobertura completa.

### 2.3 Motores e modelos de tradução
Estado comprovado:

- O projeto implementa motores locais opcionais: Marian e PyTorch.
- O fluxo local depende do extra opcional `[gpu]` e exige modelos já disponíveis localmente, sem download automático.
- A CLI suporta seleção de engine e dispositivo (`auto`, `cpu`, `cuda`, `mps`, `gpu`) e o comportamento é documentado como permissivo em `auto` e estrito quando um dispositivo é pedido explicitamente.
- Há uma política clara de offline: o projeto exige cache local do Hugging Face e falha explicitamente se o modelo não estiver disponível em cache quando `HF_HUB_OFFLINE=1`.
- Há seleção automática de modelos por idioma com prioridade explícita, mas ela depende do par de idiomas e do modelo específico em cache.

Limitações provadas:

- A capacidade de tradução local é dependente do ambiente do usuário.
- O repositório não distribui modelos nem pesos.
- A compatibilidade real do modelo, idioma e hardware precisa ser validada no ambiente de execução.
- A documentação reconhece que a qualidade pode variar e que a presença de um motor funcional não garante qualidade linguística aceitável.

### 2.4 Qualidade linguística
Estado comprovado:

- Há validação de placeholders, chaves e glossário.
- Há infraestrutura para proteção de placeholders e consistência de ícones, nomes e marcações estruturais.
- O projeto não possui prova formal de qualidade linguística superior à tradução literal em pares reais, nem um benchmark oficial que ateste qualidade aceitável em múltiplos idiomas e contextos.
- Há documentação explícita de que uma tradução pode ser tecnicamente bem-sucedida e ainda ser linguisticamente ruim.

Conclusão:

- Existem mecanismos técnicos para controle de qualidade estrutural.
- A qualidade linguística ainda precisa ser validada por evidência real e não por inferência.
- Esse ponto é o principal bloqueador para a GUI completa e para qualquer avaliação externa mais ampla.

### 2.5 Uso de CPU e GPU
Estado comprovado:

- O projeto implementa detecção e seleção de dispositivo em nível de CLI e documentação.
- A arquitetura prevê uso de CPU, CUDA, MPS e GPU automática.
- O ambiente de CI não instala a stack de ML para evitar downloads pesados; a validação real de GPU permanece dependente do ambiente local.

Limitações provadas:

- O suporte a GPU não é validado automaticamente em CI.
- O uso de memória e desempenho depende de hardware e modelo.
- Não existe uma bancada oficial de benchmark que permita afirmar que a performance atual é aceitável de forma generalizada.

### 2.6 Testes automatizados e CI
Estado comprovado:

- O repositório possui suíte de testes em pytest.
- O CI executa lint, formatação, consistência de versão e testes cruzados em Windows, Ubuntu e macOS para Python 3.11, 3.12 e 3.13.
- O fluxo de CI publica relatórios JUnit de testes e valida a consistência de versão entre `pyproject.toml`, `VERSION` e `poliglota/__init__.py`.
- Há testes para CLI, adaptadores de formato, qualidade, dispositivos e contrato da arquitetura.

Importante:

- Os testes automatizados são essenciais e comprovam funcionalidade estrutural e de integração.
- Eles não substituem validação de qualidade linguística, nem de robustez em produção real.
- Testes de engine e GPU precisam ser considerados condicionais ao ambiente, e a documentação do projeto reconhece essa limitação.

### 2.7 CLI e experiência de instalação
Estado comprovado:

- A CLI está implementada e declarada no `pyproject.toml` como entrypoint `poliglota`.
- Há instalação via `pip install -e .` e extras opcionais para desenvolvimento e GPU.
- O uso de CLI está documentado, com comandos `validate`, `sync`, `list-locales` e `translate`.
- A instalação e operação real dependem de ambiente Python 3.11+ e dependências locais.

O que isso implica:

- A CLI é oficial e permanece indispensável.
- Ela é a interface principal do produto em sua fase atual.
- A experiência de instalação é simples, mas não elimina a necessidade de preparação local de modelos e recursos externos.

### 2.8 Interface gráfica
Estado comprovado:

- Não há implementação de interface gráfica ativa no repositório.
- Não há evidência de GUI funcional, dependências de GUI ou planejamentos concretos que impliquem uma tecnologia única definida.
- A visão do projeto afirma que a GUI deve ser adicional e não substituir a CLI.

Conclusão:

- A GUI é uma oportunidade futura, não uma funcionalidade atual.
- A decisão sobre tecnologia precisa ser feita com base na arquitetura real, custos de dependência, empacotamento e recursos adequados.

### 2.9 Documentação e limitações conhecidas
Estado comprovado:

- O repositório contém documentação pública, guias de instalação, arquitetura, motores, dispositivos e limitações.
- A documentação reconhece explicitamente que o projeto é experimental e que a qualidade de tradução e a compatibilidade de modelos precisam ser validadas em ambiente real.
- O documento `docs/LIMITATIONS.md` classifica ARB como referência e YAML/JSON/XML como experimentais ou parcialmente cobertos.

Conclusão:

- Há documentação suficiente para orientar uso e limites.
- O projeto não tenta esconder que o estado é experimental.
- A documentação é um recurso de alinhamento do roadmap, não uma garantia de maturidade funcional.

---

## 3. Fases de evolução

### Fase 0 — Estabelecer a linha de base
Objetivo:
Estabelecer o estado real do projeto, incluindo modelos disponíveis, idiomas cobertos, condições de execução, limites conhecidos e divergências entre documentação e comportamento comprovado.

Escopo:
- confirmar a arquitetura e o conjunto de comandos existentes;
- mapear formatos implementados e experimentais;
- documentar motores e modelos locais explicitamente suportados;
- registrar requisitos de CPU/GPU, offline e dependências opcionais;
- identificar lacunas entre código, documentação e suporte real.

Dependências:
- leitura de `README.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`, arquitetura e documentos de limites;
- revisão da suíte de testes e dos workflows de CI;
- análise de comando real e recursos de modelo e dispositivo.

Evidências necessárias:
- arquivos de documentação pública e de arquitetura;
- teste de consistência de versão;
- evidência de suporte por formato e motores;
- documento de limitações e relatórios relevantes.

Critérios objetivos de conclusão:
- a linha de base do projeto está documentada em arquivos rastreáveis;
- as capacidades e limitações são descritas sem inferências não confirmadas;
- versões, dependências e comportamentos reais são alinhados com código e CI.

Condições que impedem a aprovação:
- alegar suporte sem evidência de implementação ou teste;
- tratar documentação como verdade sem checagem do código;
- afirmar que qualidade linguística foi validada sem benchmark ou avaliação representativa.

Resultado esperado:
Uma linha de base confiável que permite decidir a próxima etapa sem presumir maturidade acima do real.

### Fase 1 — Validar a qualidade da tradução
Objetivo:
Avaliar se os motores e modelos produzem traduções adequadas para os idiomas e usos pretendidos, sem depender apenas de testes automáticos, velocidade ou semelhança entre CPU e GPU.

Escopo:
- definir corpus representativo e amostras de referência;
- comparar motores e modelos em CPU e GPU, quando disponíveis;
- registrar erros estruturais e linguísticos nos resultados;
- validar preservação de placeholders, chaves, números e formatação;
- definir critérios explícitos de aprovação antes da avaliação.

Dependências:
- linha de base da Fase 0;
- disponibilidade local real de modelos e ambiente de execução;
- corpus de avaliação e documentação de critérios.

Evidências necessárias:
- amostras representativas dos tipos de texto suportados;
- resultados de CPU e GPU em condições comparáveis;
- análise de qualidade linguística em relação aos objetivos do projeto;
- registro de falhas, truncamentos, textos vazios, placeholders alterados e mudanças indevidas.

Critérios objetivos de conclusão:
- a qualidade da tradução foi avaliada em referência a critérios definidos previamente;
- os resultados estão documentados e comparáveis entre motores/ambientes;
- a preservação de placeholders e estrutura é demonstrada;
- o projeto não avança para GUI com qualidade linguística ainda não validada.

Condições que impedem a aprovação:
- ausência de amostragem representativa;
- aprovação baseada somente em testes automatizados ou em execução sem contexto linguístico;
- ausência de comparação entre CPU e GPU quando disponível;
- falha em preservar placeholders, nomes, números ou estrutura.

Resultado esperado:
Uma conclusão factual sobre a qualidade da tradução, com evidência de que ela excede a simples substituição literal e atende ao objetivo do produto.

### Fase 2 — Consolidar a confiabilidade do núcleo
Objetivo:
Produzir confiança real nos fluxos existentes de validação, sincronização, descoberta de locales e tradução local, com foco em integridade de arquivos e comportamento offline.

Escopo:
- validar integridade dos arquivos gerados e alterados;
- confirmar comportamento com placeholders, chaves, glossários e estruturas de locale;
- verificar fluxo de sincronização e gravação de arquivos;
- reforçar tratamento de erros e comportamentos explícitos em casos de ausência de modelo ou ambiente incompatível;
- documentar as lacunas efetivamente encontradas na auditoria do projeto.

Dependências:
- Fase 1 concluída ou pelo menos com evidência clara de bloqueios linguísticos;
- uso real de modelos locais e arquivos de teste;
- ambiente de execução que permita validação funcional concreta.

Evidências necessárias:
- testes de regressão, cenários de erro, foco em gravação e sincronização;
- documentação de casos de falha e de recuperação;
- confirmação de que o comportamento offline e os dispositivos respeitam a política explícita do projeto.

Critérios objetivos de conclusão:
- os fluxos de validação e sincronização são estáveis;
- os placeholders e chaves são preservados;
- a operação em modo offline falha de forma previsível quando o recurso não está disponível;
- os riscos de modificação indevida de arquivos são conhecidos e controlados.

Condições que impedem a aprovação:
- alterações silenciosas em arquivos sem explicitação ao usuário;
- execução sem modelo local quando a operação exige modelo;
- ausência de regras claras para falhas de dispositivo, cache e modelo.

Resultado esperado:
Núcleo confiável, com processos que preservam integridade estrutural e controle explícito de recursos.

### Fase 3 — Desenvolver uma interface gráfica amigável
Objetivo:
Adicionar uma GUI como camada complementar à CLI, sem transformar a interface gráfica em requisito para uso por terminal.

Escopo:
- permitir seleção de arquivos ou pastas;
- oferecer escolha de idiomas e formatos suportados;
- apresentar prévia das mudanças antes de gravar;
- mostrar progresso e mensagens compreensíveis;
- manter operações demoradas fora do bloqueio total da interface;
- permitir gravação explícita e segura.

Dependências:
- Fases 0 a 2 concluídas ou com evidência suficiente para fundamentar a interação do usuário;
- decisão informada sobre tecnologia GUI, custos de dependência e compatibilidade com empacotamento;
- manutenção da CLI como interface oficial e não substituída.

Evidências necessárias:
- arquitetura de integração entre GUI e camada funcional atual;
- validação do impacto no processo de instalação e execução;
- avaliação da viabilidade de dependências e recursos do ambiente alvo.

Critérios objetivos de conclusão:
- a GUI usa a mesma lógica de núcleo do produto e não reimplementa regras de negócio;
- a instalação da GUI é opcional e não exige que a CLI deixe de funcionar;
- a gravação e a revisão de alterações são claras e seguras;
- o sistema continua compatível com uso local e offline quando adequado.

Condições que impedem a aprovação:
- tecnologia escolhida sem considerar arquitetura real e custo;
- GUI que reescreve ou contorna regras do núcleo;
- processo de gravação que não exija confirmação explícita;
- dependências pesadas ou não necessárias para o uso principal.

Resultado esperado:
Uma interface de uso amigável, complementar, segura e compatível com a CLI.

### Fase 4 — Validar a experiência completa
Objetivo:
Validar o fluxo completo do produto, do ambiente de instalação à tradução e gravação dos arquivos, mantendo a continuidade do uso da CLI.

Escopo:
- validar fluxo de instalação em ambiente alvo;
- verificar operação da CLI em cenários típicos;
- testar traduções e sincronização em arquivos reais;
- confirmar que a experiência não depende de condições ocultas nem de downloads automáticos.

Dependências:
- Fases 0 a 3 já concluídas ou com riscos explicitamente mapeados;
- garantia de que a documentação e os requisitos de instalação correspondem ao comportamento real.

Evidências necessárias:
- cenário real de uso do zero até gravação do arquivo;
- registro de tempo, recursos, falhas e correções necessárias;
- validação da continuidade da CLI após a introdução da GUI.

Critérios objetivos de conclusão:
- o fluxo completo é executável e documentado;
- os arquivos são alterados apenas quando o usuário aceita;
- a CLI continua funcionando para uso técnico e automatizado;
- a experiência global é consistente com a arquitetura do projeto.

Condições que impedem a aprovação:
- falhas de instalação ou ambiguidade de requisitos;
- uso de downloads silenciosos ou rede não explícita;
- operação completa que só funciona em um ambiente específico sem documentação adequada.

Resultado esperado:
Experiência comum validada para uso real, com documentação e limitações claras.

### Fase 5 — Avaliar a expansão controlada de formatos
Objetivo:
Permitir expansão futura para outros formatos de localização, mas apenas quando houver necessidade real, manutenção adequada e qualidade preservada.

Escopo:
- definir critérios para adicionar um novo formato;
- avaliar custo de manutenção, qualidade do adapter e necessidade para a comunidade ou usuários;
- priorizar formatos com impacto real no uso productivo;
- evitar a transformação do projeto em uma plataforma genérica de tradução.

Dependências:
- Fases 0 a 4 concluídas, com arquitetura estável e domínio bem entendido.

Evidências necessárias:
- análise da necessidade real do formato;
- estudo do impacto na arquitetura e na qualidade;
- manutenção contínua e critérios de compatibilidade com as regras do core.

Critérios objetivos de conclusão:
- novo formato só é adicionado quando traz valor real e preserva a clareza do projeto;
- a nova extensão não degrada a experiência atual;
- a qualidade e a manutenção são avaliadas antes da introdução.

Condições que impedem a aprovação:
- expansão por cobertura genérica sem necessidade;
- suporte a formatos com qualidade incerta ou manutenção impraticável;
- incompatibilidade com a visão restrita do produto.

Resultado esperado:
Um portfólio de formatos controlado, com alta qualidade e baixo acoplamento à aplicação.

---

## 4. Critérios de aprovação

### Critério geral
Uma fase não pode ser considerada concluída apenas porque o código foi escrito. A conclusão depende de evidências verificáveis, documentação de resultados e critérios explícitos definidos antes da avaliação.

Para cada fase, os critérios mínimos são:

- objetivo: a fase deve ter um propósito operacional e mensurável;
- escopo: precisa definir claramente o que entra e o que não entra;
- dependências: as dependências de entrada precisam ser identificadas;
- evidências necessárias: devem existir provas reais de execução, análise e reprodução;
- critérios objetivos: o que torna a fase aprovada deve ser específico e verificável;
- condições que impedem a aprovação: deve haver bloqueios claros para evitar aprovação artificial;
- resultado esperado: o que a fase entrega ao projeto deve ser explícito.

### Regras de bloqueio entre fases
Entre fases, o avanço deve ser impedido quando:

- a qualidade da tradução não estiver validada adequadamente;
- a integridade dos arquivos não tiver sido confirmada;
- a CLI e o núcleo não forem confiáveis no uso real;
- a GUI for considerada antes da maturidade funcional e da qualidade estrutural;
- houver dependência de downloads automáticos, rede não declarada, ou ambiente não documentado;
- a documentação para uso e instalação não refletir o comportamento real.

---

## 5. Marco de qualidade linguística

A qualidade de tradução deve ser tratada como critério funcional e de produto, não como efeito colateral da presença de código ou de testes automatizados. A produção de um texto “bem formatado” ou sem erros de execução não prova qualidade linguística.

### Qualidade linguística aprovada
A qualidade linguística pode ser considerada aprovada apenas quando houver evidência de que a tradução:

- preserva o significado original;
- é natural no idioma de destino;
- está gramaticalmente correta;
- mantém nomes, números, placeholders e indicadores de formatação;
- considera contexto de mensagens curtas e UI;
- evita texto não traduzido, truncado, vazio ou alterado de forma indevida;
- apresenta consistência em relação a referências humanas e revisões por pessoas competentes.

### Consistência entre CPU e GPU
Essa dimensão é diferente da qualidade linguística. Um resultado consistente entre CPU e GPU não prova qualidade de tradução; apenas indica previsibilidade de execução em diferentes dispositivos.

### Compatibilidade técnica do modelo
Compatibilidade técnica é outra dimensão: o modelo pode funcionar corretamente e ainda produzir tradução inadequada. A capacidade técnica de carregamento e execução não substitui a validação da qualidade da saída.

### Desempenho e consumo de recursos
Desempenho não deve ser tratado como equivalente a qualidade. O projeto prioriza eficiência, mas a otimização não pode sacrificar silenciosamente a qualidade da língua ou a integridade do arquivo.

### Regra de avanço
Se a qualidade linguística não for aprovada, o roadmap deve prever retorno à investigação do motor, do modelo ou da configuração da tradução. A fase não pode ser declarada concluída apenas porque a execução foi bem-sucedida do ponto de vista técnico.

---

## 6. Critérios para considerar o produto pronto para avaliação externa

Antes de recomendar uso por usuários não técnicos ou avaliação externa, o projeto deve atender a critérios objetivos:

- qualidade da tradução validada em amostras relevantes e documentadas;
- preservação de placeholders, chaves, marcações e estrutura estrutural dos arquivos;
- gravação de arquivos segura e explícita;
- fluxo de instalação e operação documentados e reproduzíveis;
- comportamento claro em ausência de modelo, ambiente incompatível ou dispositivo indisponível;
- documentação das limitações conhecidas e das condições que exigem atenção do usuário;
- continuidade do uso da CLI e compatibilidade do núcleo com a arquitetura prevista;
- não depender de downloads automáticos nem de rede silenciosa no uso normal;
- evidência de confiabilidade suficiente para justificar a recomendação de uso fora do ambiente de desenvolvimento.

Não deve haver data artificial nem declaração de prontidão antecipada. Qualquer recomendação externa precisa ser baseada em evidência e não em expectativa de maturidade.

---

## 7. Riscos e limitações

### Fatos comprovados
- O projeto está em versão 0.0.1, sem release pública e sem garantia de estabilidade de API.
- ARB é o formato mais maduro; JSON, YAML e XML são mais experimentais.
- O suporte a tradução local depende de modelos locais e de uma stack com dependências opcionais.
- A GPU real não é validada de maneira automática no CI.
- O repositório não distribui modelos, pesos ou tokenizers.
- Testes automatizados não substituem a validação de qualidade linguística.
- A interface gráfica não existe como funcionalidade atual.

### Hipóteses que precisam de validação
- que a qualidade da tradução atende ao objetivo do projeto em idiomas relevantes;
- que o desempenho em CPU e GPU é aceitável para os casos de uso de interesse;
- que a experiência de GUI será útil e compatível com a arquitetura atual;
- que a expansão de formatos aumentará valor sem comprometer manutenção e qualidade;
- que os modelos locais escolhidos produzirão resultados consistentes para os pares de idiomas esperados.

Essas hipóteses não devem ser tratadas como fatos até que a evidência seja gerada em ambiente apropriado.

---

## 8. Como tratar a qualidade de tradução

O projeto deve deixar explícito este ponto: uma tradução pode ser tecnicamente bem-sucedida e ainda ser linguisticamente ruim. A validação futura não pode se basear em uma métrica automática isolada como prova suficiente de qualidade.

O estado real do projeto exige avaliação com critérios definidos antes da execução, incluindo:

- fidelidade ao significado original;
- naturalidade no idioma de destino;
- correção gramatical;
- preservação de nomes, números, placeholders e marcadores de formatação;
- adequação de mensagens curtas e contextuais;
- detecção de textos não traduzidos, truncados, vazios ou alterados indevidamente;
- qualidade em relação a referências revisadas por pessoas competentes;
- consumo de recursos e tempo de execução sem sacrificar silenciosamente a qualidade.

Esses critérios devem ser definidos e justificados antes da avaliação; em caso contrário, o resultado pode parecer positivo por conveniência e, na prática, não refletir qualidade real.

---

## 9. Conclusão

O Poliglota está em um estágio funcional, modular e claramente experimental. A arquitetura e a CLI estão estabelecidas; a base de formatos e motores existe; os testes e o CI fornecem uma camada importante de garantia estrutural; porém, a qualidade linguística, a confiabilidade real do núcleo e a experiência completa ainda exigem validação orientada por evidência, não por conjectura.

O roadmap acima define uma sequência prudente e orientada por critérios verificáveis: primeiro a linha de base, depois a qualidade da tradução, depois a confiabilidade do núcleo, a GUI, a experiência completa e, por fim, a expansão controlada de formatos. Essa ordem é necessária para manter o foco na visão original do projeto e evitar escalada para produtos ou serviços que não fazem parte do escopo do Poliglota.
