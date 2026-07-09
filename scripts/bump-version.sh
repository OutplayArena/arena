#!/usr/bin/env bash
#
# bump-version.sh — Bump the OutplayArena version across all version files.
#
# Usage: scripts/bump-version.sh <version> [--date YYYY-MM-DD]
#
# Updates four files:
#   1. backend/pyproject.toml      → version = "X.Y.Z"
#   2. frontend/package.json       → "version": "X.Y.Z"
#   3. helm/arena/Chart.yaml        → version: X.Y.Z and appVersion: "X.Y.Z"
#   4. agent-sdk/CHANGELOG.md       → promote ## [Unreleased] → ## [X.Y.Z] - <date>
#
# The SDK package version is VCS-derived (hatch-vcs) so it needs no manual
# bump — pushing the git tag vX.Y.Z drives the SDK version automatically.
#
# The changelog content curation stays manual; this script only creates the
# header and link reference. Fill the body afterwards.
#
# Idempotent: files already at the target version are skipped.
#
set -euo pipefail

# ──── helpers ──────────────────────────────────────────────────────────────

die() { echo "::error:: $*" >&2; exit 1; }

version_files=(
    "backend/pyproject.toml"
    "frontend/package.json"
    "helm/arena/Chart.yaml"
)
changelog="agent-sdk/CHANGELOG.md"

# ──── usage ────────────────────────────────────────────────────────────────

usage() {
    cat <<'EOF'
Usage: scripts/bump-version.sh <version> [--date YYYY-MM-DD]

Arguments:
  version           Target version, e.g. "0.4.0" or "v0.4.0"
  --date            Release date (ISO 8601, default: today)

Files updated:
  backend/pyproject.toml          version field
  frontend/package.json            version field
  helm/arena/Chart.yaml            version + appVersion
  agent-sdk/CHANGELOG.md           [Unreleased] → [X.Y.Z] section header + link

SDK version is VCS-derived (hatch-vcs); no manual bump needed.
EOF
    exit "${1:-0}"
}

# ──── parse args ───────────────────────────────────────────────────────────

raw_version=""
release_date=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage 0 ;;
        --date)
            shift
            release_date="$1"
            [[ "$release_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || die "--date must be YYYY-MM-DD"
            ;;
        *) [[ -z "$raw_version" ]] && raw_version="$1" || die "unexpected argument: $1" ;;
    esac
    shift
done

[[ -n "$raw_version" ]] || die "version is required (e.g. 0.4.0)"
[[ -z "$release_date" ]] && release_date="$(date +%Y-%m-%d)"

# Strip leading 'v'
version="${raw_version#v}"

# Validate semver-ish (X.Y.Z with optional pre-release suffix)
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\S*)?$ ]] || die "invalid version: $version (expected X.Y.Z)"

# Resolve repo root
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not in a git repository"
cd "$repo_root"

# ──── bump version files ───────────────────────────────────────────────────

bumped=()
skipped=()

for f in "${version_files[@]}"; do
    [[ -f "$f" ]] || die "file not found: $f"

    case "$f" in
        backend/pyproject.toml)
            current=$(grep -m1 '^version = "' "$f" | sed -E 's/.*"(.*)".*/\1/')
            [[ "$current" == "$version" ]] && {
                skipped+=("$f (already $version)")
                continue
            }
            sed -i -E "s/^version = \".*\"/version = \"$version\"/" "$f"
            bumped+=("$f: $current → $version")
            ;;
        frontend/package.json)
            current=$(grep -m1 '"version"' "$f" | sed -E 's/.*"version": *"(.*)".*/\1/')
            [[ "$current" == "$version" ]] && {
                skipped+=("$f (already $version)")
                continue
            }
            sed -i -E "s/\"version\": *\"[^\"]*\"/\"version\": \"$version\"/" "$f"
            bumped+=("$f: $current → $version")
            ;;
        helm/arena/Chart.yaml)
            current_version=$(grep -m1 '^version: ' "$f" | awk '{print $2}')
            current_appver=$(grep -m1 '^appVersion: ' "$f" | sed -E 's/.*"(.*)".*/\1/')
            [[ "$current_version" == "$version" && "$current_appver" == "$version" ]] && {
                skipped+=("$f (already $version)")
                continue
            }
            sed -i -E "s/^version: .*/version: $version/" "$f"
            sed -i -E "s/^appVersion: \".*\"/appVersion: \"$version\"/" "$f"
            bumped+=("$f: version $current_version → $version, appVersion $current_appver → $version")
            ;;
    esac
done

# ──── changelog ────────────────────────────────────────────────────────────

if [[ -f "$changelog" ]]; then
    current_target="## [$version]"
    if grep -qF "$current_target" "$changelog"; then
        skipped+=("$changelog (already has [$version] section)")
    elif grep -qF "## [Unreleased]" "$changelog"; then
        # Replace the Unreleased header with the new version header
        sed -i -E "s/^## \[Unreleased\]/## [$version] - $release_date/" "$changelog"

        # Prepend a fresh Unreleased section above it
        # Use a temp file to insert lines before the matched version header
        tmp="$(mktemp)"
        awk -v ver="$version" '
            $0 == "## ["ver"]" { print "## [Unreleased]"; print ""; }
            { print }
        ' "$changelog" > "$tmp"
        mv "$tmp" "$changelog"

        # Append link reference at the bottom (before the [Unreleased] link)
        unreleased_line="[Unreleased]: https://github.com/OutplayArena/arena/compare/v$version...HEAD"
        compare_line="[$version]: https://github.com/OutplayArena/arena/releases/tag/v$version"

        # If there's a [Unreleased] compare link, insert the new link before it
        if grep -qF "$unreleased_line" "$changelog" 2>/dev/null; then
            sed -i -E "s#^\[Unreleased\].*#$compare_line\n$unreleased_line#" "$changelog"
        else
            # Just append
            echo "$compare_line" >> "$changelog"
        fi

        bumped+=("$changelog: [Unreleased] → [$version] - $release_date")
    else
        echo "::warning:: $changelog has no [Unreleased] section — skipping changelog promotion" >&2
        skipped+=("$changelog (no [Unreleased] header)")
    fi
else
    echo "::warning:: $changelog not found — skipping" >&2
    skipped+=("$changelog (not found)")
fi

# ──── summary ──────────────────────────────────────────────────────────────

echo ""
echo "=== Version bump: $version (date: $release_date) ==="
echo ""
if [[ ${#bumped[@]} -gt 0 ]]; then
    echo "Bumped:"
    for b in "${bumped[@]}"; do echo "  - $b"; done
fi
if [[ ${#skipped[@]} -gt 0 ]]; then
    echo "Skipped:"
    for s in "${skipped[@]}"; do echo "  - $s"; done
fi
echo ""
echo "Next steps:"
echo "  1. Edit agent-sdk/CHANGELOG.md to add release notes under [${version}]"
echo "  2. Create docs/releases/v${version}.md with curated release notes"
echo "  3. Commit, PR to dev, then PR dev → main"
echo "  4. Tag v${version} on the merge commit to trigger release workflows"