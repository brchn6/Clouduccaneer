#!/usr/bin/env python3
"""
Comprehensive test runner for CloudBuccaneer.
Runs different test suites and generates reports.
"""

import subprocess
import sys
from pathlib import Path
import argparse
import time


def run_command(cmd, description=""):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description or ' '.join(cmd)}")
    print('='*60)
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        duration = time.time() - start_time
        print(f"\n✅ {description or 'Command'} completed successfully in {duration:.2f}s")
        return True
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        print(f"\n❌ {description or 'Command'} failed in {duration:.2f}s (exit code: {e.returncode})")
        return False
    except FileNotFoundError:
        print(f"\n❌ Command not found: {cmd[0]}")
        return False


def install_dependencies():
    """Install test dependencies."""
    print("Installing test dependencies...")
    
    # Install main dependencies
    success = run_command([
        sys.executable, "-m", "pip", "install", "-e", "."
    ], "Installing main package")
    
    if not success:
        return False
    
    # Install test dependencies
    success = run_command([
        sys.executable, "-m", "pip", "install", 
        "pytest>=7.0", "pytest-cov>=4.0", "pytest-mock>=3.0", 
        "pytest-xdist>=3.0", "pytest-html>=3.0"
    ], "Installing test dependencies")
    
    return success


def run_unit_tests(parallel=True, coverage=True, verbose=False):
    """Run unit tests."""
    cmd = [sys.executable, "-m", "pytest"]
    
    if parallel:
        cmd.extend(["-n", "auto"])
    
    if coverage:
        cmd.extend(["--cov=cb", "--cov-report=term-missing", "--cov-report=html"])
    
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Run specific test files
    test_files = [
        "tests/test_utils.py",
        "tests/test_renamer.py", 
        "tests/test_ytwrap.py",
        "tests/test_spotwrap.py",
        "tests/test_cli.py"
    ]
    
    cmd.extend(test_files)
    
    return run_command(cmd, "Unit tests")


def run_integration_tests(verbose=False):
    """Run integration tests."""
    cmd = [sys.executable, "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    cmd.extend([
        "tests/test_integration.py",
        "--tb=short"
    ])
    
    return run_command(cmd, "Integration tests")


def run_existing_tests():
    """Run existing tests (like test_summarize.py)."""
    cmd = [sys.executable, "-m", "pytest", "tests/test_summarize.py", "-v"]
    return run_command(cmd, "Existing tests")


def run_linting():
    """Run code linting."""
    print("Running code quality checks...")
    
    # Try to install and run basic linting
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "flake8"], 
                      check=True, capture_output=True)
        
        success = run_command([
            sys.executable, "-m", "flake8", "src/cb", "--max-line-length=100", 
            "--ignore=E203,W503"
        ], "Code linting with flake8")
        
        return success
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Linting skipped (flake8 not available)")
        return True


def run_security_checks():
    """Run security checks."""
    print("Running security checks...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "safety"], 
                      check=True, capture_output=True)
        
        success = run_command([
            sys.executable, "-m", "safety", "check"
        ], "Security check with safety")
        
        return success
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Security checks skipped (safety not available)")
        return True


def run_smoke_tests():
    """Run basic smoke tests."""
    print("Running smoke tests...")
    
    # Test that the CLI can be imported and shows help
    cmd = [sys.executable, "-c", "from cb.cli import app; app(['--help'])"]
    
    return run_command(cmd, "CLI smoke test")


def generate_test_report():
    """Generate a comprehensive test report."""
    cmd = [
        sys.executable, "-m", "pytest", 
        "--html=test_report.html", 
        "--self-contained-html",
        "--cov=cb",
        "--cov-report=html",
        "tests/"
    ]
    
    return run_command(cmd, "Generating comprehensive test report")


def main():
    parser = argparse.ArgumentParser(description="CloudBuccaneer Test Runner")
    parser.add_argument("--quick", action="store_true", 
                       help="Run only quick tests")
    parser.add_argument("--unit-only", action="store_true",
                       help="Run only unit tests")
    parser.add_argument("--integration-only", action="store_true",
                       help="Run only integration tests")
    parser.add_argument("--no-coverage", action="store_true",
                       help="Skip coverage reporting")
    parser.add_argument("--no-parallel", action="store_true",
                       help="Don't run tests in parallel")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    parser.add_argument("--install-deps", action="store_true",
                       help="Install dependencies before running tests")
    parser.add_argument("--report", action="store_true",
                       help="Generate HTML test report")
    
    args = parser.parse_args()
    
    print("🧪 CloudBuccaneer Test Suite")
    print("=" * 40)
    
    # Track overall success
    all_success = True
    
    # Install dependencies if requested
    if args.install_deps:
        if not install_dependencies():
            print("❌ Failed to install dependencies")
            return 1
    
    # Run smoke tests first
    if not run_smoke_tests():
        print("❌ Smoke tests failed - basic functionality broken")
        all_success = False
    
    # Run tests based on arguments
    if args.unit_only:
        success = run_unit_tests(
            parallel=not args.no_parallel,
            coverage=not args.no_coverage,
            verbose=args.verbose
        )
        all_success = all_success and success
        
    elif args.integration_only:
        success = run_integration_tests(verbose=args.verbose)
        all_success = all_success and success
        
    elif args.quick:
        # Quick tests: just unit tests without coverage
        success = run_unit_tests(
            parallel=not args.no_parallel,
            coverage=False,
            verbose=args.verbose
        )
        all_success = all_success and success
        
    else:
        # Full test suite
        # 1. Unit tests
        success = run_unit_tests(
            parallel=not args.no_parallel,
            coverage=not args.no_coverage,
            verbose=args.verbose
        )
        all_success = all_success and success
        
        # 2. Integration tests
        success = run_integration_tests(verbose=args.verbose)
        all_success = all_success and success
        
        # 3. Existing tests
        success = run_existing_tests()
        all_success = all_success and success
        
        # 4. Code quality checks
        if not args.quick:
            success = run_linting()
            all_success = all_success and success
            
            success = run_security_checks()
            all_success = all_success and success
    
    # Generate report if requested
    if args.report:
        generate_test_report()
    
    # Final summary
    print("\n" + "="*60)
    print("🏁 TEST SUMMARY")
    print("="*60)
    
    if all_success:
        print("✅ All tests passed! The application is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
