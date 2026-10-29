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

## Fluxo principal

1. Selecionar a pasta do projeto.
2. Definir o formato (`arb`, `json`, `yaml` ou `xml`).
3. Informar locale de origem e destino.
4. Escolher motor (`marian` ou `pytorch`) e dispositivo (`auto`, `cpu`, `cuda`, `mps`, `gpu`).
5. Clicar em `Validar`, `Sincronizar`, `Listar idiomas` ou `Traduzir`.
6. Ler a saída do terminal embutida na área de resultados.

## Limitações conhecidas

- A GUI é uma primeira versão funcional e leve; ela não substitui a CLI como referência.
- Traduções reais continuam exigindo modelos locais e o extra opcional `.[gpu]` quando necessário.
- Sem modelo ou sem suporte de GPU, a aplicação informa a condição em vez de ocultá-la.
- Nenhum download automático de pacote, modelo ou serviço remoto é disparado pela GUI.

## Segurança e offline

A GUI segue as mesmas regras do projeto:

- não baixa modelos automaticamente;
- não envia arquivos para a rede;
- não altera arquivos sem o caminho explícito da CLI;
- não substitui falhas de GPU ou de modelo por fallback silencioso.
