import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import dts from "vite-plugin-dts";
import { libInjectCss } from "vite-plugin-lib-inject-css";

const sharedRuntimes = ["react", "react-dom", "@mui/material", "@mui/system", "@emotion/react", "@emotion/styled"];

export default defineConfig({
  plugins: [libInjectCss(), dts({ outDir: "dist", insertTypesEntry: true })],
  build: {
    lib: {
      entry: fileURLToPath(new URL("./src/index.ts", import.meta.url)),
      formats: ["es"],
      fileName: () => "epic.theme.js",
      cssFileName: "epic.theme",
    },
    rollupOptions: {
      external: (id) => sharedRuntimes.some((name) => id === name || id.startsWith(`${name}/`)),
    },
  },
});
