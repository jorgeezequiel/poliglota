# Scripts de Desenvolvimento e Automação

Este diretório contém scripts auxiliares para desenvolvimento, manutenção e automação do projeto Poliglota.

## Estrutura

- **`audit/`** — Scripts de auditoria (Fases A-C) para validação interna.
  - `audit_phase_a_inventory.py` — Inventário completo de um corpus local.
  - `audit_phase_b_compatibility.py` — Compatibilidade entre locales e modelo de tradução.
  - `audit_phase_c_flow.py` — Validação de fluxo de CLI usando paths explícitos.
  - `audit_phase_c_flow_v2.py` — Smoke test de CLI sem hard-coded venv GPU.
  - `_portable.py` — Helpers compartilhados para resolução de caminhos e argumentos portáveis.

- **`deliver.py`** — Automação de entrega e operações Git (não executado, futuro condicional).
- **`generate_audit_report.py`** — Geração de relatórios finais de auditoria.

## Portabilidade

Os scripts de auditoria foram ajustados para não dependerem de caminhos absolutos específicos do ambiente local. O comportamento padrão é inferir a raiz do repositório a partir da localização do script, mas também é possível passar explicitamente `--repo-root`, `--corpus-root`, `--report-dir` e `--python-executable`.

A expectativa de uso é:

```bash
python scripts/audit/audit_phase_a_inventory.py --corpus-root /caminho/para/corpus --report-dir ./reports
python scripts/audit/audit_phase_c_flow.py --repo-root . --corpus-root /caminho/para/corpus --python-executable python
```

A validação de GPU permanece explícita. Se uma operação exigir CUDA, o script informa a indisponibilidade em vez de substituir silenciosamente CUDA por CPU.

## Notas

- Estes scripts **não fazem parte da CLI principal** (`poliglota --help`).
- São artefatos de desenvolvimento interno e traceabilidade histórica.
- Resultados são salvos em `reports/` (ignorados pelo Git).
- Todos os scripts mantêm compatibilidade multiplataforma (Windows, Linux, macOS).
