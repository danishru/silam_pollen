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
          beforeDefaultRemarkPlugins: [remarkGithubAdmonitions],
        },
        blog: {
          routeBasePath: "blog",
          showReadingTime: false,
          beforeDefaultRemarkPlugins: [remarkGithubAdmonitions],
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
//        { to: "/docs/intro", label: "Docs", position: "left" },
        { to: "/blog", label: "Releases", position: "left" },
        { to: "/coverage", label: "Coverage map", position: "left" },
        { to: "/roadmap", label: "Roadmap", position: "left" },
        {
          type: "localeDropdown",
          position: "right",
          className: "silamLocaleDropdown"
        }
      ]
    },
    footer: {
      style: "light",
      links: [
        {
          title: "Community",
          items: [
            {
              label: "Home Assistant forum",
              href: "https://community.home-assistant.io/t/silam-pollen-allergy-proof-your-home-assistant"
            },
            {
              label: "GitHub issues",
              href: "https://github.com/danishru/silam_pollen/issues"
            }
          ]
        },
        {
          title: "Data source",
          items: [
            {
              label: "SILAM by FMI",
              href: "https://silam.fmi.fi/"
            }
          ]
        }
      ],
      copyright: `© ${new Date().getFullYear()} SILAM Pollen Monitor · Built for Home Assistant`
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula
    }
  }
};

export default config;
