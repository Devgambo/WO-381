import "../src/index.css";

/** @type {import('@storybook/react').Preview} */
export default {
  parameters: {
    layout: "fullscreen",
    backgrounds: {
      default: "app",
      values: [{ name: "app", value: "#0a0a0b" }],
    },
    controls: {
      matchers: { color: /(background|color)$/i, date: /Date$/i },
    },
  },
};
