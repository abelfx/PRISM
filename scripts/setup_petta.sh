#!/usr/bin/env bash
set -euo pipefail

# setup_petta.sh — Sets up PeTTa and PLN integration for PRISM
# Used by CI and local developer setup.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRISM_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd "${PRISM_DIR}/.." && pwd)"
PETTA_DIR="${PARENT_DIR}/PeTTa"
PLN_REPO="${PLN_REPO:-https://github.com/abelfx/PLN.git}"
PLN_BRANCH="${PLN_BRANCH:-feat/synthetic_evaluation}"

echo "=== PRISM PeTTa Integration Setup ==="
echo "PRISM Dir:   ${PRISM_DIR}"
echo "PeTTa Dir:   ${PETTA_DIR}"
echo "PLN Repo:    ${PLN_REPO}"
echo "PLN Branch:  ${PLN_BRANCH}"

# 1. Clone PeTTa if missing
if [ ! -d "${PETTA_DIR}" ]; then
    echo "Cloning PeTTa..."
    git clone --depth 1 https://github.com/trueagi-io/PeTTa.git "${PETTA_DIR}"
else
    echo "PeTTa already present."
fi

# 2. Clone PLN fork if missing
PLN_DIR="${PETTA_DIR}/repos/PLN"
if [ ! -d "${PLN_DIR}" ]; then
    echo "Cloning PLN fork into PeTTa/repos/PLN..."
    mkdir -p "${PETTA_DIR}/repos"
    git clone -b "${PLN_BRANCH}" --depth 1 "${PLN_REPO}" "${PLN_DIR}"
else
    echo "PLN already present."
fi

# 3. Ensure PRISM symlink inside PeTTa
if [ ! -e "${PETTA_DIR}/prism" ]; then
    echo "Creating symlink PeTTa/prism -> ${PRISM_DIR}..."
    ln -s "${PRISM_DIR}" "${PETTA_DIR}/prism"
else
    echo "Symlink PeTTa/prism already exists."
fi

echo "=== PeTTa Setup Completed Successfully ==="
