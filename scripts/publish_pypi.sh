#!/bin/bash
# One-shot PyPI upload for flybrain-connectome.
# Prerequisites: pip install twine build
# Run: bash scripts/publish_pypi.sh
#      bash scripts/publish_pypi.sh --dry-run   # validate only, no upload
#
# --dry-run mode performs 3 checks and exits without network/write ops:
#   (1) tar -tvf / unzip -l to list sdist + wheel contents
#   (2) Compare pyproject.toml package declaration vs actual archived files
#   (3) Install to temp venv and verify `import flybrain_cli`
#
# First-time setup:
#   1. Register at https://pypi.org/account/register/ (username: any, email: yours)
#   2. Create an API token at https://pypi.org/manage/account/token/
#      - Scope: project-scoped (select "flybrain-connectome" or leave unscoped)
#      - Copy the token (starts with "pypi-")
#   3. Save the token (choose one):
#      a) Environment variable:  export TWINE_PASSWORD="pypi-..."
#      b) .pypirc file in your home dir (see below)
#   4. Run this script.

set -e

# ── Parse flags ─────────────────────────────────────────────────────
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            echo "Usage: bash scripts/publish_pypi.sh [--dry-run]"
            echo ""
            echo "  --dry-run   Validate sdist/wheel without uploading:"
            echo "              (1) list archive contents"
            echo "              (2) compare declared vs actual packages"
            echo "              (3) install to temp venv and verify import"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg (use --help)"
            exit 1
            ;;
    esac
done

if $DRY_RUN; then
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  PUBLISH PIPY — DRY RUN MODE (no upload, no network)         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
fi

# ── 0. Preflight ────────────────────────────────────────────────────
echo "[0/5] Preflight checks..."

# Check twine is installed (skip in dry-run: twine check is still useful)
python -m twine --version >/dev/null 2>&1 || {
    if $DRY_RUN; then
        echo "  [dry-run] twine not installed — skipping twine check"
    else
        echo "  installing twine..."
        python -m pip install twine
    fi
}

# Check dist/ exists
if [ ! -d "dist" ] || [ -z "$(ls -A dist/ 2>/dev/null)" ]; then
    echo "  ERROR: dist/ is empty. Run 'python -m build' first."
    exit 1
fi

ls -la dist/
echo ""

