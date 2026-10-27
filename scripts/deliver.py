#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Poliglota v0.0.1 — Delivery Automation Script
Consolidate audit changes, validate, and prepare for local/remote publication.
Usage: python deliver.py [--tag] [--push] [--dry-run]
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Files to commit (modified + new artifacts only; excludes tools/scripts)
FILES_TO_COMMIT = [
    ".github/workflows/ci.yml",
    "poliglota/engines/pytorch_engine.py",
    "tests/test_engines.py",
    "docs/development/workflows.md",
    "AUDIT_REPORT_20261027.md",
    "DELIVERY_CHECKLIST_20261027.md",
]

COMMIT_MESSAGE = (
    "refactor(ci): desacople workflows CI/CD + cache HF + 5 jobs; "
    "docs(workflows): add strategy guide; "
    "fix(engines): format pytorch_engine.py line 551; "
    "test(engines): mock CUDA availability"
)

TAG_NAME = "v0.0.1-audit-complete"
TAG_MESSAGE = (
    "Auditoria CI/CD completa: workflows refatorados, "
    "250/250 tests PASSED, corpus v2 validado 100%"
)


def run_cmd(cmd, description, dry_run=False):
    """Execute command; return True if success, False if failure."""
    print(f"\n{'[DRY-RUN]' if dry_run else '[EXEC]'} {description}")
    print(f"  Command: {' '.join(cmd)}")
    
    if dry_run:
        print(f"  → Would execute (dry-run mode)")
        return True
    
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=True, capture_output=True, text=True)
        print(f"  ✅ Success")
        if result.stdout.strip():
            print(f"  Output: {result.stdout[:200]}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed with exit code {e.returncode}")
        if e.stderr:
            print(f"  Error: {e.stderr[:300]}")
        return False


def validate_files():
    """Verify all files to commit exist and are modified/untracked."""
    print("\n📋 Validating files...")
    missing = []
    for file in FILES_TO_COMMIT:
        path = PROJECT_ROOT / file
        if not path.exists():
            missing.append(file)
            print(f"  ⚠️  {file}: NOT FOUND")
        else:
            print(f"  ✅ {file}: exists")
    
    if missing:
        print(f"\n❌ Missing files: {missing}")
        return False
    return True


def validate_git_status():
    """Check git status; ensure no unexpected changes."""
    print("\n📋 Validating git status...")
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True
    )
    
    print(f"  Git Status Output:\n{result.stdout}")
    
    # Expected: 3 modified + 2 untracked
    lines = result.stdout.strip().split('\n')
    modified = [l for l in lines if l.startswith(' M')]
    untracked = [l for l in lines if l.startswith('??')]
    
    print(f"  Modified: {len(modified)}, Untracked: {len(untracked)}")
    
    if len(modified) != 3 or len(untracked) != 2:
        print(f"  ⚠️  Unexpected git state (expected 3 modified + 2 untracked)")
        return False
    
    print(f"  ✅ Git status as expected")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Poliglota Delivery Script")
    parser.add_argument("--tag", action="store_true", help="Create annotated tag")
    parser.add_argument("--push", action="store_true", help="Push to remote (requires tag)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without executing")
    args = parser.parse_args()
    
    print("=" * 70)
    print("🚀 Poliglota v0.0.1 — Delivery Automation")
    print(f"   Timestamp: {TIMESTAMP}")
    print(f"   Project: {PROJECT_ROOT}")
    print(f"   Mode: {'DRY-RUN' if args.dry_run else 'LIVE EXECUTION'}")
    print("=" * 70)
    
    # Step 1: Validate
    if not validate_files():
        print("\n❌ File validation failed. Aborting.")
        sys.exit(1)
    
    if not validate_git_status():
        print("\n⚠️  Git status validation flagged issues. Review before proceeding.")
        if not args.dry_run:
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Aborted.")
                sys.exit(1)
    
    # Step 2: Add files
    if not run_cmd(
        ["git", "add"] + FILES_TO_COMMIT,
        "Adding files to staging",
        dry_run=args.dry_run
    ):
        print("\n❌ Failed to add files. Aborting.")
        sys.exit(1)
    
    # Step 3: Commit
    if not run_cmd(
        ["git", "commit", "-m", COMMIT_MESSAGE],
        "Creating commit",
        dry_run=args.dry_run
    ):
        print("\n❌ Failed to create commit. Aborting.")
        sys.exit(1)
    
    # Step 4: Tag (optional)
    if args.tag:
        if not run_cmd(
            ["git", "tag", "-a", TAG_NAME, "-m", TAG_MESSAGE],
            f"Creating tag {TAG_NAME}",
            dry_run=args.dry_run
        ):
            print(f"\n⚠️  Failed to create tag (non-blocking).")
    
    # Step 5: Push (optional, requires tag)
    if args.push:
        if not args.tag:
            print("\n⚠️  --push requires --tag. Skipping push.")
        else:
            if not run_cmd(
                ["git", "push", "origin", "main", "--tags"],
                "Pushing to remote (main + tags)",
                dry_run=args.dry_run
            ):
                print(f"\n⚠️  Failed to push. Review and retry manually.")
    
    # Step 6: Summary
    print("\n" + "=" * 70)
    print("✅ Delivery Complete!")
    print("=" * 70)
    print(f"Commit: {COMMIT_MESSAGE}")
    if args.tag:
        print(f"Tag: {TAG_NAME}")
    if args.push:
        print(f"Pushed to origin/main")
    print("\nNext steps:")
    print("  1. Review local commit: git log --oneline -1")
    print("  2. Review changes: git show HEAD")
    if args.tag:
        print(f"  3. Push tag: git push origin {TAG_NAME}")
    else:
        print("  3. (Optional) Create tag: python deliver.py --tag")
    print("=" * 70)


if __name__ == "__main__":
    main()
