import React, {useEffect, useState} from 'react';
import Layout from '@theme/Layout';
import useBaseUrl from '@docusaurus/useBaseUrl';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useColorMode} from '@docusaurus/theme-common';
import styles from './coverage.module.css';

const TEXT = {
  en: {
    title: 'Coverage map',
    description: 'SILAM Pollen coverage map',
    iframeTitle: 'SILAM Pollen coverage map',
    lang: 'en',
  },
  ru: {
    title: 'Карта покрытия',
    description: 'Карта покрытия SILAM Pollen',
    iframeTitle: 'Карта покрытия SILAM Pollen',
    lang: 'ru',
  },
};

function useNavbarHeight() {
  const [navbarHeight, setNavbarHeight] = useState(64);

  useEffect(() => {
    const navbar = document.querySelector('.navbar');

    const updateNavbarHeight = () => {
      const height = navbar?.getBoundingClientRect().height || 64;
      setNavbarHeight(Math.ceil(height));
    };

    updateNavbarHeight();

    window.addEventListener('resize', updateNavbarHeight);

    if (!navbar || typeof ResizeObserver === 'undefined') {
      return () => window.removeEventListener('resize', updateNavbarHeight);
    }

    const observer = new ResizeObserver(updateNavbarHeight);
    observer.observe(navbar);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', updateNavbarHeight);
    };
  }, []);

  return navbarHeight;
}

export default function CoveragePage() {
  const {i18n} = useDocusaurusContext();
  const {colorMode} = useColorMode();
  const navbarHeight = useNavbarHeight();

  const currentLocale = i18n.currentLocale === 'ru' ? 'ru' : 'en';
  const text = TEXT[currentLocale];
  const src = useBaseUrl(`/coverage-map/index.html?lng=${text.lang}&theme=${colorMode}`);

  return (
    <Layout title={text.title} description={text.description} noFooter>
      <main
        className={`${styles.coveragePage} silamCoveragePage`}
        style={{'--silam-coverage-top': `${navbarHeight}px`}}
      >
        <iframe
          className={`${styles.coverageFrame} silamCoverageFrame`}
          src={src}
          title={text.iframeTitle}
          loading="eager"
        />
      </main>
    </Layout>
  );
}
