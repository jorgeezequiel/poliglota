# GUI desktop do Poliglota

A GUI do Poliglota é uma camada visual sobre a mesma CLI e os serviços já existentes no pacote. Ela não duplica a lógica de negócio: abre a mesma pipeline de validação, sincronização e tradução que a CLI usa.

## Quando usar

Use a GUI quando:

- você deseja uma interface visual para explorar um projeto de localização;
- prefere selecionar pasta, formato e idiomas em uma janela simples;
- quer validar ou sincronizar recursos sem memorizar comandos de terminal;
- precisa de uma primeira visão do estado do projeto sem depender de ambiente de servidor ou downloads automáticos.

A CLI continua sendo a interface oficial e o ponto de referência para comportamento e validação.

## Como abrir

Depois de instalar o pacote em ambiente Python:

```bash
poliglota gui
```

Ou diretamente:

```bash
python -m poliglota gui
```

Também é possível abrir a GUI em modo de diagnóstico sem janela:

```bash
python -m poliglota.gui --headless
```

O formulário é restaurado automaticamente entre sessões. Para usar um arquivo de estado diferente do padrão:

```bash
python -m poliglota.gui --state-file C:\temp\meu-estado.json
```

## Fluxo principal

1. Selecionar a pasta do projeto.
2. Definir o formato (`arb`, `json`, `yaml` ou `xml`).
3. Informar locale de origem e destino.
4. Escolher motor (`marian` ou `pytorch`) e dispositivo (`auto`, `cpu`, `cuda`, `mps`, `gpu`).
5. Clicar em `Validar`, `Sincronizar`, `Listar idiomas` ou `Traduzir`.
6. Acompanhar a saída do comando em tempo real na área de resultados.

## Texto multilinha

O campo `Texto` aceita várias linhas (três linhas visíveis, com rolagem interna). O conteúdo é sincronizado com o restante do formulário e enviado como um único argumento para o comando `translate`, preservando quebras de linha. O campo é habilitado apenas quando ocioso; durante uma operação ele fica desabilitado junto com o resto do formulário.

## Saída, cópia e salvamento

A área de resultados é somente leitura: o usuário pode selecionar e copiar o texto, mas não editá-lo por engano. Abaixo dela há três ações:

| Botão | Ação |
| --- | --- |
| `Copiar` | envia todo o conteúdo da saída para a área de transferência |
| `Salvar` | grava a saída em um arquivo `.txt` escolhido pelo usuário, em UTF-8 |
| `Limpar` | esvazia a área de resultados |

Essas ações continuam disponíveis durante a execução de um comando, para permitir copiar a saída parcial enquanto o processo ainda está rodando.

## Tooltips

Campos, comboboxes, botões e o seletor de tema exibem uma dica curta ao passar o mouse (por exemplo, “Idioma de origem, por exemplo pt_BR.”). As dicas são implementadas com Tkinter puro, sem dependências externas.

## Restaurar padrões

O botão `Restaurar padrões` devolve pasta do projeto, formato, locales, motor, dispositivo, modelo, `dry-run` e texto aos valores iniciais. O tema escolhido é preservado, e a alteração é gravada no arquivo de estado.

## Fechamento durante uma operação

Se a janela for fechada enquanto um comando está em andamento, a GUI pede confirmação. Recusar mantém a janela aberta e a operação continua; confirmar encerra o processo, grava o estado pendente e fecha a janela.

## Atalhos de teclado

| Atalho | Ação |
| --- | --- |
| `Enter` (em um campo do formulário) | executa `Validar` |
| `F5` | executa `Validar` |
| `Ctrl+O` | abre o seletor de pasta do projeto |
| `Esc` | solicita o cancelamento da operação em andamento |

## Progresso, streaming e cancelamento

- A barra de progresso fica visível o tempo todo e entra em modo indeterminado enquanto um comando roda, porque a CLI não informa percentual.
- O tempo decorrido aparece na linha de status, por exemplo `Validando recursos... (3.2s)`, atualizado a cada 200 ms.
- A saída do processo é lida linha a linha e aparece na área de resultados conforme é produzida, em vez de esperar o comando terminar.
- `stdout` e `stderr` são mesclados e decodificados como UTF-8 (a CLI força UTF-8 na inicialização), com substituição de caracteres inválidos para nunca quebrar a janela.
- Durante uma operação, o formulário e os botões de ação ficam desabilitados; os comboboxes voltam ao estado `readonly` ao final.
- O botão `Cancelar` (ou `Esc`) encerra o processo em execução e registra `Operação cancelada pelo usuário` na saída.
- Comandos que excedem 300 segundos são encerrados automaticamente com uma mensagem de tempo limite.

## Tema claro/escuro

O seletor `Tema` no topo da janela alterna entre `light` e `dark`. O tema é aplicado imediatamente a todos os widgets (formulário, botões, barra de progresso, campo de texto multilinha e área de resultados) e fica salvo no arquivo de estado. Valores desconhecidos no arquivo caem no tema padrão (`light`).

## Alta densidade de pixels (Windows)

No Windows, a GUI ativa o reconhecimento de DPI antes de criar a janela (`SetProcessDpiAwareness`, com fallback para `SetProcessDPIAware`) e ajusta o fator de escala do Tk ao DPI do monitor. Em monitores a 125%, 150% ou 200%, fontes e espaçamentos permanecem proporcionais em vez de minúsculos. Em outros sistemas, o ajuste é simplesmente ignorado.

