#!/bin/bash
# Ralph - Autonomous Agent Loop for Athlete OS
# Usage: ./ralph.sh [max_iterations]

set -e

MAX_ITERATIONS=${1:-10}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Starting Ralph - Athlete OS Autonomous Agent"
echo "   Max iterations: $MAX_ITERATIONS"
echo "   Project root: $PROJECT_ROOT"
echo ""

cd "$PROJECT_ROOT"

for i in $(seq 1 $MAX_ITERATIONS); do
  echo "═══════════════════════════════════════════"
  echo "═══ Iteration $i of $MAX_ITERATIONS ═══"
  echo "═══════════════════════════════════════════"

  # Pipe prompt to Claude Code
  # Using --dangerously-skip-permissions for autonomous operation
  OUTPUT=$(cat "$SCRIPT_DIR/prompt.md" \
    | claude --dangerously-skip-permissions 2>&1 \
    | tee /dev/stderr) || true

  # Check for completion signal
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo ""
    echo "✅ All stories complete!"
    echo "   Check git log for commits"
    echo "   Check scripts/ralph/progress.txt for learnings"
    exit 0
  fi

  # Brief pause between iterations
  sleep 2
done

echo ""
echo "⚠️  Max iterations ($MAX_ITERATIONS) reached"
echo "    Some stories may still be incomplete"
echo "    Run again to continue: ./ralph.sh"
exit 1
