echo "branch: $(git branch --show-current)"
echo "--- uncommitted:"; git status --short
echo "--- loose assertions / skipped tests:"; grep -rn --include='*.py' "in (400, 403)\|pytest.skip\|xfail" tests/ || echo none
echo "--- plaintext pin fallback:"; grep -n "stored == pin" users/utils.py || echo none
echo "--- PAYMENT_MISMATCH tests:"; grep -rl --include='*.py' "PAYMENT_MISMATCH" tests/ || echo MISSING
echo "--- seed test:"; grep -rl --include='*.py' "seed_demo" tests/ || echo MISSING
echo "--- shift read API:"; grep -n "class ShiftListView\|class ShiftReportView" shifts/views.py || echo MISSING
echo "--- shift report tests:"; grep -rl --include='*.py' "/report/" tests/ || echo MISSING
echo "--- tests:"; if [ -z "${VIRTUAL_ENV:-}" ] && [ -x "../.venv/bin/python" ]; then PYTHON="../.venv/bin/python"; else PYTHON="python"; fi; $PYTHON -m pytest -q 2>&1 | tail -2

