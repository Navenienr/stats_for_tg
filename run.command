#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ -d ".venv" ]; then
  source ".venv/bin/activate"
fi

python3 main.py
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -ne 0 ]; then
  echo "The script ended with an error (code $EXIT_CODE)."
fi
echo "Press Enter to close this window."
read
exit $EXIT_CODE
