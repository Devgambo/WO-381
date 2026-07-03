/** @type {import('@storybook/react-vite').StorybookConfig} */
export default {
  stories: ["../src/**/*.stories.@(js|jsx|ts|tsx)"],
  // Storybook 9 folds controls/actions/viewport/backgrounds into core, so no
  // addon-essentials needed. Add "@storybook/addon-docs" here if you want
  // autodocs.
  addons: [],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  docs: {},
};
