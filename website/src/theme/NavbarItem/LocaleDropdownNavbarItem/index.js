import React from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useLocation} from '@docusaurus/router';
import clsx from 'clsx';

const LOCALE_LABELS = {
  en: 'ENG',
  ru: 'РУС',
};

const LOCALE_NAMES = {
  en: 'English',
  ru: 'Русский',
};

function ensureLeadingSlash(value) {
  if (!value) {
    return '/';
  }

  return value.startsWith('/') ? value : `/${value}`;
}

function stripBaseUrl(pathname, baseUrl) {
  const normalizedPathname = ensureLeadingSlash(pathname);
  const normalizedBaseUrl = ensureLeadingSlash(baseUrl || '/');
  const baseUrlWithSlash = normalizedBaseUrl.endsWith('/')
    ? normalizedBaseUrl
    : `${normalizedBaseUrl}/`;

  if (normalizedPathname === normalizedBaseUrl.replace(/\/$/, '')) {
    return '/';
  }

  if (normalizedPathname.startsWith(baseUrlWithSlash)) {
    return ensureLeadingSlash(normalizedPathname.slice(baseUrlWithSlash.length));
  }

  return normalizedPathname;
}

function stripLocalePrefix(pathname, locales, defaultLocale) {
  const normalizedPathname = ensureLeadingSlash(pathname);

  for (const locale of locales) {
    if (locale === defaultLocale) {
      continue;
    }

    const prefix = `/${locale}`;

    if (normalizedPathname === prefix) {
      return '/';
    }

    if (normalizedPathname.startsWith(`${prefix}/`)) {
      return ensureLeadingSlash(normalizedPathname.slice(prefix.length));
    }
  }

  return normalizedPathname;
}

function buildLocalePath({pathname, search, hash, baseUrl, locales, defaultLocale, targetLocale}) {
  const pathWithoutBaseUrl = stripBaseUrl(pathname, baseUrl);
  const pathWithoutLocale = stripLocalePrefix(pathWithoutBaseUrl, locales, defaultLocale);
  const localizedPath = targetLocale === defaultLocale
    ? pathWithoutLocale
    : `/${targetLocale}${pathWithoutLocale === '/' ? '/' : pathWithoutLocale}`;

  return `${localizedPath}${search || ''}${hash || ''}`;
}

function getTargetLocale(currentLocale) {
  return currentLocale === 'ru' ? 'en' : 'ru';
}

export default function LocaleDropdownNavbarItem({
  className,
  mobile = false,
  onClick,
}) {
  const {siteConfig, i18n} = useDocusaurusContext();
  const location = useLocation();
  const defaultLocale = i18n?.defaultLocale || siteConfig.i18n?.defaultLocale || 'en';
  const locales = i18n?.locales || siteConfig.i18n?.locales || ['en', 'ru'];
  const currentLocale = i18n?.currentLocale || defaultLocale;
  const targetLocale = getTargetLocale(currentLocale);
  const label = LOCALE_LABELS[targetLocale] || targetLocale.toUpperCase();
  const targetLanguageName = LOCALE_NAMES[targetLocale] || targetLocale;
  const to = buildLocalePath({
    pathname: location.pathname,
    search: location.search,
    hash: location.hash,
    baseUrl: siteConfig.baseUrl,
    locales,
    defaultLocale,
    targetLocale,
  });

  return (
    <Link
      to={to}
      lang={targetLocale}
      hrefLang={targetLocale}
      data-noBrokenLinkCheck
      aria-label={`Switch language to ${targetLanguageName}`}
      title={`Switch language to ${targetLanguageName}`}
      className={clsx(
        mobile ? 'menu__link' : 'navbar__item navbar__link',
        'silamLocaleSwitch',
        className,
      )}
      onClick={onClick}>
      <span className="silamLocaleSwitch__text">{label}</span>
    </Link>
  );
}
