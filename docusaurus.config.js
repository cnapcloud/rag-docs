// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'RAG Platform',
  tagline: 'RAG API / RAG ENT API / RAG Admin 설치·운영·연동 가이드',
  favicon: 'img/favicon.ico',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://docs.example.com',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'cnapcloud', // Usually your GitHub org/user name.
  projectName: 'rag-docs', // Usually your repo name.

  onBrokenLinks: 'throw',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'ko',
    locales: ['ko'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          routeBasePath: '/',
          numberPrefixParser: false,
          editUrl: 'https://github.com/cnapcloud/rag-docs/tree/main/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Replace with your project's social card
      image: 'img/docusaurus-social-card.jpg',
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'RAG Platform',
        logo: {
          alt: 'RAG Platform logo',
          src: 'img/logo.svg',
        },
        items: [
          {to: '/overview/introduction', label: 'Overview', position: 'left'},
          {to: '/getting-started/quickstart', label: 'Getting Started', position: 'left'},
          {to: '/concepts/architecture', label: 'Concepts', position: 'left'},
          {to: '/guides/rag-api/kb', label: 'Guides', position: 'left'},
          {to: '/reference/api-guide', label: 'Reference', position: 'left'},
          {to: '/support/support-policy', label: 'Support', position: 'left'},
          {to: '/demo/rag-demo', label: 'Demo', position: 'left'},
          {
            href: 'https://github.com/cnapcloud/rag-docs',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {label: 'Overview', to: '/overview/introduction'},
              {label: 'Getting Started', to: '/getting-started/quickstart'},
              {label: 'Concepts', to: '/concepts/architecture'},
              {label: 'Guides', to: '/guides/rag-api/kb'},
              {label: 'Reference', to: '/reference/api-guide'},
            ],
          },
          {
            title: 'Support',
            items: [
              {label: 'Support Policy', to: '/support/support-policy'},
              {label: 'Release Notes', to: '/support/releases-and-compatibility'},
              {label: 'Known Limitations', to: '/support/known-limitations'},
            ],
          },
          {
            title: 'Resources',
            items: [
              {label: 'Demo', to: '/demo/rag-demo'},
              {label: 'GitHub', href: 'https://github.com/cnapcloud/rag-docs'},
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} CNAP Cloud.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
