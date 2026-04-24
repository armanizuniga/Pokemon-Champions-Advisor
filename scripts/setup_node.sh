#!/bin/bash
set -e

echo "Installing Node.js dependencies for calc bridge..."
cd "$(dirname "$0")/../node"
npm install
echo "Done. @smogon/calc is ready."