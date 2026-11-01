## Summary

<!-- What changes for users, and why? Name the issues this fixes with "Fixes #123": they stay open until the next release and then close with a link to it. -->

## Checklist

- [ ] The title is a Conventional Commit, such as `feat(scope): …` or `fix: …`.
- [ ] Tests cover the change, and `scripts/check.sh` passes; the Docker end-to-end or browser test covers a visible flow.
- [ ] User-facing texts are in `strings.json`, every translation (`de`, `nl`, `fr`, `es`) and every file of the card texts in `frontend/text/`.
- [ ] The documentation in `docs/` is updated in English and German (the `.de.md` pages), and a new file in `changelog.d/` says what changes for users, or `CHANGELOG.md` under Unreleased.
- [ ] Screenshots are regenerated with `bash tests/e2e/screenshots.sh` if a card or dialog looks different.
- [ ] Every commit is signed off (`git commit -s`).
- [ ] Every commit is signed as well (`git commit -S`), with a key that GitHub verifies; the sign-off alone is no signature.
- [ ] No tokens, keys, real board IDs or private addresses are included.

## Test plan

<!-- How did you verify the change? -->
