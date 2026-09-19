#!/usr/bin/env bash
# ==============================================================================
# Voxlery — Automated Uninstallation Script (macOS & Linux)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "  Voxlery Uninstallation Utility (macOS / Linux)"
echo "  Safe Cleanup · Privacy Preserving · Photos Untouched"
echo "====================================================================="
echo ""
echo "Note: Original photo files on your disk will NEVER be touched or deleted."
echo ""

DO_REMOVE_DATA=false
DO_REMOVE_VENV=false
DO_REMOVE_MODELS=false
NON_INTERACTIVE=false

# Check CLI arguments
for arg in "$@"; do
    case "$arg" in
        --all|--purge)
            DO_REMOVE_DATA=true
            DO_REMOVE_VENV=true
            DO_REMOVE_MODELS=true
            NON_INTERACTIVE=true
            ;;
        -y|--yes)
            NON_INTERACTIVE=true
            DO_REMOVE_DATA=true
            DO_REMOVE_VENV=true
            ;;
        --remove-models)
            DO_REMOVE_MODELS=true
            ;;
        --keep-models)
            DO_REMOVE_MODELS=false
            ;;
    esac
done

if [ "$NON_INTERACTIVE" = false ]; then
    read -p "1. Remove library database, thumbnails, and vector index (~/.voxlery)? [Y/n] " ans_data
    if [[ ! "$ans_data" =~ ^[Nn] ]]; then
        DO_REMOVE_DATA=true
    fi

    read -p "2. Remove isolated Python virtual environment (.venv) and build cache? [Y/n] " ans_venv
    if [[ ! "$ans_venv" =~ ^[Nn] ]]; then
        DO_REMOVE_VENV=true
    fi

    read -p "3. Do you also want to remove downloaded Ollama AI models (moondream, gemma4:e2b)? [y/N] " ans_models
    if [[ "$ans_models" =~ ^[Yy] ]]; then
        DO_REMOVE_MODELS=true
    fi
    echo ""
fi

# 1. Remove User Data Directory (~/.voxlery and legacy ~/.pixelmemory)
if [ "$DO_REMOVE_DATA" = true ]; then
    VOXLERY_DATA="$HOME/.voxlery"
    if [ -d "$VOXLERY_DATA" ]; then
        echo "[*] Removing Voxlery data directory ($VOXLERY_DATA)..."
        rm -rf "$VOXLERY_DATA"
        echo "[OK] Removed: $VOXLERY_DATA"
    else
        echo "[i] No data directory found at $VOXLERY_DATA"
    fi

    LEGACY_DATA="$HOME/.pixelmemory"
    if [ -d "$LEGACY_DATA" ]; then
        echo "[*] Removing legacy data directory ($LEGACY_DATA)..."
        rm -rf "$LEGACY_DATA"
        echo "[OK] Removed: $LEGACY_DATA"
    fi
fi

# 2. Remove Virtual Environment and Build Artifacts
if [ "$DO_REMOVE_VENV" = true ]; then
    if [ -d ".venv" ]; then
        echo "[*] Removing Python virtual environment (.venv)..."
        rm -rf ".venv"
        echo "[OK] Removed virtual environment (.venv)"
    fi

    if [ -d "node_modules" ]; then
        echo "[*] Removing node_modules..."
        rm -rf "node_modules"
        echo "[OK] Removed node_modules"
    fi

    if [ -d "src-tauri/target" ]; then
        echo "[*] Removing desktop build artifacts (src-tauri/target)..."
        rm -rf "src-tauri/target"
        echo "[OK] Removed src-tauri/target"
    fi

    # Clean __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
fi

# 3. Remove Ollama AI Models
if [ "$DO_REMOVE_MODELS" = true ]; then
    echo ""
    echo "── Ollama Model Removal ───────────────────────────────────────────"
    if command -v ollama >/dev/null 2>&1; then
        for model in "moondream" "gemma4:e2b"; do
            echo "[*] Removing Ollama model '$model'..."
            if ollama rm "$model" 2>/dev/null; then
                echo "[OK] Removed model: $model"
            else
                echo "[i] Model '$model' was not installed or already removed."
            fi
        done
    else
        echo "[!] Ollama command line tool not found. Skipping model removal."
    fi
fi

echo ""
echo "====================================================================="
echo "  [OK] Voxlery Uninstallation Complete!"
echo "====================================================================="
echo ""
