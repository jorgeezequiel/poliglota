# GUI desktop do Poliglota

A interface gráfica do Poliglota oferece os fluxos de validação, sincronização e tradução, além de um editor local para revisar resultados gerados. As operações de projeto usam a mesma lógica de tradução da CLI.

## Quando usar a GUI

Use a GUI quando:

- você prefere trabalhar com formulário em vez de memorizar comandos do terminal;
- quer abrir um projeto, selecionar o formato e os idiomas em uma interface simples;
- precisa validar ou sincronizar arquivos de localização de forma visual;
- deseja acompanhar a saída do processo em tempo real.

A CLI continua sendo a referência oficial de comportamento e validação.

## Como abrir

Após instalar o pacote:

```bash
poliglota gui
```

Ou diretamente:

```bash
python -m poliglota.gui
```

Também é possível abrir a GUI em modo de diagnóstico sem janela principal:

```bash
python -m poliglota.gui --headless
```

## Fluxo principal

1. escolha a pasta do projeto;
2. defina o formato (`arb`, `json`, `yaml`, `xml`);
3. informe a origem e o destino;
4. configure motor e dispositivo;
5. clique em `Validar`, `Sincronizar`, `Listar idiomas` ou `Traduzir`;
6. acompanhe a saída da operação na área de resultados;
7. depois de traduzir o projeto, clique em `Revisar traduções` para conferir cada chave, comparar original e resultado e editar qualquer mensagem.

## Revisar e exportar

O editor mostra o status de revisão, a chave, o arquivo de destino, o texto original, a tradução atual e a descrição ARB quando disponível. `Salvar rascunho` persiste a alteração sem marcá-la como aprovada; `Marcar revisada` registra a decisão do revisor. O editor valida placeholders conhecidos antes de salvar.

Se o conteúdo do editor mudar, selecionar outra mensagem, fechar pelo botão ou pelo `X`, ou exportar abre uma confirmação. `Sim` salva um rascunho e continua, `Não` descarta somente a edição ainda não persistida e `Cancelar` mantém a mensagem aberta. Uma falha ao salvar mantém a edição no editor e bloqueia a navegação/fechamento/exportação. Exportar também exige resolver a edição visível antes da confirmação separada de itens ainda pendentes.

As saídas automáticas ficam em `.poliglota_translated`. Rascunhos, aprovações e histórico de conteúdo ficam em `.poliglota_reviewed/review_manifest.json`, sem sobrescrever os arquivos de origem. O estado é separado por pasta do projeto, formato, par de locales, caminho relativo e chave. Ao reabrir `Revisar traduções`, o Poliglota retoma os rascunhos persistidos. Se o original ou a tradução preliminar mudar, a revisão anterior é preservada para consulta, mas fica obsoleta e não é aplicada nem exportada como aprovada até nova revisão. Mudanças apenas em descrições/metadados não tornam o texto obsoleto.

Ao escolher um diretório pai para exportar, a GUI cria uma pasta nova `poliglota-reviewed-<locale>`; se ela já existir, usa um nome com data e hora, sem sobrescrevê-la. Todos os arquivos são preparados e validados em uma área temporária no mesmo volume. A publicação usa um marcador de exportação incompleta enquanto copia; em falha, o diretório criado por aquela tentativa é removido. Arquivos de destino preexistentes nunca são substituídos. A exportação inclui os arquivos do conjunto de origem e recusa arquivos de tradução ausentes, estruturas divergentes e revisões obsoletas.

Se ainda houver mensagens pendentes, a GUI informa a quantidade e pede confirmação antes de exportar. Esses textos continuam sendo traduções preliminares; a confirmação de exportação não os aprova linguisticamente.

## Estado e persistência

A GUI salva valores do formulário entre sessões. Em geral, o estado persiste em:

- Windows: `%APPDATA%\poliglota\gui_state.json`
- macOS: `~/Library/Application Support/poliglota/gui_state.json`
- Linux: `$XDG_CONFIG_HOME/poliglota/gui_state.json` ou `~/.config/poliglota/gui_state.json`

A persistência inclui pasta do projeto, formato, locales de origem/destino, modelo, dispositivo, tema e geometria da janela. Os rascunhos e estados de revisão são mantidos junto às saídas do projeto. Uma sessão de revisão corrompida ou de esquema incompatível apresenta erro e preserva o manifesto existente; não é tratada como uma sessão vazia. A configuração geral da GUI, separada do manifesto de revisão, ainda usa os padrões do programa quando ausente ou inválida.

## Campos e validação

Antes de disparar uma ação, a GUI valida os campos do formulário:

- projeto precisa existir e ser um diretório acessível;
- origem/destino precisam ter código de locale não vazio;
- modelo, quando informado, precisa seguir caracteres válidos;
- texto de tradução precisa ser válido quando a operação exige esse campo.

Quando a validação falha, a operação não é disparada e o foco vai para o primeiro campo inválido.

## Saída e cancelamento

A área de resultados exibe a saída da execução em tempo real. O processo pode ser cancelado por tecla `Esc` ou pelo botão de cancelamento, e o comando terminado recebe mensagem indicando interrupção pelo usuário.

A GUI também oferece ações para:

- copiar a saída;
- salvar em arquivo `.txt` em UTF-8;
- limpar a área de resultados.

## Limitações conhecidas da GUI

- a GUI é um wrapper sobre a CLI e não substitui a CLI como referência;
- a tradução real continua exigindo modelo local compatível;
- a revisão é manual e local; o Poliglota não certifica correção semântica nem substitui revisão linguística;
- a exportação pode incluir preliminares, mas exige confirmação explícita enquanto houver itens pendentes;
- a GUI não faz download automático de pacotes ou modelos;
- falhas do modelo, do dispositivo ou do ambiente continuam sendo reportadas pela própria CLI.

## Arquitetura da interface

Os principais módulos da GUI são:

- `poliglota/gui.py` — entrypoint e criação da aplicação;
- `poliglota/gui_app.py` — lógica de validação e execução de comandos;
- `poliglota/gui_view.py` — apresentação e widgets;
- `poliglota/gui_config.py` — estado persistido da interface;
- `poliglota/translation_review.py` e `poliglota/review_window.py` — persistência, validação e editor de revisão;
- `poliglota/gui_validators.py` e `poliglota/gui_errors.py` — validação e classificação de erros.

## Ver também

- [docs/guides/installation.md](installation.md)
- [docs/guides/usage.md](usage.md)
- [docs/guides/translation-engine.md](translation-engine.md)
- [docs/LIMITATIONS.md](../LIMITATIONS.md)
