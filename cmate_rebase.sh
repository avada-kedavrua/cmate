#!/usr/bin/env bash
# cmate_rebase.sh — one-shot rebase to conventional commits
# Run from the root of the cmate repository:  bash cmate_rebase.sh
#
# Helpers are written to .git/cmate-rebase-helpers/ so they survive
# across shell sessions — if git stops on a conflict you can still
# run `git rebase --continue` from a fresh terminal.

set -euo pipefail

# ── safety check ─────────────────────────────────────────────────────────────
if ! git rev-parse --git-dir &>/dev/null; then
  echo "Error: not inside a git repository." >&2
  exit 1
fi

HELPERS=".git/cmate-rebase-helpers"
mkdir -p "$HELPERS"

# ── safe_commit helper ────────────────────────────────────────────────────────
# Stages each given path individually (skips missing ones), then commits only
# when there is something staged.
# Usage: safe_commit "commit message" path1 path2 ...
cat > "$HELPERS/safe_commit.sh" << 'SAFE_EOF'
#!/usr/bin/env bash
set -euo pipefail
msg="$1"; shift
for path in "$@"; do
    git add -- "$path" 2>/dev/null || echo "[warn] skipped: $path"
done
if git diff --cached --quiet; then
    echo "[skip] nothing staged for: $msg"
else
    git commit -m "$msg"
fi
SAFE_EOF
chmod +x "$HELPERS/safe_commit.sh"
SC="$HELPERS/safe_commit.sh"   # short alias, expanded when split scripts are written

# ── split scripts ─────────────────────────────────────────────────────────────
# Each script: (1) reset the picked commit back to staged-but-not-committed,
#              (2) re-commit in logical slices.

# a3653bd — bootstrap cmate package alongside ConfigChecker prototype
cat > "$HELPERS/s_a3653bd.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "feat: introduce cmate package with DSL engine" cmate/ pyproject.toml .gitignore
$SC "feat(presets): add mindie and vllm preset rule files" presets/
$SC "docs: add initial README" README.md
git add -A
git diff --cached --quiet || git commit -m "chore: remove ConfigChecker prototype and scratch files"
EOF

# 2469598 — extend lexer/parser/visitor + matching tests
cat > "$HELPERS/s_2469598.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "feat(dsl): extend lexer, parser, and visitor with new language features" \
    cmate/lexer.py cmate/parser.py cmate/visitor.py
$SC "test(dsl): add tests for new lexer, parser, and visitor features" tests/
EOF

# 2a4710a — "ut: add uts" mega-commit (license + linter + src + tests)
cat > "$HELPERS/s_2a4710a.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "chore: add Mulan PSL v2 license" LICENSE
$SC "chore: configure lintrunner and add linting adapters" .lintrunner.toml tools/
$SC "chore: update pyproject and package init" pyproject.toml cmate/__init__.py
$SC "docs: update README" README.md
$SC "refactor: update core cmate engine modules" cmate/
$SC "test: add comprehensive test suite for all core modules" tests/
EOF

# cc30b1f — preset + custom_fn/cli + test runner
cat > "$HELPERS/s_cc30b1f.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "feat(presets): update mindie_ep_extension preset" presets/mindie_ep_extension.cmate
$SC "feat(custom_fn): add new custom functions and update cli" cmate/cmate.py cmate/custom_fn.py
$SC "fix(test): update test runner" cmate/_test.py tests/test_test.py
EOF

# 32bc124 — multi-module refactor + tests
cat > "$HELPERS/s_32bc124.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "refactor: overhaul AST, data_source, parser, util, and visitor" \
    cmate/_ast.py cmate/cmate.py cmate/data_source.py cmate/parser.py cmate/util.py cmate/visitor.py
$SC "test: update tests after core refactor" \
    tests/test_ast.py tests/test_cmate.py tests/test_util.py tests/test_visitor.py
EOF

# b199288 — multi-module changes + presets + tests
cat > "$HELPERS/s_b199288.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "feat: extend DSL and update core modules" \
    cmate/_ast.py cmate/_test.py cmate/cmate.py cmate/custom_fn.py \
    cmate/data_source.py cmate/util.py cmate/visitor.py
$SC "feat(presets): update presets for new DSL features" \
    presets/mindie.cmate presets/mindie_ep_extension.cmate
$SC "test: update tests" tests/test_cmate.py tests/test_visitor.py
EOF

# a0abd1f — "v3": major refactor + tests
cat > "$HELPERS/s_a0abd1f.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "refactor: major refactor of core language implementation" cmate/
$SC "test: update tests for core refactor" tests/
EOF

# dbf988e — "v45": new DSL constructs + presets + tests
cat > "$HELPERS/s_dbf988e.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "feat(dsl): add new language constructs to AST, lexer, parser, and visitor" \
    cmate/_ast.py cmate/_test.py cmate/cmate.py cmate/lexer.py cmate/parser.py cmate/visitor.py
$SC "feat(presets): update mindie preset for new language features" presets/mindie.cmate
$SC "test: add tests for new language constructs" tests/test_parser.py tests/test_visitor.py
EOF

