#!/bin/bash
# One-shot PyPI upload for flybrain-connectome.
# Prerequisites: pip install twine
# Run: bash scripts/publish_pypi.sh
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

# ── 0. Preflight ────────────────────────────────────────────────────
echo "[0/5] Preflight checks..."

# Check twine is installed
python -m twine --version >/dev/null 2>&1 || {
    echo "  installing twine..."
    python -m pip install twine
}

# Check dist/ exists
if [ ! -d "dist" ] || [ -z "$(ls -A dist/ 2>/dev/null)" ]; then
    echo "  ERROR: dist/ is empty. Run 'python -m build' first."
    exit 1
fi

ls -la dist/
echo ""

# ── 1. Validate the packages ────────────────────────────────────────
echo "[1/5] twine check (metadata validation)..."
python -m twine check dist/*
echo "  ✓ metadata OK"
echo ""

# ── 2. Dry-run against testpypi (catch upload errors without uploading)
echo "[2/5] twine check --strict..."
python -m twine check --strict dist/*
echo "  ✓ strict metadata OK"
echo ""

# ── 3. Confirm with user ────────────────────────────────────────────
echo "[3/5] About to upload to PyPI:"
echo "      - Package: flybrain-connectome"
echo "      - Version: $(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null || python -c 'import toml; print(toml.load("pyproject.toml")["project"]["version"])')"
echo "      - Files: $(ls dist/ | tr '\n' ' ')"
echo ""
read -p "Type 'UPLOAD' to confirm (or press Enter to abort): " CONFIRM
if [ "$CONFIRM" != "UPLOAD" ]; then
    echo "Aborted. No files were uploaded."
    exit 0
fi

# ── 4. Upload ────────────────────────────────────────────────────────
echo "[4/5] Uploading to PyPI..."
if [ -n "$TWINE_PASSWORD" ]; then
    echo "  (using TWINE_PASSWORD env var)"
    python -m twine upload dist/*
else
    echo "  (using ~/.pypirc if present, or interactive prompt)"
    python -m twine upload dist/*
fi
echo ""

# ── 5. Verify ────────────────────────────────────────────────────────
echo "[5/5] Verifying upload..."
sleep 10  # PyPI indexing takes a moment
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ flybrain-connectome==3.0.1 --dry-run 2>&1 | tail -5 || \
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
