export default {
  title: "SILAM Pollen",
  url: "https://danishru.github.io",
  baseUrl: "/silam_pollen/site/",
  organizationName: "danishru",
  projectName: "silam_pollen",

  i18n: {
    defaultLocale: "en",
    locales: ["en", "ru"],
  },

  themeConfig: {
    navbar: {
      items: [
        { type: "localeDropdown", position: "right" },
        { to: "/blog", label: "Releases", position: "left" },
        { to: "/docs/intro", label: "Docs", position: "left" },
      ],
    },
  },
};
