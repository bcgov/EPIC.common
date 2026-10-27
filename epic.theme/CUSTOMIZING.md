# Customize the shared theme

`createAppTheme` combines supplied options at the top level. Passing a `components`, `palette`, or `typography` object replaces that section; it does not recursively combine it.

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

For an existing styled slot, explicitly retain its base styles (including callbacks/variants) when adding new rules. Configure MUI X Date Pickers in the consuming application; the theme does not install Date Pickers.
