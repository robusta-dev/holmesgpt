#!/bin/bash
# Publish HolmesGPT to PyPI
# Usage: ./scripts/publish-pypi.sh [version]
# If no version is provided, it will use the latest git tag

set -e

# Get version from argument or latest git tag
VERSION=${1:-$(git describe --tags --abbrev=0)}

if [ -z "$VERSION" ]; then
    echo "Error: No version provided and no git tags found"
    echo "Usage: $0 [version]"
    exit 1
fi

echo "Publishing HolmesGPT version: $VERSION"

# Check if PYPI_TOKEN is set
if [ -z "$PYPI_TOKEN" ]; then
    echo "Error: PYPI_TOKEN environment variable is not set"
    echo "Please set PYPI_TOKEN to your PyPI API token"
    exit 1
fi

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Error: Poetry is not installed"
    echo "Please install Poetry first: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Ask for confirmation
echo "This will:"
echo "  1. Update version in holmes/__init__.py and pyproject.toml to $VERSION"
echo "  2. Build and publish the package to PyPI"
echo "  3. Restore original files"
echo ""
read -p "Are you sure you want to publish version $VERSION to PyPI? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Update package version using sed (same as CI workflows)
echo "Updating package version to $VERSION..."
sed -i.bak 's/__version__ = .*/__version__ = "'$VERSION'"/g' holmes/__init__.py
sed -i.bak 's/version = "0.0.0"/version = "'$VERSION'"/g' pyproject.toml

# Install dependencies (Poetry will use its own virtualenv)
echo "Installing dependencies..."
poetry install --no-root

# Build and publish
echo "Building and publishing to PyPI..."
poetry publish --build -u __token__ -p $PYPI_TOKEN

# Restore original files
echo "Restoring original files..."
mv holmes/__init__.py.bak holmes/__init__.py
mv pyproject.toml.bak pyproject.toml

echo "Successfully published HolmesGPT $VERSION to PyPI!"
