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
  tagline: 'rag-api / rag-ent-api / rag-admin 설치·운영·연동 가이드',
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
          editUrl: 'https://github.com/cnapcloud/rag-docs/tree/main/docs/',
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
          alt: 'RAG Platform 로고',
          src: 'img/logo.svg',
        },
        items: [
          {to: '/overview/01-product', label: '개요', position: 'left'},
          {to: '/install/01-requirements', label: '설치', position: 'left'},
          {to: '/operations/01-runbook-k8s', label: '운영', position: 'left'},
          {to: '/reference/01-api-guide', label: '레퍼런스', position: 'left'},
          {to: '/support/01-support-policy', label: '지원', position: 'left'},
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
            title: '문서',
            items: [
              {label: '개요', to: '/overview/01-product'},
              {label: '설치', to: '/install/02-quickstart'},
              {label: '운영', to: '/operations/01-runbook-k8s'},
              {label: '레퍼런스', to: '/reference/01-api-guide'},
            ],
          },
          {
            title: '지원',
            items: [
              {label: '지원 정책', to: '/support/01-support-policy'},
              {label: '릴리스 노트', to: '/support/02-releases'},
              {label: '알려진 제약', to: '/support/03-known-limitations'},
            ],
          },
          {
            title: '리소스',
            items: [
              {label: '데모 시나리오', to: '/demo/01-scenario'},
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
