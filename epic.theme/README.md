# EPIC theme — Material UI v9

`epic.theme` provides EPIC design tokens, BC Sans fonts, component defaults and `createAppTheme`.

## Compatibility

| Theme line | Material UI | React | Release channel |
| --- | --- | --- | --- |
| Existing `1.0.11` | Existing v5 applications | Existing supported versions | Existing `latest`, unchanged |
| `2.0.0` | `^9.5.0` | React / React DOM `^18.3.1` | `mui9` |

The validated v2 build uses Node 24, TypeScript 5.9 and Emotion 11. React 19 is a separate validation exercise. The package is ESM and targets bundler-based applications; the old UMD build is not part of v2.

Compliance's existing `^1.0.11` dependency excludes v2 and needs no modification. Other consumers using `latest` remain on the existing channel. Do not move `latest`, unpublish v1, or publish v9 changes in a v1 release.

## Application usage

After the v2 release is published, install its numeric version explicitly:

```sh
npm install --save-exact epic.theme@2.0.0
```

Install compatible MUI/React/Emotion peers in the application. On React 18, install `react-is@18.3.1` and set the application's `overrides.react-is` to `18.3.1` as MUI documents.

```tsx
import { ThemeProvider } from '@mui/material/styles';
import { createAppTheme } from 'epic.theme';

const theme = createAppTheme({});

export function App() {
  return <ThemeProvider theme={theme}>{/* Application */}</ThemeProvider>;
}
```

The root import includes BC Sans font CSS automatically. `epic.theme/style.css` is also exported for CSS tooling. No new global CSS reset is introduced.

`BCDesignTokens`, `EAOColors`, and the existing custom Button variant type augmentation remain public.

## Application-specific overrides

The existing helper uses a shallow spread for supplied options. Passing a `components`, `palette`, or `typography` object replaces that section; it does not recursively combine it. This migration preserves that behaviour.

To add application-specific component keys, compose them explicitly with the base theme:

```tsx
import { createTheme } from '@mui/material/styles';
import { createAppTheme } from 'epic.theme';

const base = createAppTheme({});
export const theme = createTheme({
  ...base,
  components: {
    ...base.components,
    MuiPaper: {
      ...base.components?.MuiPaper,
      styleOverrides: { root: { boxShadow: 'none' } },
    },
  },
});
```

For an existing styled slot, explicitly retain its base styles (including callbacks/variants) when adding new rules. MUI X picker-specific integration remains in Submit, so this package does not require Date Pickers.

## Validation

```sh
npm ci
npm test
npm run build
npm run test:package
```

The package test packs the built files and installs them in a disposable clean consumer. It verifies strict peer resolution, font CSS, public declarations, Button augmentation and a production Vite build. Network access to npm is needed for the clean installation.

## Release procedure

1. Review/merge the publishing safeguards before the theme migration reaches `main`.
2. For a prerelease, use `2.0.0-next.N` and set `publishConfig.tag` to `mui9-next`.
3. For stable v2, use its numeric version and `publishConfig.tag: mui9`.
4. The matching source tag is `epic-theme-v<version>`; only such v2 tags trigger publication after validation.
5. The workflow publishes the validated tarball and checks that `latest` did not change. If it did, investigate; do not overwrite a concurrent release automatically.
6. Submit adopts the published numeric version and reruns its production checks before deployment. No Compliance release or dependency change is required.

Publishing/deployment remain release actions. Local package tests and source changes do not publish anything.
