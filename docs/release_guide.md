# Polaris ERP Agent Release Guide

This repository is the main Polaris AI Agent server application. It is not published as an npm or Python package. Releases are created with Git tags and GitHub Releases.

## Versioning

- Current version: `0.1.0`
- Tag format: `vMAJOR.MINOR.PATCH`
- Use semantic versioning:
  - `PATCH` for bug fixes and documentation-only release corrections.
  - `MINOR` for backward-compatible features.
  - `MAJOR` for breaking API, deployment, or database changes.

## Pre-Release Checklist

Run these commands from the repository root:

```bash
python -m unittest discover -s tests
cd admin
npm ci
npm run build
cd ..
python scripts/check_admin_dist.py
git diff --check
```

If database migrations changed, verify the corresponding files in `database/` and update the relevant database documentation under `docs/`.

## Create A Release

1. Update `VERSION`.
2. Update `CHANGELOG.md`.
3. Commit the release files.
4. Create and push the tag:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin main
git push origin v0.1.0
```

5. Create a GitHub Release from the tag and paste the matching `CHANGELOG.md` section.

## Related Repositories

- Mini-program application: `BennettLocke/polaris-ai-erp-weapp`
- UI component library: `BennettLocke/bennett-locke-ui`
- Device client: `BennettLocke/polaris-xiaoxing-device`
