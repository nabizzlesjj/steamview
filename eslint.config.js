import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    languageOptions: {
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Steam's internals are untyped by nature; the focus module has to
      // reach into them. Those uses are localised and commented.
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // The library is rendered in Steam's SP window, a different realm
      // from the one this plugin runs in, so `x instanceof Element` is
      // false for every element in it. That one check silently disabled
      // the preview in 1.0-1.2. Use `isElement` from steam/dom.ts.
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "BinaryExpression[operator='instanceof'][right.name=/^(Node|Element|HTML\\w*Element|Document|Window|EventTarget)$/]",
          message:
            "instanceof against a DOM class is false for nodes from Steam's SP window (another realm). Use isElement() from steam/dom.ts.",
        },
      ],
    },
  },
);