## Geometria da janela

O tamanho e a posição da janela são lembrados entre sessões. Ao restaurar, a geometria é normalizada: tamanho mínimo de `760x500`, tamanho limitado ao monitor atual e posições fora da tela são trazidas de volta para a área visível. Uma geometria ausente ou malformada abre a janela no tamanho padrão (`960x640`).

## Persistência do formulário

A GUI lembra o que foi preenchido na última sessão: pasta do projeto, formato, locales de origem e destino, motor, dispositivo, modelo, o estado do modo de simulação (`dry-run`), o tema visual e a geometria da janela.

O arquivo de estado é gravado em:

| Sistema | Caminho |
| --- | --- |
| Windows | `%APPDATA%\poliglota\gui_state.json` |
| macOS | `~/Library/Application Support/poliglota/gui_state.json` |
| Linux | `$XDG_CONFIG_HOME/poliglota/gui_state.json` (ou `~/.config/poliglota/gui_state.json`) |

Regras de gravação:

- a gravação é automática, com atraso de 600 ms após a última alteração no formulário;
- ao fechar a janela, o estado pendente é gravado imediatamente;
- um arquivo ausente, ilegível ou corrompido não impede a abertura: a GUI volta aos valores padrão e registra a ocorrência no log;
- chaves desconhecidas, tipos errados e valores fora das listas suportadas são ignorados, mantendo o padrão do campo.

Para apontar para outro arquivo (por exemplo, um estado descartável em testes), use a variável de ambiente `POLIGLOTA_GUI_STATE_FILE` ou a opção `--state-file`.

## Validação em tempo real

Abaixo do formulário existe uma linha de status de validação, atualizada enquanto o usuário digita:

- `✓ Configuração válida.` em verde quando todos os campos estão corretos;
- `✗ <Campo>: <motivo>` em vermelho quando algo está incorreto, indicando também quantos outros campos precisam de atenção.

Além do texto, o campo com problema é destacado visualmente: o `ttk.Entry` recebe o estilo `Invalid.TEntry` (fundo avermelhado e borda de erro) e volta ao estilo normal assim que o valor fica válido. O foco do teclado vai para o primeiro campo inválido quando um comando é bloqueado.

O que é verificado localmente, antes de qualquer comando ser executado:

| Campo | Verificação |
| --- | --- |
| Projeto | pasta informada existe e é um diretório acessível |
| Idioma de origem/destino | código não vazio, formato de locale válido (`pt`, `pt_BR`, `en-US`, `zh_Hant_TW`) e tamanho razoável |
| Modelo | opcional; quando preenchido, aceita apenas letras, números, `.`, `_`, `-` e `/` |
| Texto para tradução | campo multilinha; validado em tempo real quando preenchido e obrigatório apenas no botão `Traduzir` |

Quando a validação falha, o comando não é disparado, o foco vai para o primeiro campo inválido e a barra de status resume a pendência.

## Erros acionáveis

Falhas da CLI deixam de ser apenas um código de saída. A área de resultados mostra um relatório com:

1. um título em linguagem simples (por exemplo, "Nenhum arquivo de tradução encontrado");
2. uma sugestão concreta de próximo passo;
3. os detalhes técnicos originais, com o código de saída, para quem precisar investigar.

As categorias reconhecidas incluem permissão negada, tempo esgotado, dependência opcional ausente, memória de GPU insuficiente, CUDA indisponível, opção de motor/dispositivo inválida, problema de glossário, ausência de arquivos de tradução, arquivo/pasta não encontrado, problemas de validação de recursos e arquivo malformado. Saídas não reconhecidas caem em uma categoria genérica, preservando o texto original.

## Organização do código

- `poliglota/gui.py` — entry point (`poliglota gui`, `--headless`, `--state-file`, `--project-root`), logging e criação do app.
- `poliglota/gui_app.py` — comportamento: validação, montagem dos comandos, execução da CLI (streaming e cancelamento) e persistência.
- `poliglota/gui_view.py` — apresentação: widgets, layout, temas, destaque de campos inválidos, barra de progresso, painel de saída, geometria e atalhos.
- `poliglota/gui_config.py` — estado persistido e listas de opções.
- `poliglota/gui_validators.py` e `poliglota/gui_errors.py` — validadores puros e categorização de erros.

## Log

Diagnósticos da GUI são gravados em `gui.log`, na mesma pasta do arquivo de estado, com rotação em 1 MB e até 3 backups. O log é criado apenas ao abrir a janela; a inicialização `--headless` não grava nada.

## Limitações conhecidas

- A GUI é uma primeira versão funcional e leve; ela não substitui a CLI como referência.
- Traduções reais continuam exigindo modelos locais e o extra opcional `.[gpu]` quando necessário.
- Sem modelo ou sem suporte de GPU, a aplicação informa a condição em vez de ocultá-la.
- Nenhum download automático de pacote, modelo ou serviço remoto é disparado pela GUI.
- A validação local cobre apenas o que a GUI consegue saber sem executar a CLI; regras de conteúdo (placeholders, glossário, chaves) continuam sendo verificadas pelo comando `validate`.


## Segurança e offline

A GUI segue as mesmas regras do projeto:

- não baixa modelos automaticamente;
- não envia arquivos para a rede;
- não altera arquivos sem o caminho explícito da CLI;
- não substitui falhas de GPU ou de modelo por fallback silencioso.
