import { readFile } from "node:fs/promises";
import { releaseChannel } from "./release-channel.mjs";

const pkg = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
process.stdout.write(`${releaseChannel(pkg, process.argv[2] ?? process.env.GITHUB_REF_NAME)}\n`);
