export async function resolve(specifier, context, nextResolve) {
  const stubs = {
    "@hermes/plugin-sdk": new URL("./stubs/plugin-sdk.mjs", import.meta.url),
    react: new URL("./stubs/react.mjs", import.meta.url),
    "react/jsx-runtime": new URL("./stubs/jsx-runtime.mjs", import.meta.url),
  }
  if (stubs[specifier]) {
    return { url: stubs[specifier].href, shortCircuit: true }
  }
  return nextResolve(specifier, context)
}
