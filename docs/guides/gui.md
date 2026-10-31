# GUI desktop do Poliglota

A interface gráfica do Poliglota é uma camada visual sobre a mesma lógica da CLI. Ela não reimplementa a regra de negócio; apenas oferece um formulário para validar, sincronizar, listar locales e traduzir texto/projetos usando os mesmos comandos já presentes no pacote.

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
6. acompanhe a saída da operação na área de resultados.

## Estado e persistência

A GUI salva valores do formulário entre sessões. Em geral, o estado persiste em:

- Windows: `%APPDATA%\poliglota\gui_state.json`
- macOS: `~/Library/Application Support/poliglota/gui_state.json`
- Linux: `$XDG_CONFIG_HOME/poliglota/gui_state.json` ou `~/.config/poliglota/gui_state.json`

A persistência inclui pasta do projeto, formato, bairros de origem/destino, model, tema e geometria da janela. Arquivos corrompidos ou ausentes são tratados como padrão do programa.

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
- a GUI não faz download automático de pacotes ou modelos;
- falhas do modelo, do dispositivo ou do ambiente continuam sendo reportadas pela própria CLI.

## Arquitetura da interface

Os principais módulos da GUI são:

- `poliglota/gui.py` — entrypoint e criação da aplicação;
- `poliglota/gui_app.py` — lógica de validação e execução de comandos;
- `poliglota/gui_view.py` — apresentação e widgets;
- `poliglota/gui_config.py` — estado persistido da interface;
- `poliglota/gui_validators.py` e `poliglota/gui_errors.py` — validação e classificação de erros.

## Ver também

- [docs/guides/installation.md](installation.md)
- [docs/guides/usage.md](usage.md)
- [docs/guides/translation-engine.md](translation-engine.md)
- [docs/LIMITATIONS.md](../LIMITATIONS.md)
