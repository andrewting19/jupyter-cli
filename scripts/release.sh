#!/bin/bash
#
# Release script for jupyter-cli
#
# Usage:
#   ./scripts/release.sh patch   # 0.1.2 -> 0.1.3
#   ./scripts/release.sh minor   # 0.1.2 -> 0.2.0
#   ./scripts/release.sh major   # 0.1.2 -> 1.0.0
#   ./scripts/release.sh 0.2.0   # Set specific version
#
# Requirements:
#   - PyPI API token in PYPI_TOKEN environment variable
#   - Or ~/.pypirc configured with credentials
#   - pip install build twine
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Files containing version
PYPROJECT="pyproject.toml"
INIT_FILE="jupyter_cli/__init__.py"

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep -E '^version = "' "$PYPROJECT" | sed 's/version = "\(.*\)"/\1/')

if [ -z "$CURRENT_VERSION" ]; then
    echo -e "${RED}Error: Could not determine current version${NC}"
    exit 1
fi

echo -e "${YELLOW}Current version: $CURRENT_VERSION${NC}"

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Determine new version
case "$1" in
    patch)
        NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
        ;;
    minor)
        NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
        ;;
    major)
        NEW_VERSION="$((MAJOR + 1)).0.0"
        ;;
    "")
        echo "Usage: $0 [patch|minor|major|<version>]"
        echo ""
        echo "Examples:"
        echo "  $0 patch    # $CURRENT_VERSION -> $MAJOR.$MINOR.$((PATCH + 1))"
        echo "  $0 minor    # $CURRENT_VERSION -> $MAJOR.$((MINOR + 1)).0"
        echo "  $0 major    # $CURRENT_VERSION -> $((MAJOR + 1)).0.0"
        echo "  $0 1.0.0    # $CURRENT_VERSION -> 1.0.0"
        exit 0
        ;;
    *)
        # Assume it's a specific version
        if [[ ! "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo -e "${RED}Error: Invalid version format. Use X.Y.Z${NC}"
            exit 1
        fi
        NEW_VERSION="$1"
        ;;
esac

echo -e "${GREEN}New version: $NEW_VERSION${NC}"
echo ""

# Confirm
read -p "Proceed with release? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Update version in pyproject.toml
echo "Updating $PYPROJECT..."
sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" "$PYPROJECT"
rm -f "$PYPROJECT.bak"

# Update version in __init__.py
echo "Updating $INIT_FILE..."
sed -i.bak "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" "$INIT_FILE"
rm -f "$INIT_FILE.bak"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info

# Build
echo "Building package..."
python -m build

# Check if PYPI_TOKEN is set
if [ -n "$PYPI_TOKEN" ]; then
    echo "Uploading to PyPI..."
    twine upload dist/* -u __token__ -p "$PYPI_TOKEN"
else
    echo "Uploading to PyPI (using ~/.pypirc)..."
    twine upload dist/*
fi

# Git commit and tag
echo "Creating git commit and tag..."
git add "$PYPROJECT" "$INIT_FILE"
git commit -m "Release v$NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

echo ""
echo -e "${GREEN}Release v$NEW_VERSION complete!${NC}"
echo ""
echo "Next steps:"
echo "  git push origin main"
echo "  git push origin v$NEW_VERSION"
echo ""
echo "PyPI: https://pypi.org/project/jupyter-cli/$NEW_VERSION/"
