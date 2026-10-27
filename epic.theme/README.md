# EPIC theme

Shared EPIC colours, BC Sans fonts and Material UI component styles for React applications.

## Install

Use theme **2.x** with Material UI **9.5 or later within v9**, React **18.3**, and Emotion **11**. Existing MUI 5 applications should keep theme **1.0.11**. React 19 has not been validated for this release.

```sh
npm install --save-exact epic.theme@2.0.1
```

Your application must also have compatible `@mui/material`, `@emotion/react`, `@emotion/styled`, `react` and `react-dom` packages installed. With React 18, align `react-is` with React:

```sh
npm install --save-exact react-is@18.3.1
```

Add this to your application's `package.json`:

```json
"overrides": {
  "react-is": "18.3.1"
}
```

Use an explicit theme version. The npm `latest` label remains on the legacy theme for existing applications.

## Use the theme

Wrap your application in `ThemeProvider` once:

```tsx
import { Button, ThemeProvider } from '@mui/material';
import { createAppTheme } from 'epic.theme';

const theme = createAppTheme();

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <Button>Save</Button>
    </ThemeProvider>
  );
}
```

This applies the shared colours, typography and component styles. Importing the package also loads the BC Sans font CSS.

## Customize your application

For a few local style changes, use MUI's `sx` prop:

```tsx
<Button sx={{ mt: 2 }}>Save</Button>
```

You can also import `BCDesignTokens` and `EAOColors` for shared colour values.

`createAppTheme` accepts MUI theme options, but replacing `components`, `palette` or `typography` replaces that entire section. To keep the shared defaults while adding component overrides, see the [customization guide](https://github.com/bcgov/EPIC.common/blob/main/epic.theme/CUSTOMIZING.md).

The package includes TypeScript types and uses ES modules for bundler-based applications. Date Pickers are configured separately in the consuming application.

For maintainers: [local checks and release instructions](https://github.com/bcgov/EPIC.common/blob/main/epic.theme/RELEASING.md).
