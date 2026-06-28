import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useLocation} from '@docusaurus/router';
import ThemedImage from '@theme/ThemedImage';

const trimSlashes = (value) => value.replace(/^\/+|\/+$/g, '');

const getRelativePathname = (pathname, baseUrl, locales) => {
  let relativePathname = pathname;

  if (baseUrl && relativePathname.startsWith(baseUrl)) {
    relativePathname = relativePathname.slice(baseUrl.length);
  }

  const segments = trimSlashes(relativePathname).split('/').filter(Boolean);

  if (segments.length > 0 && locales.includes(segments[0])) {
    segments.shift();
  }

  return segments.join('/');
};

export default function NavbarLogo() {
  const {siteConfig, i18n} = useDocusaurusContext();
  const {pathname} = useLocation();
  const navbar = siteConfig.themeConfig.navbar ?? {};
  const logo = navbar.logo ?? {};
  const title = navbar.title ?? siteConfig.title;
  const locales = i18n?.locales ?? siteConfig.i18n?.locales ?? [];
  const href = logo.href ?? '/';
  const isHomePage = getRelativePathname(pathname, siteConfig.baseUrl, locales) === '';
  const hasLogo = Boolean(logo.src);
  const logoSrc = useBaseUrl(logo.src ?? '');
  const logoSrcDark = useBaseUrl(logo.srcDark ?? logo.src ?? '');

  return (
    <Link
      aria-current={isHomePage ? 'page' : undefined}
      className={clsx('navbar__brand', isHomePage && 'navbar__brand--active')}
      to={href}>
      {hasLogo ? (
        <ThemedImage
          alt={logo.alt ?? title ?? 'SILAM Pollen'}
          className="navbar__logo"
          height={logo.height}
          sources={{
            light: logoSrc,
            dark: logoSrcDark,
          }}
          width={logo.width}
        />
      ) : null}
      {title ? <b className="navbar__title text--truncate">{title}</b> : null}
    </Link>
  );
}
