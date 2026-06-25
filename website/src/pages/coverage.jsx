import React from 'react';
import Layout from '@theme/Layout';
import useBaseUrl from '@docusaurus/useBaseUrl';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
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

export default function CoveragePage() {
  const {i18n} = useDocusaurusContext();
  const currentLocale = i18n.currentLocale === 'ru' ? 'ru' : 'en';
  const text = TEXT[currentLocale];

  const src = useBaseUrl(`/coverage-map/index.html?lng=${text.lang}`);

  return (
    <Layout
      title={text.title}
      description={text.description}
      noFooter
    >
      <main className={styles.coverageFullscreenPage}>
        <iframe
          className={styles.coverageFrame}
          src={src}
          title={text.iframeTitle}
          loading="eager"
        />
      </main>
    </Layout>
  );
}
