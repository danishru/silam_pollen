import React, {useCallback, useEffect, useRef, useState} from 'react';
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

function CoverageMapFrame({text}) {
  const frameRef = useRef(null);
  const {colorMode} = useColorMode();
  const navbarHeight = useNavbarHeight();

  // Локальный переключатель темы внутри карты скрываем: тема управляется navbar Docusaurus.
  // src намеренно не зависит от colorMode/lang, чтобы React не перезагружал iframe
  // при штатном переключении темы или локали в Docusaurus.
  const src = useBaseUrl('/coverage-map/index.html?themeToggle=0');

  const sendFrameContext = useCallback(() => {
    const frameWindow = frameRef.current?.contentWindow;
    if (!frameWindow) {
      return;
    }

    frameWindow.postMessage(
      {
        type: 'silam-coverage-context',
        theme: colorMode,
        lang: text.lang,
        navbarHeight,
      },
      '*',
    );
  }, [colorMode, navbarHeight, text.lang]);

  const sendNavbarHover = useCallback((hover) => {
    const frameWindow = frameRef.current?.contentWindow;
    if (!frameWindow) {
      return;
    }

    frameWindow.postMessage(
      {
        type: 'silam-coverage-navbar-hover',
        hover,
      },
      '*',
    );
  }, []);

  useEffect(() => {
    sendFrameContext();
  }, [sendFrameContext]);

  useEffect(() => {
    const navbar = document.querySelector('.navbar');
    if (!navbar) {
      return undefined;
    }

    const hideInfoWindow = () => sendNavbarHover(true);

    navbar.addEventListener('pointerenter', hideInfoWindow);
    navbar.addEventListener('focusin', hideInfoWindow);
    navbar.addEventListener('touchstart', hideInfoWindow, {passive: true});

    return () => {
      navbar.removeEventListener('pointerenter', hideInfoWindow);
      navbar.removeEventListener('focusin', hideInfoWindow);
      navbar.removeEventListener('touchstart', hideInfoWindow);
    };
  }, [sendNavbarHover]);

  return (
    <main
      className={`${styles.coveragePage} silamCoveragePage`}
      style={{'--silam-coverage-top': `${navbarHeight}px`}}
    >
      <iframe
        ref={frameRef}
        className={`${styles.coverageFrame} silamCoverageFrame`}
        src={src}
        title={text.iframeTitle}
        loading="eager"
        onLoad={sendFrameContext}
      />
    </main>
  );
}

export default function CoveragePage() {
  const {i18n} = useDocusaurusContext();
  const currentLocale = i18n.currentLocale === 'ru' ? 'ru' : 'en';
  const text = TEXT[currentLocale];

  return (
    <Layout title={text.title} description={text.description} noFooter>
      <CoverageMapFrame text={text} />
    </Layout>
  );
}
