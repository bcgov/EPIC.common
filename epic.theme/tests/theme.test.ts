import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { Button, ThemeProvider } from "@mui/material";
import { describe, expect, it } from "vitest";
import { satisfies } from "semver";
import { BCDesignTokens, EAOColors, createAppTheme } from "../src/index";
import { releaseChannel } from "../scripts/release-channel.mjs";

const release = { name: "epic.theme", version: "2.0.0", peerDependencies: { "@mui/material": "^9.5.0" }, publishConfig: { tag: "mui9" } };

describe("published theme contract", () => {
  it("retains EPIC defaults and public exports", () => {
    const theme = createAppTheme({});
    expect(theme.palette.primary.main).toBe(BCDesignTokens.themePrimaryBlue);
    expect(theme.typography.fontFamily).toContain("BC Sans");
    expect(theme.components?.MuiButton?.defaultProps).toMatchObject({ variant: "contained", color: "primary" });
    expect(EAOColors).toBeDefined();
  });

  it("renders primary, secondary and disabled buttons with the shared styles", () => {
    const markup = renderToString(createElement(ThemeProvider, { theme: createAppTheme({}) },
      createElement(Button, null, "Submit"),
      createElement(Button, { color: "secondary" }, "Cancel"),
      createElement(Button, { disabled: true }, "Saving"),
    ));
    expect(markup).toContain(BCDesignTokens.surfaceColorPrimaryButtonDefault);
    expect(markup).toContain(BCDesignTokens.surfaceColorSecondaryButtonDefault);
    expect(markup).toContain("disabled");
    expect(markup).toContain("BC Sans");
  });

  it("keeps the supported application options working", () => {
    const theme = createAppTheme({ spacing: 10 });
    expect(theme.spacing(2)).toBe("20px");
    expect(theme.components?.MuiButton).toBeDefined();
  });
});

describe("release isolation", () => {
  it("keeps v2 outside Compliance's existing dependency range", () => {
    expect(satisfies("1.0.11", "^1.0.11")).toBe(true);
    expect(satisfies("2.0.0", "^1.0.11")).toBe(false);
    expect(satisfies("2.0.0-next.0", "^1.0.11")).toBe(false);
  });

  it("uses isolated stable and prerelease channels", () => {
    expect(releaseChannel(release, "epic-theme-v2.0.0")).toBe("mui9");
    expect(releaseChannel({ ...release, version: "2.0.0-next.0", publishConfig: { tag: "mui9-next" } }, "epic-theme-v2.0.0-next.0")).toBe("mui9-next");
  });

  it("rejects latest, wrong release refs and the old major", () => {
    expect(() => releaseChannel({ ...release, publishConfig: { tag: "latest" } }, "epic-theme-v2.0.0")).toThrow();
    expect(() => releaseChannel(release, "main")).toThrow();
    expect(() => releaseChannel({ ...release, peerDependencies: { "@mui/material": "^7.3.0" } }, "epic-theme-v2.0.0")).toThrow();
    expect(() => releaseChannel({ ...release, version: "1.0.11" }, "epic-theme-v1.0.11")).toThrow();
  });
});
