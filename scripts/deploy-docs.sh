#!/bin/bash
# Deploy documentation to GitHub Pages

set -e

echo "Building documentation..."
mkdocs build --clean --strict

echo "Deploying to GitHub Pages..."
mkdocs gh-deploy --force --clean --verbose

echo "Documentation deployed successfully!"
echo "Visit: https://queelius.github.io/ebk/"