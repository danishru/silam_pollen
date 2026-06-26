import React, {useMemo} from 'react';
import OriginalNavbar from '@theme-original/Navbar';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useColorMode} from '@docusaurus/theme-common';

function localeLabel(locale) {
  if (locale === 'ru') {
    return 'RUS';
  }
  if (locale === 'en') {
    return 'ENG';
  }
  return String(locale || 'LANG').slice(0, 3).toUpperCase();
}

function buildLocaleTargetHref({baseUrl, currentLocale, defaultLocale, targetLocale}) {
  if (typeof window === 'undefined') {
    return baseUrl || '/';
  }

  const url = new URL(window.location.href);
  const cleanBaseUrl = baseUrl || '/';
  const normalizedBase = cleanBaseUrl.endsWith('/')
    ? cleanBaseUrl.slice(0, -1)
    : cleanBaseUrl;

  let localPath = url.pathname;
  if (cleanBaseUrl !== '/' && localPath.startsWith(cleanBaseUrl)) {
    localPath = localPath.slice(cleanBaseUrl.length);
  }
  localPath = `/${localPath.replace(/^\/+/, '')}`;

  if (currentLocale !== defaultLocale) {
    const currentPrefix = `/${currentLocale}`;
    if (localPath === currentPrefix) {
      localPath = '/';
    } else if (localPath.startsWith(`${currentPrefix}/`)) {
      localPath = localPath.slice(currentPrefix.length);
    }
  }

  if (targetLocale !== defaultLocale) {
    localPath = `/${targetLocale}${localPath === '/' ? '' : localPath}`;
  }

  return `${normalizedBase}${localPath}${url.search}${url.hash}`;
}

function MobileTopbarControls() {
  const {siteConfig, i18n} = useDocusaurusContext();
  const {colorMode, setColorMode} = useColorMode();
  const currentLocale = i18n.currentLocale;
  const defaultLocale = i18n.defaultLocale;
  const targetLocale = (i18n.locales || []).find((locale) => locale !== currentLocale) || defaultLocale;
  const targetHref = useMemo(
    () => buildLocaleTargetHref({
      baseUrl: siteConfig.baseUrl,
      currentLocale,
      defaultLocale,
      targetLocale,
    }),
    [siteConfig.baseUrl, currentLocale, defaultLocale, targetLocale],
  );
  const nextColorMode = colorMode === 'dark' ? 'light' : 'dark';

  return React.createElement(
    'div',
    {className: 'silamMobileTopbarControls', 'aria-label': 'Mobile display controls'},
    React.createElement(
      'a',
      {
        className: 'silamMobileLanguageButton',
        href: targetHref,
        'aria-label': `Switch language to ${targetLocale}`,
        title: `Switch language to ${targetLocale}`,
      },
      localeLabel(currentLocale),
    ),
    React.createElement(
      'button',
      {
        type: 'button',
        className: 'silamMobileThemeButton',
        onClick: () => setColorMode(nextColorMode),
        'aria-label': `Switch to ${nextColorMode} mode`,
        title: `Switch to ${nextColorMode} mode`,
      },
      React.createElement('span', {className: 'silamMobileThemeIcon', 'aria-hidden': 'true'}, colorMode === 'dark' ? '☀' : '☾'),
    ),
  );
}

export default function NavbarWrapper(props) {
  return React.createElement(
    React.Fragment,
    null,
    React.createElement(OriginalNavbar, props),
    React.createElement(MobileTopbarControls),
  );
}