# 6f9cce7 — all core modules + presets + all tests
cat > "$HELPERS/s_6f9cce7.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "feat(dsl): add new AST nodes, grammar rules, and evaluation logic" \
    cmate/_ast.py cmate/_test.py cmate/cmate.py cmate/custom_fn.py \
    cmate/lexer.py cmate/parser.py cmate/visitor.py
$SC "feat(presets): add mindie_ep_extension preset" presets/mindie_ep_extension.cmate
$SC "test: add and update tests for new DSL features" tests/
EOF

# 6f40b03 — env script feature (src + test) + docs
cat > "$HELPERS/s_6f40b03.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "feat(cli): add env script generation (--env-script / --no-env-script)" \
    cmate/cmate.py cmate/visitor.py tests/test_env_script.py
$SC "docs: update README and pyproject for env script feature" \
    README.md README_en.md pyproject.toml
EOF

# 84dfc3f — cli fix + docs update (HEAD)
cat > "$HELPERS/s_84dfc3f.sh" << EOF
#!/usr/bin/env bash
set -euo pipefail
git reset HEAD~1
$SC "fix(cli): fix cmate CLI" cmate/cmate.py
$SC "docs: update README and quick start guides" \
    README.md README_CN.md "docs/en/quick_start.md" "docs/zh/quick_start.md"
EOF

chmod +x "$HELPERS"/s_*.sh

# ── sequence-editor shim ──────────────────────────────────────────────────────
# git calls GIT_SEQUENCE_EDITOR <todo-file>; we replace its contents with ours.
SEQ_ED="$HELPERS/seq_editor.sh"
REBASE_TODO="$HELPERS/todo"

cat > "$SEQ_ED" << EOF
#!/usr/bin/env bash
cp "$REBASE_TODO" "\$1"
EOF
chmod +x "$SEQ_ED"

# ── rebase todo ───────────────────────────────────────────────────────────────
H="$HELPERS"

cat > "$REBASE_TODO" << EOF
pick 7ab1fdf x
exec git commit --amend -m "chore: initial project scaffold"
pick a3653bd x
exec $H/s_a3653bd.sh
pick 801ac05 x
exec git commit --amend -m "fix(cli): improve context variable description handling and env target formatting"
pick 6820fb8 x
exec git commit --amend -m "feat(util): add func_timeout utility and reorganize data_source and visitor"
pick 2469598 x
exec $H/s_2469598.sh
pick a12dd72 x
exec git commit --amend -m "refactor(util): replace threading with signals for func_timeout"
pick 7164a67 x
exec git commit --amend -m "fix(parser): correctly handle orelse in nested if-elif-else chains"
pick b16b47f x
exec git commit --amend -m "refactor(visitor): introduce specialized visitor classes"
pick 1cb3afd x
exec git commit --amend -m "test(parser,visitor): enhance expression evaluation and AST test coverage"
pick 2a4710a x
exec $H/s_2a4710a.sh
pick 24974cb x
exec git commit --amend -m "test: add initial test suite for all core modules"
pick 3541ddf x
exec git commit --amend -m "refactor: restructure core modules"
pick d8ef977 x
exec git commit --amend -m "fix(cli): fix cmate orchestration logic"
pick cc30b1f x
exec $H/s_cc30b1f.sh
pick 557fc90 x
exec git commit --amend -m "feat(presets): add mindie_ep_extension preset"
pick 32bc124 x
exec $H/s_32bc124.sh
pick b199288 x
exec $H/s_b199288.sh
pick a0abd1f x
exec $H/s_a0abd1f.sh
pick 8bcdd04 x
exec git commit --amend -m "fix(test): fix test runner"
pick dbf988e x
exec $H/s_dbf988e.sh
pick efdc442 x
exec git commit --amend -m "fix(visitor): fix visitor evaluation logic and update mindie preset"
pick 48db918 x
exec git commit --amend -m "fix(cli): fix CLI argument handling"
pick 119f65a x
exec git commit --amend -m "fix(util,visitor): fix util and visitor edge cases"
pick 02c62d5 x
exec git commit --amend -m "test: expand test coverage across core modules"
pick bb8cc56 x
exec git commit --amend -m "fix(test): update test runner and mindie preset"
pick 6f9cce7 x
exec $H/s_6f9cce7.sh
pick 7d68513 x
exec git commit --amend -m "fix(visitor): fix visitor evaluation and test runner"
pick a8a6966 x
exec git commit --amend -m "docs: add quick start guides (EN/ZH) and update README"
pick 6f40b03 x
exec $H/s_6f40b03.sh
pick 3c90fdc x
exec git commit --amend -m "docs: rename README files and fix pyproject readme reference"
pick 84dfc3f x
exec $H/s_84dfc3f.sh
EOF

# ── launch ────────────────────────────────────────────────────────────────────
echo ""
echo "Starting rebase of $(git rev-list --count HEAD) commits..."
echo "Helpers stored in: $HELPERS"
echo ""

GIT_SEQUENCE_EDITOR="$SEQ_ED" git rebase -i --root

echo ""
echo "✓  Rebase complete. New history:"
git log --oneline
echo ""
echo "When ready to push:"
echo "  git push --force-with-lease"
echo ""
rm -rf "$HELPERS"
