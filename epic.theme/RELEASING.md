# Publish epic.theme to npm

Merging a PR does **not** publish the package. A maintainer publishes a release by pushing a Git tag: a name attached to the exact code being released. GitHub Actions then tests, builds and publishes that code.

These instructions use **2.0.1** as the example. For a later release, replace `2.0.1` everywhere below with the new version.

## 1. Check the one-time GitHub setup

A repository administrator must:

- Create an environment named **npm** in the EPIC.common repository's **Settings → Environments**.
- In npm's `epic.theme` package settings, add a **GitHub Actions Trusted Publisher**: organization `bcgov`, repository `EPIC.common`, workflow filename `publish-epic-theme.yml`, environment `npm`. Enable direct publishing with **npm publish**.
- If the environment has approval rules, allow version tags such as `epic-theme-v2.0.1` and arrange for a release approver.

No `NPM_TOKEN` secret or local `npm login` is needed. npm checks the GitHub workflow's identity using OIDC. The workflow grants this identity permission only to the publishing job and uses npm 11.11.0, which supports trusted publishing.

## 2. Merge the release code

Review and merge the theme PR into **main**, including the publishing workflow. Wait for its validation checks to pass.

The merged `epic.theme/package.json` must contain:

```json
"version": "2.0.1"
```

Its `publishConfig.tag` must be `mui9`. Update the version in a PR before future releases; the workflow does not increase it automatically.

## 3. Download the latest main branch

Open a terminal in your **EPIC.common repository root**, not inside `epic.theme`:

```sh
git fetch origin main
```

Check the package that is actually on main:

```sh
git show origin/main:epic.theme/package.json
```

Find `version` and confirm it is `2.0.1`. **Stop if it still shows the old version:** the release PR has not reached main yet. These commands do not switch your working branch or alter local files.

## 4. Create and push the release tag

```sh
git tag -a epic-theme-v2.0.1 origin/main -m "Release epic.theme 2.0.1"
git push origin epic-theme-v2.0.1
```

The first command creates a local tag on the downloaded main commit. The second sends only that tag to GitHub and **starts the npm release**.

The package version and tag must match exactly: version `2.0.1` requires tag `epic-theme-v2.0.1`. If the tag already exists, stop and check the previous release; do not delete or force-push it.

## 5. Watch the GitHub Action

Open [EPIC.common → Actions → Validate and release epic.theme](https://github.com/bcgov/EPIC.common/actions/workflows/publish-epic-theme.yml).

Open the run for your tag:

1. **validate** installs dependencies, runs tests, builds the theme and checks it in a clean sample application.
2. **publish** sends that tested package to npm. If it says **Waiting for approval**, an authorized reviewer must approve the **npm** environment.
3. Wait for both jobs to succeed. If either fails, read the failed step before retrying; first check whether npm already received the version.

For normal releases, pushing the version tag is the publishing trigger.

To retry an existing tag after changing the publishing workflow, first check that its version has not already been published on npm:

1. Merge the publishing fix into **main**.
2. Open the Actions page above and click **Run workflow**.
3. Select **main** as the branch.
4. Enter `epic-theme-v2.0.1` in **release_tag**, then click **Run workflow**.
5. Watch `validate` and `publish` as described above.

The workflow reads the updated instructions from main but builds and publishes the code at that exact release tag. It checks that the tagged commit belongs to main and that its package version matches the tag. Do not delete or move the old tag. Leaving **release_tag** empty runs validation only. Rerunning the original failed run would still use its old publishing instructions.

## 6. Confirm the package is on npm

```sh
npm view epic.theme@2.0.1 version
npm view epic.theme dist-tags
```

The first command should print `2.0.1`. The tags should include:

```text
latest: 1.0.11
mui9: 2.0.1
```

`mui9` is the label for the new theme. **Keep `latest` on 1.0.11** so existing applications can continue using their current theme. Do not move `latest` to v2.

## 7. Update a consuming application when needed

The documentation-only `2.0.1` release does not require a Submit update. If an application needs to adopt a new theme version, install it explicitly. For Submit, run this from `submit-web`:

```sh
npm install --save-exact epic.theme@2.0.1
```

Confirm its `package.json` now contains `"epic.theme": "2.0.1"` and commit the updated `package.json` and `package-lock.json` together.

Run Submit's lint, unit tests and production build, and complete application testing before deployment. Publishing the theme does not update or deploy Submit automatically. Compliance needs no change.

## If something goes wrong

- **Version not found on npm:** check the tag's Actions run and whether environment approval is pending.
- **Permission/authentication error:** ask an npm package maintainer to check the Trusted Publisher fields above, including the exact workflow filename and `npm` environment, and that direct `npm publish` is allowed. The old `NPM_TOKEN` secret is not used by this workflow.
- **Version already published:** check npm first. A published version cannot be replaced; make corrections in a new version through a new PR and tag.
- **Need to undo a Submit deployment:** deploy the previous Submit image. Do not unpublish the theme or change the legacy `latest` tag.

## Optional: test a prerelease

For an early trial, use a version such as `2.0.1-next.1`, set `publishConfig.tag` to `mui9-next`, and push the matching tag `epic-theme-v2.0.1-next.1`. Follow the same steps above with that version. Stable releases use `mui9`.

## Updating the README after publication

A published npm version cannot be replaced. Updating GitHub's README alone does not update the README included in `epic.theme@2.0.0`. Publish a new patch version, such as `2.0.1`, with the corrected documentation. Do not unpublish or move an existing release tag.

This documentation-only `2.0.1` release changes no theme source or dependencies. Submit can remain on exact version `2.0.0`; adopting the documentation-only patch is optional. Keep `latest` on `1.0.11`.

## Check a change locally

From the `epic.theme` folder, run:

```sh
npm ci
npm test
npm run build
npm run test:package
```

The last command installs the built package in a temporary sample application to check its imports, fonts, types and production build. It needs access to npm.
