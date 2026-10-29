# Scripts de Desenvolvimento e Automação

Este diretório contém scripts auxiliares para desenvolvimento, manutenção e automação do projeto Poliglota.

## Estrutura

- **`audit/`** — Scripts de auditoria (Fases A-C) para validação interna.
  - `audit_phase_a_inventory.py` — Inventário completo do corpus QuestLog.
  - `audit_phase_b_compatibility.py` — Compatibilidade entre locales QuestLog e modelo NLLB-200.
  - `audit_phase_c_flow.py` — Teste de fluxo de produção com CLI.
  - `audit_phase_c_flow_v2.py` — Teste de fluxo com comando instalado.

- **`deliver.py`** — Automação de entrega e operações Git (não executado, futuro condicional).

- **`generate_audit_report.py`** — Geração de relatórios finais de auditoria.

## Notas

- Estes scripts **não fazem parte da CLI principal** (`poliglota --help`).
- São artefatos de desenvolvimento interno e traceabilidade histórica.
- Resultados são salvos em `reports/` (ignorado pelo Git).
- Todos os scripts mantêm compatibilidade multiplataforma (Windows, Linux, macOS).

## Uso

Para executar um script de auditoria:

```bash
python scripts/audit/audit_phase_a_inventory.py
```

Consulte `docs/audits/` para relatórios e documentação de auditoria.
