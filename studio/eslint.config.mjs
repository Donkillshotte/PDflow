import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// Next 16 ships native flat configs; FlatCompat treats these configs as
// legacy eslintrc objects and fails with circular plugin metadata.
const eslintConfig = [
  ...nextVitals,
  ...nextTypescript,
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
