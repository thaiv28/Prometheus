#!/usr/bin/env bash
# The benchmark job's one sticky PR comment (.github/workflows/benchmarks.yml).
# Needs `gh` with GH_TOKEN and GH_REPO, and PR (the pull request number).
#
#   benchmark_comment.sh find SHA REPORT_FILE
#       If the sticky comment holds a verdict for commit SHA, print it
#       (pass / fail / skip) and write its report to REPORT_FILE; print nothing
#       otherwise. Lets a label change reuse the verdict without rerunning.
#   benchmark_comment.sh post SHA VERDICT OVERRIDE REPORT_FILE
#       Create or edit the sticky comment: the verdict, whether the
#       `benchmark-override` label is on, and the report.
set -euo pipefail

MARKER="<!-- benchmark-report -->"
mode="$1"
sha="$2"

comment_id() {
    gh api "repos/$GH_REPO/issues/$PR/comments" --paginate \
        --jq ".[] | select(.body | startswith(\"$MARKER\")) | .id" | tail -1
}

if [ "$mode" = find ]; then
    id="$(comment_id)"
    [ -n "$id" ] || exit 0
    body="$(gh api "repos/$GH_REPO/issues/comments/$id" --jq .body)"
    verdict="$(sed -nE "s/^<!-- verdict: (pass|fail|skip) sha: $sha -->$/\1/p" <<<"$body")"
    [ -n "$verdict" ] || exit 0
    sed -n '/^<!-- report -->$/,/^<!-- \/report -->$/p' <<<"$body" | sed '1d;$d' > "$3"
    echo "$verdict"
    exit 0
fi

verdict="$3"
override="$4"
report="$5"
case "$verdict" in
    pass) line="No guarded benchmark value is significantly worse." ;;
    skip) line="No baseline yet: the base commit's benchmark scripts have no \`--dump\`, so there is nothing to compare. Passing." ;;
    fail)
        if [ "$override" = true ]; then
            line="A guarded benchmark check failed, but the \`benchmark-override\` label is on, so the check passes."
        else
            line="A guarded benchmark check failed (a value significantly worse, or AURA's ECE over 0.01), so the check fails. If the change is intended, add the \`benchmark-override\` label (and record why in the work log)."
        fi
        ;;
    *) line="The benchmark comparison didn't finish; see the run log." ;;
esac
body="$(mktemp)"
{
    echo "$MARKER"
    echo "<!-- verdict: $verdict sha: $sha -->"
    echo "### Benchmarks for ${sha:0:7}"
    echo
    echo "$line"
    echo
    echo "<!-- report -->"
    [ -f "$report" ] && cat "$report"
    echo "<!-- /report -->"
    echo
    echo "<sub>Base and head benchmark scripts run with \`--dump\` on DBs built from the same CSVs, compared by \`scripts/compare_benchmarks.py\`.</sub>"
} > "$body"

id="$(comment_id)"
if [ -n "$id" ]; then
    gh api --method PATCH "repos/$GH_REPO/issues/comments/$id" -F "body=@$body" > /dev/null
    echo "Updated comment $id."
else
    gh api --method POST "repos/$GH_REPO/issues/$PR/comments" -F "body=@$body" > /dev/null
    echo "Posted a new comment."
fi
