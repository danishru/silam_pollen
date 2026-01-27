import { themes as prismThemes } from "prism-react-renderer";
import remarkGithubAdmonitions from "remark-github-admonitions-to-directives";

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "SILAM Pollen",
  tagline: "Docs & releases",
  favicon: "img/favicon.ico",

  url: "https://danishru.github.io",
  baseUrl: "/silam_pollen/site/",

  organizationName: "danishru",
  projectName: "silam_pollen",

  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "warn",

  i18n: {
    defaultLocale: "en",
    locales: ["en", "ru"],
  },

  presets: [
    [
      "classic",
      {
        docs: {
          routeBasePath: "docs",
          sidebarPath: "./sidebars.js",
          remarkPlugins: [remarkGithubAdmonitions],
        },
        blog: {
          routeBasePath: "blog",
          showReadingTime: false,
          remarkPlugins: [remarkGithubAdmonitions],
        },
        theme: {
          customCss: "./src/css/custom.css"
        }
      }
    ]
  ],

  themeConfig: {
    navbar: {
      title: "SILAM Pollen",
      items: [
        { to: "/docs/intro", label: "Docs", position: "left" },
        { to: "/blog", label: "Releases", position: "left" },
        { type: "localeDropdown", position: "right" }
      ]
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Project",
          items: [
            { label: "GitHub", href: "https://github.com/danishru/silam_pollen" },
            { label: "Coverage map", href: "https://danishru.github.io/silam_pollen/" }
          ]
        }
      ],
      copyright: `Copyright © ${new Date().getFullYear()}`
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula
    }
  }
};

export default config;