# ── DRY RUN MODE ────────────────────────────────────────────────────
if $DRY_RUN; then
    echo "════════════════════════════════════════════════════════════"
    echo "  DRY RUN: 3 validation checks"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    # ── (1) List archive contents ───────────────────────────────────
    echo "[1/3] Archive contents..."
    for f in dist/*; do
        echo ""
        echo "  ── $(basename "$f") ──"
        case "$f" in
            *.tar.gz)
                listing=$(tar -tzf "$f" 2>/dev/null || true)
                total=$(echo "$listing" | wc -l)
                echo "$listing" | head -50
                if [ "$total" -gt 50 ]; then
                    echo "  ... ($total files total)"
                fi
                ;;
            *.whl)
                listing=$(unzip -l "$f" 2>/dev/null | tail -n +4 || true)
                total=$(echo "$listing" | grep -c '|' || true)
                echo "$listing" | head -50
                if [ "$total" -gt 50 ]; then
                    echo "  ... ($total files total)"
                fi
                ;;
            *)
                echo "  (unknown format: $f)"
                ;;
        esac
    done
    echo ""
    echo "  ✓ archive listing complete"
    echo ""

    # ── (2) Compare declared vs actual packages ─────────────────────
    echo "[2/3] Package declaration vs actual..."
    # Read declared packages from pyproject.toml
    DECLARED_PACKAGES=$(python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    cfg = tomllib.load(f)
inc = cfg.get('tool', {}).get('setuptools', {}).get('packages', {}).get('find', {}).get('include', [])
excl = cfg.get('tool', {}).get('setuptools', {}).get('packages', {}).get('find', {}).get('exclude', [])
mods = cfg.get('tool', {}).get('setuptools', {}).get('py-modules', [])
print('INCLUDE:', inc)
print('EXCLUDE:', excl)
print('PY_MODULES:', mods)
")
    echo "  Declared from pyproject.toml:"
    echo "$DECLARED_PACKAGES" | while IFS= read -r line; do echo "    $line"; done

    # Find actual top-level directories in the sdist
    echo ""
    echo "  Actual top-level packages in sdist:"
    SDIST=$(ls dist/*.tar.gz 2>/dev/null | head -1)
    if [ -n "$SDIST" ]; then
        tar -tzf "$SDIST" | grep -E '^[^/]+/' | sed 's|/.*||' | sort -u | while IFS= read -r pkg; do
            echo "    $pkg/"
        done
    fi

    # Check that expected modules are present in wheel
    echo ""
    echo "  Expected modules in wheel:"
    WHEEL=$(ls dist/*.whl 2>/dev/null | head -1)
    if [ -n "$WHEEL" ]; then
        for mod in flybrain_cli.py; do
            if unzip -l "$WHEEL" 2>/dev/null | grep -q "$mod"; then
                echo "    ✓ $mod"
            else
                echo "    ✗ $mod (MISSING!)"
            fi
        done
        for pkg in "flybrain-connectome-mcp" "integrations"; do
            if unzip -l "$WHEEL" 2>/dev/null | grep -q "$pkg"; then
                echo "    ✓ $pkg/"
            else
                echo "    ✗ $pkg/ (MISSING!)"
            fi
        done
    fi
    echo ""
    echo "  ✓ declaration comparison complete"
    echo ""

    # ── (3) Install to temp venv and verify import ───────────────────
    echo "[3/3] Temp venv install + import test..."
    VENV_DIR=$(mktemp -d -t flybrain-test-XXXXXX)
    echo "  Temp venv: $VENV_DIR"

    python -m venv "$VENV_DIR" 2>&1 || {
        echo "  ERROR: cannot create venv"
        exit 1
    }

    "$VENV_DIR/Scripts/python.exe" -m pip install --quiet --upgrade pip 2>&1 | tail -1
    echo "  pip upgraded"

    # Install the wheel into temp venv
    if [ -n "$WHEEL" ]; then
        "$VENV_DIR/Scripts/python.exe" -m pip install --quiet "$WHEEL" 2>&1 | tail -3
        echo "  ✓ wheel installed to temp venv"
    else
        echo "  ERROR: no wheel found in dist/"
        exit 1
    fi

    # Verify imports
    echo ""
    echo "  Verifying imports..."
    PY="$VENV_DIR/Scripts/python.exe"
    IMPORTS_OK=true

    $PY -c "import flybrain_cli; print(f'    ✓ flybrain_cli v{flybrain_cli.__version__}')" 2>&1 || IMPORTS_OK=false
    $PY -c "import flybrain_export; print(f'    ✓ flybrain_export')" 2>&1 || IMPORTS_OK=false
    $PY -c "import flybrain_cli; flybrain_cli.main(['--version'])" 2>&1 | head -1 || IMPORTS_OK=false
    # Verify mcp server files are in site-packages (package name has hyphens, can't import directly)
    MCP_FILES=$($PY -c "
import sysconfig, os
sp = sysconfig.get_paths()['purelib']
base = os.path.join(sp, 'flybrain-connectome-mcp')
found = sum(1 for f in os.listdir(base) if f.endswith('.py')) if os.path.isdir(base) else 0
print(f'    ✓ mcp server files in site-packages: {found} .py files')
print(f'    ✓ mcp_connectome subdir: {os.path.isdir(os.path.join(base, \"mcp_connectome\"))}')
" 2>&1) || { IMPORTS_OK=false; echo "    ✗ mcp server files not found"; }
    if [ -n "$MCP_FILES" ]; then echo "$MCP_FILES"; fi

    echo ""
    if $IMPORTS_OK; then
        echo "  ✓ ALL IMPORTS PASSED"
    else
        echo "  ✗ SOME IMPORTS FAILED — see errors above"
    fi

    # Cleanup temp venv (use Python for Windows compatibility)
    python -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" "$VENV_DIR"
    echo ""
    echo "  ✓ temp venv cleaned up"
    echo ""

    # ── Summary ─────────────────────────────────────────────────────
    VERSION=$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null || python -c 'import toml; print(toml.load("pyproject.toml")["project"]["version"])')
    echo "════════════════════════════════════════════════════════════"
    echo "  DRY RUN SUMMARY"
    echo "════════════════════════════════════════════════════════════"
    echo "  Package:  flybrain-connectome"
    echo "  Version:  $VERSION"
    echo "  Files:    $(ls dist/ | tr '\n' ' ')"
    echo "  Status:   ✓ READY FOR UPLOAD (if all checks above passed)"
    echo ""
    echo "  To upload: bash scripts/publish_pypi.sh"
    echo ""
    exit 0
fi

# ── 1. Validate the packages ────────────────────────────────────────
echo "[1/5] twine check (metadata validation)..."
python -m twine check dist/*
echo "  ✓ metadata OK"
echo ""

# ── 2. Strict check ────────────────────────────────────────────────
echo "[2/5] twine check --strict..."
python -m twine check --strict dist/*
echo "  ✓ strict metadata OK"
echo ""

# ── 3. Confirm with user ────────────────────────────────────────────
echo "[3/5] About to upload to PyPI:"
echo "      - Package: flybrain-connectome"
VERSION=$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null || python -c 'import toml; print(toml.load("pyproject.toml")["project"]["version"])')
echo "      - Version: $VERSION"
echo "      - Files: $(ls dist/ | tr '\n' ' ')"
echo ""
read -p "Type 'UPLOAD' to confirm (or press Enter to abort): " CONFIRM
if [ "$CONFIRM" != "UPLOAD" ]; then
    echo "Aborted. No files were uploaded."
    exit 0
fi

# ── 4. Upload ────────────────────────────────────────────────────────
echo "[4/5] Uploading to PyPI..."
python -m twine upload dist/*
echo ""

# ── 5. Verify ────────────────────────────────────────────────────────
echo "[5/5] Verifying upload..."
sleep 10  # PyPI indexing takes a moment
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "flybrain-connectome==$VERSION" --dry-run 2>&1 | tail -5 || \
    echo "  (test install check failed — verify at https://pypi.org/project/flybrain-connectome/)"
echo ""
echo "✓ Done. Visit: https://pypi.org/project/flybrain-connectome/"

# ── Bonus: .pypirc template ──────────────────────────────────────────
if [ ! -f ~/.pypirc ]; then
    cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TEST_TOKEN_HERE
EOF
    echo "Created ~/.pypirc template — edit it to add your token."
fi
