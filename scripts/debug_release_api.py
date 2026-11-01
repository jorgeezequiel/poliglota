#!/usr/bin/env python3
"""
Debug script to test GitHub Release API access
Simulates what the workflow does with real token
"""

import subprocess
import sys
import os

def run_cmd(cmd, env=None, description=""):
    """Run command and return output"""
    print(f"\n{'='*60}")
    print(f">> {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print()
    
    result = subprocess.run(
        cmd if isinstance(cmd, list) else cmd,
        shell=True,
        capture_output=True,
        text=True,
        env=env
    )
    
    print("STDOUT:")
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    print(f"Exit Code: {result.returncode}")
    
    return result

def main():
    # Get real token
    print("Getting GitHub token...")
    token_result = subprocess.run(
        ['gh', 'auth', 'token'],
        capture_output=True,
        text=True
    )
    
    if token_result.returncode != 0:
        print("FAILED: Could not get GitHub token")
        print("Make sure you're authenticated with 'gh auth login'")
        return 1
    
    token = token_result.stdout.strip()
    print(f"OK: Got token (length: {len(token)})")
    
    repo = "jorgeezequiel/poliglota"
    tag = "v0.0.2"
    
    # Create environment for testing
    test_env = os.environ.copy()
    test_env['GH_TOKEN'] = token
    
    # Test 1: Script Python (improved version)
    run_cmd(
        [sys.executable, '-m', 'scripts.release_validation', 'release-status',
         '--repo', repo, '--tag', tag, '--token', token],
        description="Test 1: Python validation script (with improved error messages)"
    )
    
    # Test 2: gh CLI directly
    run_cmd(
        f'gh release view {tag} --repo {repo}',
        env=test_env,
        description="Test 2: gh CLI - Direct release view"
    )
    
    # Test 3: gh CLI with token info
    run_cmd(
        'gh auth status',
        env=test_env,
        description="Test 3: gh CLI - Auth status (token scopes)"
    )
    
    # Test 4: curl to API
    run_cmd(
        f'curl -i -H "Authorization: Bearer {token}" '
        f'-H "Accept: application/vnd.github+json" '
        f'-H "X-GitHub-Api-Version: 2022-11-28" '
        f'https://api.github.com/repos/{repo}/releases/tags/{tag}',
        description="Test 4: curl - Direct API call (see HTTP headers)"
    )
    
    # Test 5: List releases via gh
    run_cmd(
        f'gh release list --repo {repo} --limit 3',
        env=test_env,
        description="Test 5: gh CLI - List releases (verify API access)"
    )
    
    print("\n" + "="*60)
    print("OK: Diagnostics complete")
    print("="*60)
    print("\nAnalysis:")
    print("- If all tests pass, the API is accessible")
    print("- If test 2-4 fail with 403, check job permissions in workflow")
    print("- If test 2-4 fail with 401, check token validity")
    print("- If test 5 passes but test 2 fails, release might already exist")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
