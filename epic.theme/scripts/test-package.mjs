import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const pkg = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
const temporary = await mkdtemp(join(tmpdir(), "epic-theme-consumer-"));
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const run = (args, cwd = temporary) => execFileSync(npm, args, { cwd, stdio: "inherit" });
try {
  const packed = JSON.parse(execFileSync(npm, ["pack", "--json", "--pack-destination", temporary], { cwd: root, encoding: "utf8" }))[0];
  const files = packed.files.map(({ path }) => path);
  for (const file of ["dist/epic.theme.js", "dist/index.d.ts", "dist/index.css"]) assert(files.includes(file), `Missing ${file}`);
  const bundle = await readFile(join(root, "dist/epic.theme.js"), "utf8");
  assert.match(bundle, /@mui\/material\/styles/);
  assert(bundle.length < 50_000, "The theme must not embed the MUI/React runtime");
  assert.match(await readFile(join(root, "dist/index.css"), "utf8"), /BCSans|BC Sans/);
  const dependencies = Object.fromEntries(["react", "react-dom", "@emotion/react", "@emotion/styled", "@mui/material", "@types/react", "@types/react-dom", "typescript", "vite"].map(name => [name, pkg.devDependencies[name]]));
  dependencies["react-is"] = "18.3.1";
  dependencies["epic.theme"] = `file:${join(temporary, packed.filename)}`;
  await writeFile(join(temporary, "package.json"), JSON.stringify({ private: true, type: "module", dependencies, overrides: { "react-is": "18.3.1" }, scripts: { build: "tsc --noEmit && vite build" } }));
  await writeFile(join(temporary, "tsconfig.json"), JSON.stringify({ compilerOptions: { strict: true, jsx: "react-jsx", target: "ES2022", module: "ESNext", moduleResolution: "bundler", skipLibCheck: true, noEmit: true }, include: ["main.tsx"] }));
  await writeFile(join(temporary, "index.html"), '<div id="root"></div><script type="module" src="/main.tsx"></script>');
  await writeFile(join(temporary, "main.tsx"), `import { createRoot } from 'react-dom/client';
import { Button, ThemeProvider } from '@mui/material';
import { createAppTheme, BCDesignTokens, EAOColors } from 'epic.theme';
const theme = createAppTheme({});
createRoot(document.getElementById('root')!).render(<ThemeProvider theme={theme}><Button variant="dashed" sx={{ color: BCDesignTokens.themePrimaryBlue }}>Consumer {String(Boolean(EAOColors))}</Button></ThemeProvider>);`);
  run(["install", "--ignore-scripts", "--no-audit", "--no-fund"]);
  run(["ls", "react", "@emotion/react", "@mui/material"]);
  run(["run", "build"]);
  process.stdout.write(`Packed consumer passed for epic.theme@${pkg.version}\n`);
} finally {
  await rm(temporary, { recursive: true, force: true });
}
