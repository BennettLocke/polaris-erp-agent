# Release Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a clean public versioning and release foundation for the Polaris AI Agent server, mini-program, and UI component library.

**Architecture:** Application repositories publish Git tags and GitHub Releases; the component-library repository becomes an npm-packable package. CI validates each repository before tags are created.

**Tech Stack:** Python 3.11, Flask, React/Vite, uni-app/Vue 3, Node test runner, GitHub Actions, npm package metadata.

---

### Task 1: Main Server Release Foundation

**Files:**
- Create: `Z:\sjagent\VERSION`
- Create: `Z:\sjagent\CHANGELOG.md`
- Create: `Z:\sjagent\docs\release_guide.md`
- Create: `Z:\sjagent\.github\workflows\ci.yml`

- [ ] **Step 1: Add version and changelog**

Create `VERSION` with:

```text
0.1.0
```

Create `CHANGELOG.md` with an initial `v0.1.0` entry for the public server release.

- [ ] **Step 2: Add release guide**

Document that `polaris-erp-agent` is an application repository, not a package. Release flow: run tests, build admin, update changelog, tag `v0.1.0`, push tag, create GitHub Release.

- [ ] **Step 3: Add CI**

Add `.github/workflows/ci.yml` to run:

```bash
python -m unittest discover -s tests
python scripts/check_admin_dist.py
cd admin && npm ci && npm run build
```

Use a Python 3.11 and Node 20 GitHub Actions matrix-free workflow.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m unittest discover -s tests
cd admin
npm ci
npm run build
cd ..
python scripts/check_admin_dist.py
git diff --check
```

### Task 2: Mini Program Release Foundation

**Files:**
- Create: `Z:\肆计包装小程序\商城小程序源码\polaris-ai-erp-weapp\CHANGELOG.md`
- Create: `Z:\肆计包装小程序\商城小程序源码\polaris-ai-erp-weapp\docs\release_guide.md`
- Create: `Z:\肆计包装小程序\商城小程序源码\polaris-ai-erp-weapp\.github\workflows\ci.yml`
- Modify: `Z:\肆计包装小程序\商城小程序源码\polaris-ai-erp-weapp\README.md`

- [ ] **Step 1: Add changelog and release guide**

Document `v0.1.0` as the initial public mini-program release and state compatibility with `polaris-erp-agent >= v0.1.0`.

- [ ] **Step 2: Add CI**

Add a workflow running:

```bash
npm ci
npm run test:unit
npm run build:mp-weixin
```

- [ ] **Step 3: Update README**

Add a short release section explaining that this is an application repository and should be released through Git tags, not npm.

- [ ] **Step 4: Verify**

Run:

```powershell
npm run test:unit
npm run build:mp-weixin
git diff --check
```

### Task 3: Component Library Package Foundation

**Files:**
- Create: `Z:\肆计包装小程序\组件库全新重做\package.json`
- Create: `Z:\肆计包装小程序\组件库全新重做\CHANGELOG.md`
- Create: `Z:\肆计包装小程序\组件库全新重做\.npmignore`
- Create: `Z:\肆计包装小程序\组件库全新重做\.github\workflows\ci.yml`
- Modify: `Z:\肆计包装小程序\组件库全新重做\README.md`

- [ ] **Step 1: Add package metadata**

Create an npm-packable package named `@bennett-locke/polaris-ui`, version `0.1.0`, private `false`, and include only:

```json
[
  "css-components",
  "uni-app-components",
  "preview",
  "README.md",
  "CHANGELOG.md"
]
```

Add scripts:

```json
{
  "test": "node --test tests/*.test.mjs",
  "pack:dry": "npm pack --dry-run"
}
```

- [ ] **Step 2: Add changelog and README package notes**

Document that the package is ready to pack but npm publishing requires an npm account/token.

- [ ] **Step 3: Add CI**

Add a workflow running:

```bash
npm test
npm run pack:dry
```

- [ ] **Step 4: Verify**

Run:

```powershell
node --test tests/*.test.mjs
npm pack --dry-run
git diff --check
```

### Task 4: Commit, Tag, and Push

**Files:**
- All files created or modified above.

- [ ] **Step 1: Commit each repository separately**

Main server:

```powershell
git add -- VERSION CHANGELOG.md docs/release_guide.md docs/superpowers/plans/2026-06-02-release-versioning.md .github/workflows/ci.yml
git commit -m "Add release versioning foundation"
git push origin main
```

Mini program:

```powershell
git add -- CHANGELOG.md docs/release_guide.md .github/workflows/ci.yml README.md
git commit -m "Add mini program release workflow"
git push origin main
```

Component library:

```powershell
git add -- package.json CHANGELOG.md .npmignore .github/workflows/ci.yml README.md
git commit -m "Prepare component library package"
git push origin main
```

- [ ] **Step 2: Create and push tags**

Create tags only after verification passes:

```powershell
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Repeat in all three repositories. Use `git -c safe.directory=*` for the component-library repository if Windows safe-directory protection triggers.

- [ ] **Step 3: Final verification**

Confirm each repository is clean and `HEAD` equals `origin/main`; confirm `v0.1.0` exists locally and on GitHub.
