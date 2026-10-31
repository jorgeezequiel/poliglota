# Formatos suportados

## 1. ARB — implementado

ARB é o adaptador de referência do projeto.

Funcionalidades confirmadas:

- descoberta de arquivos `**/*.arb` sob a raiz do projeto;
- inferência de locale e módulo a partir do nome do arquivo;
- separação de entradas translatáveis de metadados do próprio arquivo;
- validação de placeholders (`{nome}`);
- sincronização de chaves ausentes a partir do locale origem;
- leitura e escrita com round-trip no adapter `ARBFormatAdapter`.

## 2. JSON, YAML e XML — implementados por adapters genéricos

Os adapters cadastrados no runtime atual são:

| Adapter | Valor de `--format` | Status |
| --- | --- | --- |
| `JsonFormatAdapter` | `json` | implementado |
| `YamlFormatAdapter` | `yaml` | implementado |
| `XmlFormatAdapter` | `xml` | implementado |

Esses adapters compartilham o contrato `FormatAdapter` e suportam as operações comuns da CLI: validação, sincronização e listagem de locales.

## 3. CSV e gettext — não implementados

Esses formatos não têm adapter do runtime e não têm suporte em comandos públicos do projeto. Eles aparecem como trabalho futuro, não como funcionalidade ativa.

## 4. Regras de uso

- `--format` sempre seleciona o adaptador de arquivos de localização;
- o projeto não faz auto-deteção de formato em tempo de execução;
- a validação específica continua mais forte para ARB do que para os formatos genéricos.

## 5. Referências

- [docs/guides/usage.md](guides/usage.md)
- [docs/LIMITATIONS.md](LIMITATIONS.md)
- [poliglota/formats](../poliglota/formats)
