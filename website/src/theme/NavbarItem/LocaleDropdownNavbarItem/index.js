import React from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useLocation} from '@docusaurus/router';
import {useAlternatePageUtils} from '@docusaurus/theme-common/internal';
import clsx from 'clsx';

const LOCALE_LABELS = {
  en: 'ENG',
  ru: 'РУС',
};

const LOCALE_NAMES = {
  en: 'English',
  ru: 'Русский',
};

function getTargetLocale(currentLocale) {
  return currentLocale === 'ru' ? 'en' : 'ru';
}

export default function LocaleDropdownNavbarItem({
  className,
  mobile = false,
  onClick,
  queryString = '',
}) {
  const {
    i18n: {currentLocale, localeConfigs},
  } = useDocusaurusContext();
  const {search, hash} = useLocation();
  const alternatePageUtils = useAlternatePageUtils();
  const targetLocale = getTargetLocale(currentLocale);
  const label = LOCALE_LABELS[targetLocale] || targetLocale.toUpperCase();
  const targetLanguageName = LOCALE_NAMES[targetLocale] || targetLocale;
  const htmlLang = localeConfigs[targetLocale]?.htmlLang || targetLocale;
  const baseTo = `pathname://${alternatePageUtils.createUrl({
    locale: targetLocale,
    fullyQualified: false,
  })}`;
  const to = `${baseTo}${search}${hash}${queryString}`;

  return (
    <Link
      to={to}
      target="_self"
      autoAddBaseUrl={false}
      lang={htmlLang}
      hrefLang={htmlLang}
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
