# Internal Reports and Project Documentation Policy

## Overview

Poliglota is a public open-source project on GitHub. Internal reports, audits, phase analyses, and execution summaries must be kept private and never published in the public repository.

This document establishes the permanent policy for organizing and protecting internal documentation.

## Policy

### Location of Internal Reports

All internal reports, audits, analyses, plans, and execution summaries **must be saved in `/reports/`** at the project root.

Internal documentation includes (but is not limited to):

- Phase audit reports (`PHASE_*_AUDIT_REPORT.md`)
- Phase planning and execution reports (`PHASE_*_PLANNING_REPORT.md`, `PHASE_*_COMPLETION.md`)
- Phase analysis and comparison reports (`PHASE_*_COMPARATIVE_REPORT.md`)
- Phase quality and technical analysis (`PHASE_*_QUALITY.md`, `PHASE_*_COMPLETION_SUMMARY.md`)
- Investigation and research reports (`INVESTIGACAO_*.md`)
- Agent execution summaries and internal notes
- Any other documentation not intended for public consumption

### What Stays Public

The following documentation remains in the repository root and `docs/` directories and **must never be moved**:

- `README.md` — Public project overview
- `CHANGELOG.md` — Public change history
- `CONTRIBUTING.md` — Public contribution guidelines
- `SECURITY.md` — Public security policy
- `LICENSE` — Open-source license
- `docs/` — Public user and developer documentation
- `pyproject.toml`, configuration files — Public project metadata

### Git Protection

The `/reports/` directory is listed in `.gitignore`:

```
# Line 144 in .gitignore
reports/
```

This prevents accidental commits of internal reports. The `.gitignore` rule applies to:

- New files created in `reports/`
- Files moved to `reports/` after the rule was established

**Important**: `.gitignore` does **not** retroactively untrack files already committed to Git. If a report was previously committed, it remains in the repository history unless explicitly removed (which requires rewriting Git history—not recommended without explicit authorization).

### Workflow for Creating New Reports

When creating a new report for any phase:

1. Create the file directly in `/reports/` using the naming convention: `PHASE_*_<TYPE>.md` (e.g., `PHASE_5_AUDIT_REPORT.md`)
2. Never create reports in the project root
3. Ensure `.gitignore` has the `/reports/` rule active
4. Verify with `git status` that the file is not staged

### Verification

To verify the `.gitignore` is working:

```bash
# Check that reports/ is in .gitignore
grep "^/reports/" .gitignore

# Verify no reports are tracked
git ls-files reports/

# Check git status shows reports as untracked
git status --short
```

All reports should show as untracked (`??`) in `git status --short` output, or not appear at all if they are already ignored.

### Checking Repository History

To verify whether a report has been committed to Git history:

```bash
# List all commits affecting a specific report
git log --all --full-history -- "reports/PHASE_*.md"

# List all markdown files ever committed
git log --all --name-status -- "*.md"
```

If a report appears in the commit history, contact the project maintainer about removing it from history (if needed).

## Current Status (Last Reorganized)

As of the latest reorganization:

- **8 internal reports** have been identified and consolidated in `/reports/`:
  - `PHASE_0_AUDIT_REPORT.md`
  - `PHASE_1_PLANNING_REPORT.md`
  - `PHASE_2_AUDIT_REPORT.md`
  - `PHASE_2_COMPARATIVE_REPORT.md`
  - `PHASE_2_COMPLETION.md`
  - `PHASE_4_COMPLETION_SUMMARY.md`
  - `PHASE_4_QUALITY.md`
  - `INVESTIGACAO_TRADUCAO_OFFLINE_E_LICENCIAMIENTO.md`

- **Status**: None of these reports are currently tracked by Git (verified with `git ls-files reports/` and `git log`).

- **`.gitignore` status**: Line 144 specifies `/reports/` as ignored. Redundant individual file entries removed during this reorganization.

## References

- [`.gitignore` configuration](../../.gitignore)
- [Development and Testing Guide](./testing.md)
- [Architecture Overview](../architecture/overview.md)
