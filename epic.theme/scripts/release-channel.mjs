export function releaseChannel(pkg, ref) {
  if (pkg.name !== "epic.theme" || !/^2\.\d+\.\d+(?:-[\w.-]+)?$/.test(pkg.version)) {
    throw new Error("This release workflow only publishes epic.theme v2.");
  }
  if (!pkg.peerDependencies?.["@mui/material"]?.startsWith("^9.")) {
    throw new Error("A v2 release must require Material UI v9.");
  }
  if (ref !== `epic-theme-v${pkg.version}`) {
    throw new Error("The release tag must match the package version.");
  }
  const channel = pkg.version.includes("-") ? "mui9-next" : "mui9";
  if (pkg.publishConfig?.tag !== channel) {
    throw new Error(`publishConfig.tag must be ${channel}; latest is reserved for existing consumers.`);
  }
  return channel;
}
