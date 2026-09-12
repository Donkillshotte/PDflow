import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// Next 16 ships native flat configs; FlatCompat treats these configs as
// legacy eslintrc objects and fails with circular plugin metadata.
const eslintConfig = [
  {
    // Release builds contain minified Next output and bundled native assets.
    // They are inputs to packaging, not Studio source, and must not be linted.
    ignores: [
      "**/.next/**",
      "out/**",
      "node-runtime/**",
      "public/monaco/**",
      "src-tauri/target/**",
    ],
  },
  ...nextVitals,
  ...nextTypescript,
  {
    // The isolated preflight test is intentionally CommonJS: it installs a
    // temporary TypeScript loader and exercises the module against a
    // disposable fixture. Keep that loader explicit without weakening the
    // rule for Studio source modules.
    files: ["tests/**/*.cjs"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
  {
    // These rules are opt-in migrations for the React Compiler. Studio still
    // intentionally uses effects for async polling and controlled UI state.
    rules: {
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/preserve-manual-memoization": "off",
    },
  },
];

export default eslintConfig;
