import {useEffect} from 'react';

// Универсальный runtime для горизонтальной anchor-навигации.
// Страница должна предоставить разметку с data-anchor-strip-* атрибутами.

export default function AnchorStripRuntime() {
  useEffect(() => {
    const cleanupHandlers = [];

    const initAnchorStrip = (root) => {
      const shell = root.closest('[data-anchor-strip-shell]') || root.parentElement;
      const layout = root.closest('[data-anchor-strip-layout]') || shell?.closest?.('[data-anchor-strip-layout]') || shell;
      const stickyHost = layout || shell;
      const viewport = root.querySelector('[data-anchor-strip-scroller]');
      const track = viewport?.firstElementChild;
      const prev = root.querySelector('[data-anchor-strip-prev]');
      const next = root.querySelector('[data-anchor-strip-next]');

      if (!shell || !layout || !viewport || !track || !prev || !next || root.dataset.anchorStripReady === 'true') {
        return null;
      }

      root.dataset.anchorStripReady = 'true';
      let offset = 0;
      let compactFrame = 0;
      let resizeFrame = 0;
      let isCompact = shell.dataset.anchorStripCompact === 'true';
      let compactBaseScrollY = 0;
      const compactStickyOffset = 8;
      const mobileCompactExitGap = 32;
      const mobileDockScrollDelta = 3;
      const mobileReturnProgressReleaseThreshold = 0.995;
      const mobileReturnSettleMs = 160;
      const compactTransitionLockMs = 840;
      let compactLockUntil = 0;
      let pendingDesktopAnchorCompactFreeze = false;
      let pendingDesktopAnchorCompactFreezeTarget = null;
      let pendingDesktopAnchorCompactFreezeFrame = 0;
      let pendingDesktopAnchorCompactFreezeTimer = 0;
      let pendingDesktopAnchorCompactFreezeLastScrollY = null;
      let pendingDesktopAnchorCompactFreezeStableFrames = 0;
      let pendingDesktopAnchorCompactFreezeStartedAt = 0;
      let isMobileBottomDocked = layout.dataset.anchorStripMobileBottomDocked === 'true';
      let isMobileBottomReturning = layout.dataset.anchorStripMobileBottomReturning === 'true';
      let lastMobileBottomScrollY = Math.max(0, window.scrollY || 0);
      let mobileBottomReturnStartedAt = 0;
      let mobileBottomPlaceholderMode = '';
      let mobileBottomFlowMargin = 0;
      let mobileBottomFlowMarginTop = 0;
      let mobileBottomSettleTimer = 0;
      let mobileBottomPlaceholderFrame = 0;
      let mobileBottomPlaceholderFrameKey = '';
      let isMobileNavbarHidden = document.documentElement.dataset.anchorMobileNavbarHidden === 'true';
      let isMobileAnchorScrollNavbarLocked = false;
      let mobileAnchorScrollNavbarTargetY = null;
      let mobileAnchorScrollNavbarFrame = 0;
      let mobileAnchorScrollNavbarFallbackTimer = 0;
      let mobileAnchorScrollNavbarReleaseTimer = 0;
      let mobileAnchorScrollDockFreezeTarget = null;
      let mobileAnchorScrollDockFreezeTimer = 0;
      const mobileAnchorScrollDockFreezeTimeoutMs = 3600;
      let lastMobileNavbarScrollY = Math.max(0, window.scrollY || 0);
      const mobileNavbarScrollDelta = 6;
      const mobileNavbarTopRevealOffset = 24;
      const mobileAnchorScrollNavbarFallbackMs = 2200;
      const mobileAnchorScrollNavbarSettleMs = 520;
      let resizeObserver = null;
      let isDisposed = false;
      const activeFrameIds = new Set();
      const activeTimerIds = new Set();
      let externalAnchorLinks = [];
      let externalAnchorLinkObserver = null;
      let externalAnchorLinkBindFrame = 0;
      const mobileBottomModeQuery = window.matchMedia?.('(max-width: 640px) and (pointer: coarse)');
      const requestFrame = (callback) => {
        const frameId = window.requestAnimationFrame((timestamp) => {
          activeFrameIds.delete(frameId);
          if (!isDisposed) {
            callback(timestamp);
          }
        });
        activeFrameIds.add(frameId);
        return frameId;
      };

      const cancelFrame = (frameId) => {
        if (!frameId) {
          return;
        }
        activeFrameIds.delete(frameId);
        window.cancelAnimationFrame(frameId);
      };

      const setTimer = (callback, delay) => {
        const timerId = window.setTimeout(() => {
          activeTimerIds.delete(timerId);
          if (!isDisposed) {
            callback();
          }
        }, delay);
        activeTimerIds.add(timerId);
        return timerId;
      };

      const clearTimer = (timerId) => {
        if (!timerId) {
          return;
        }
        activeTimerIds.delete(timerId);
        window.clearTimeout(timerId);
      };

      const clearDeferredWork = () => {
        activeFrameIds.forEach((frameId) => window.cancelAnimationFrame(frameId));
        activeFrameIds.clear();
        activeTimerIds.forEach((timerId) => window.clearTimeout(timerId));
        activeTimerIds.clear();
      };

      const safeDecodeHash = (hash) => {
        if (!hash || hash === '#') {
          return null;
        }

        try {
          return decodeURIComponent(hash.slice(1));
        } catch {
          return null;
        }
      };

      const findAnchorLink = (target) => {
        const element = target instanceof Element ? target : target?.parentElement;
        return element?.closest?.('a[href][data-anchor-link]') || null;
      };

      const findRuntimeAnchorLink = (target) => {
        const element = target instanceof Element ? target : target?.parentElement;
        const link = element?.closest?.('a[href]') || null;

        if (!link) {
          return null;
        }

        // Основной контракт для кнопок/пунктов, которые должны использовать
        // runtime-переходы вместо штатного браузерного hash-scroll.
        if (link.hasAttribute('data-anchor-link')) {
          return link;
        }

        return null;
      };

      // Sentinel привязан к sticky/layout-слою, а не к визуальному shell.
      // Так базовая точка sticky/compact считается от места strip в потоке страницы,
      // а shell остаётся только визуальной стеклянной оболочкой.
      const stickySentinel = document.createElement('span');
      stickySentinel.dataset.anchorStripStickySentinel = 'true';
      stickySentinel.setAttribute('aria-hidden', 'true');
      stickySentinel.style.cssText = 'display:block;width:0;height:0;overflow:hidden;pointer-events:none;';
      stickyHost.before(stickySentinel);
      shell.dataset.anchorStripCompact = isCompact ? 'true' : 'false';

      const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
      const formatMobilePx = (value, min = 0) => {
        const safeValue = Number.isFinite(value) ? Math.max(min, value) : min;
        return `${safeValue.toFixed(2)}px`;
      };
      const getMaxOffset = () => Math.max(0, track.scrollWidth - viewport.clientWidth);

      const getRootFontSize = () => {
        const rootFontSize = Number.parseFloat(window.getComputedStyle(document.documentElement).fontSize);
        return Number.isFinite(rootFontSize) ? rootFontSize : 16;
      };

      const getNavbarHeight = () => {
        const navbarHeight = Number.parseFloat(
          window.getComputedStyle(document.documentElement).getPropertyValue('--ifm-navbar-height'),
        );

        return Number.isFinite(navbarHeight) ? navbarHeight : 0;
      };

      const isMobileBottomMode = () => mobileBottomModeQuery?.matches === true;

      const clearMobileAnchorScrollDockFreeze = () => {
        mobileAnchorScrollDockFreezeTarget = null;
        clearTimer(mobileAnchorScrollDockFreezeTimer);
        mobileAnchorScrollDockFreezeTimer = 0;
      };

      const startMobileAnchorScrollDockFreeze = (target) => {
        if (!isMobileBottomMode() || !target) {
          return;
        }

        clearMobileAnchorScrollDockFreeze();
        mobileAnchorScrollDockFreezeTarget = target;
        mobileAnchorScrollDockFreezeTimer = setTimer(() => {
          mobileAnchorScrollDockFreezeTimer = 0;
          mobileAnchorScrollDockFreezeTarget = null;
          requestFrame(() => {
            updateMobileBottomDockState();
          });
        }, mobileAnchorScrollDockFreezeTimeoutMs);
      };

      const isMobileAnchorScrollDockFrozen = () => (
        isMobileBottomMode()
        && mobileAnchorScrollDockFreezeTarget
        && document.contains(mobileAnchorScrollDockFreezeTarget)
      );

      const getVirtualStickyTop = () => (
        getNavbarHeight() + getRootFontSize() * 0.5
      );

      const getStickyTop = () => {
        const stickyTop = Number.parseFloat(window.getComputedStyle(stickyHost).top);

        if (Number.isFinite(stickyTop)) {
          return stickyTop;
        }

        // В мобильном bottom-dock режиме layout больше не sticky к верхней панели.
        // Compact-порог всё равно считаем от виртуальной верхней точки, как если бы
        // меню страницы продолжало идти вверх и коснулось navbar.
        return getVirtualStickyTop();
      };

      const getMobileBottomGap = () => {
        const bottomGap = Number.parseFloat(
          window.getComputedStyle(stickyHost).getPropertyValue('--silam-anchor-strip-mobile-bottom-gap'),
        );

        return Number.isFinite(bottomGap) ? bottomGap : 12;
      };

      const getMobileReturnStartGap = () => {
        const returnStartGap = Number.parseFloat(
          window.getComputedStyle(stickyHost).getPropertyValue('--silam-anchor-strip-mobile-return-start-gap'),
        );

        return Number.isFinite(returnStartGap) ? Math.max(1, returnStartGap) : 120;
      };

      const getMobileCompressStartGap = (fallbackReturnStartGap = getMobileReturnStartGap()) => {
        const compressStartGap = Number.parseFloat(
          window.getComputedStyle(stickyHost).getPropertyValue('--silam-anchor-strip-mobile-compress-start-gap'),
        );

        if (Number.isFinite(compressStartGap)) {
          return Math.max(1, compressStartGap);
        }

        return Math.max(1, fallbackReturnStartGap * 0.5);
      };

      const getMobileCompressedTopGap = () => {
        const compressedTopGap = Number.parseFloat(
          window.getComputedStyle(stickyHost).getPropertyValue('--silam-anchor-strip-mobile-compressed-top-gap'),
        );

        return Number.isFinite(compressedTopGap) ? Math.max(0, compressedTopGap) : 4;
      };

      const getMobileDockLift = () => {
        const dockLift = Number.parseFloat(
          window.getComputedStyle(stickyHost).getPropertyValue('--silam-anchor-strip-mobile-dock-lift'),
        );

        return Number.isFinite(dockLift) ? Math.max(0, dockLift) : 0;
      };

      const getMobilePlaceholderFlowMargin = (fallbackBottomGap = getMobileBottomGap()) => {
        const marginBottom = Number.parseFloat(window.getComputedStyle(layout).marginBottom);

        if (Number.isFinite(marginBottom) && marginBottom > 0) {
          return marginBottom;
        }

        return getRootFontSize() * 2 + fallbackBottomGap;
      };

      const getMobilePlaceholderFlowMarginTop = () => {
        const marginTop = Number.parseFloat(window.getComputedStyle(layout).marginTop);

        if (Number.isFinite(marginTop) && marginTop > 0) {
          return marginTop;
        }

        return getRootFontSize() * 1.5;
      };

      const setMobileNavbarHidden = (nextHidden) => {
        if (nextHidden === isMobileNavbarHidden) {
          return;
        }

        isMobileNavbarHidden = nextHidden;

        if (nextHidden) {
          document.documentElement.dataset.anchorMobileNavbarHidden = 'true';
          return;
        }

        delete document.documentElement.dataset.anchorMobileNavbarHidden;
      };

      const clearMobileNavbarState = () => {
        setMobileNavbarHidden(false);
        lastMobileNavbarScrollY = Math.max(0, window.scrollY || 0);
      };

      const updateMobileNavbarState = (options = {}) => {
        const nextScrollY = Math.max(0, window.scrollY || 0);

        if (!isMobileBottomMode()) {
          releaseMobileAnchorScrollNavbarLock({restoreNormalState: false});
          clearMobileNavbarState();
          return;
        }

        if (isMobileAnchorScrollNavbarLocked) {
          lastMobileNavbarScrollY = nextScrollY;
          setMobileNavbarHidden(true);
          return;
        }

        if (options.force) {
          lastMobileNavbarScrollY = nextScrollY;
          setMobileNavbarHidden(nextScrollY > mobileNavbarTopRevealOffset);
          return;
        }

        if (nextScrollY <= mobileNavbarTopRevealOffset) {
          lastMobileNavbarScrollY = nextScrollY;
          setMobileNavbarHidden(false);
          return;
        }

        const scrollDelta = nextScrollY - lastMobileNavbarScrollY;

        if (Math.abs(scrollDelta) < mobileNavbarScrollDelta) {
          return;
        }

        lastMobileNavbarScrollY = nextScrollY;

        // На touch/mobile верхняя панель освобождает экран при движении вниз
        // и сразу возвращается, когда направление прокрутки меняется вверх.
        setMobileNavbarHidden(scrollDelta > 0);
      };


      const cancelMobileAnchorScrollNavbarWatch = () => {
        if (mobileAnchorScrollNavbarFrame) {
          cancelFrame(mobileAnchorScrollNavbarFrame);
          mobileAnchorScrollNavbarFrame = 0;
        }

        clearTimer(mobileAnchorScrollNavbarFallbackTimer);
        mobileAnchorScrollNavbarFallbackTimer = 0;

        clearTimer(mobileAnchorScrollNavbarReleaseTimer);
        mobileAnchorScrollNavbarReleaseTimer = 0;
      };

      const shouldRestoreMobileNavbarAfterAnchorScroll = () => {
        const targetY = Number.isFinite(mobileAnchorScrollNavbarTargetY)
          ? mobileAnchorScrollNavbarTargetY
          : Math.max(0, window.scrollY || 0);

        return targetY <= mobileNavbarTopRevealOffset;
      };

      const releaseMobileAnchorScrollNavbarLock = (options = {}) => {
        if (!isMobileAnchorScrollNavbarLocked && !mobileAnchorScrollNavbarFrame && !mobileAnchorScrollNavbarFallbackTimer) {
          return;
        }

        cancelMobileAnchorScrollNavbarWatch();
        isMobileAnchorScrollNavbarLocked = false;
        mobileAnchorScrollNavbarTargetY = null;
        lastMobileNavbarScrollY = Math.max(0, window.scrollY || 0);

        if (options.restoreNormalState !== false) {
          updateMobileNavbarState({force: true});
        }
      };

      const scheduleMobileAnchorScrollNavbarWatch = () => {
        if (!isMobileAnchorScrollNavbarLocked || mobileAnchorScrollNavbarFrame) {
          return;
        }

        mobileAnchorScrollNavbarFrame = requestFrame(() => {
          mobileAnchorScrollNavbarFrame = 0;

          if (!isMobileAnchorScrollNavbarLocked) {
            return;
          }

          setMobileNavbarHidden(true);

          if (
            Number.isFinite(mobileAnchorScrollNavbarTargetY)
            && Math.abs(window.scrollY - mobileAnchorScrollNavbarTargetY) <= 2
          ) {
            if (!mobileAnchorScrollNavbarReleaseTimer) {
              mobileAnchorScrollNavbarReleaseTimer = setTimer(() => {
                mobileAnchorScrollNavbarReleaseTimer = 0;
                releaseMobileAnchorScrollNavbarLock({
                  restoreNormalState: shouldRestoreMobileNavbarAfterAnchorScroll(),
                });
              }, mobileAnchorScrollNavbarSettleMs);
            }
            return;
          }

          scheduleMobileAnchorScrollNavbarWatch();
        });
      };

      const startMobileAnchorScrollNavbarLock = (targetScrollY) => {
        if (!isMobileBottomMode()) {
          return;
        }

        cancelMobileAnchorScrollNavbarWatch();
        isMobileAnchorScrollNavbarLocked = true;
        mobileAnchorScrollNavbarTargetY = Number.isFinite(targetScrollY) ? targetScrollY : null;
        lastMobileNavbarScrollY = Math.max(0, window.scrollY || 0);
        setMobileNavbarHidden(true);

        mobileAnchorScrollNavbarFallbackTimer = setTimer(() => {
          releaseMobileAnchorScrollNavbarLock({
            restoreNormalState: shouldRestoreMobileNavbarAfterAnchorScroll(),
          });
        }, mobileAnchorScrollNavbarFallbackMs);
        scheduleMobileAnchorScrollNavbarWatch();
      };

      const clearMobileBottomDockState = () => {
        clearMobileAnchorScrollDockFreeze();
        isMobileBottomDocked = false;
        isMobileBottomReturning = false;
        lastMobileBottomScrollY = Math.max(0, window.scrollY || 0);
        delete layout.dataset.anchorStripMobileBottomDocked;
        delete layout.dataset.anchorStripMobileBottomReturning;
        delete layout.dataset.anchorStripMobileBottomSettling;
        delete layout.dataset.anchorStripMobileBottomSettlePhase;
        delete layout.dataset.anchorStripMobileBottomReleaseLocked;
        clearTimer(mobileBottomSettleTimer);
        mobileBottomSettleTimer = 0;
        if (mobileBottomPlaceholderFrame) {
          cancelFrame(mobileBottomPlaceholderFrame);
          mobileBottomPlaceholderFrame = 0;
          mobileBottomPlaceholderFrameKey = '';
        }
        mobileBottomReturnStartedAt = 0;
        mobileBottomPlaceholderMode = '';
        mobileBottomFlowMargin = 0;
        mobileBottomFlowMarginTop = 0;
        layout.style.removeProperty('--anchor-strip-mobile-return-shift');
        layout.style.removeProperty('--anchor-strip-mobile-release-shift-y');
        layout.style.removeProperty('--anchor-strip-mobile-docked-shift-y');
        layout.style.removeProperty('--anchor-strip-mobile-flow-margin-bottom');
        layout.style.removeProperty('--anchor-strip-mobile-flow-margin-top');
        layout.style.removeProperty('--anchor-strip-mobile-return-progress');
        layout.style.removeProperty('--anchor-strip-mobile-return-height');
        layout.style.removeProperty('--anchor-strip-mobile-return-margin-bottom');
        layout.style.removeProperty('--anchor-strip-mobile-return-margin-top');
        layout.style.removeProperty('--anchor-strip-mobile-placeholder-height');
        layout.style.removeProperty('--anchor-strip-mobile-left');
        layout.style.removeProperty('--anchor-strip-mobile-width');
      };

      const applyMobileBottomDockDatasetState = (
        nextDocked,
        nextReturning,
        placeholderHeight,
        placeholderMargin,
        returnProgress = nextReturning ? 0 : 1,
        placeholderMarginTop = mobileBottomFlowMarginTop,
        compressedTopGap = getMobileCompressedTopGap(),
      ) => {
        const hasDockedDataset = layout.dataset.anchorStripMobileBottomDocked === 'true';
        const hasReturningDataset = layout.dataset.anchorStripMobileBottomReturning === 'true';
        const targetKey = `${nextDocked ? 'docked' : 'flow'}:${nextReturning ? 'returning' : 'steady'}`;
        const nextPlaceholderHeightValue = Math.max(1, placeholderHeight);
        const nextPlaceholderMarginValue = Math.max(0, placeholderMargin);
        const nextReturnProgressValue = clamp(returnProgress, 0, 1);
        const nextPlaceholderHeight = formatMobilePx(nextPlaceholderHeightValue, 1);
        const nextReturnProgress = nextReturnProgressValue.toFixed(3);
        const nextReturnHeight = formatMobilePx(nextPlaceholderHeightValue * nextReturnProgressValue);
        const nextReturnMargin = formatMobilePx(nextPlaceholderMarginValue * nextReturnProgressValue);
        const nextPlaceholderMarginTopValue = Math.max(0, placeholderMarginTop);
        const nextCompressedTopGapValue = clamp(compressedTopGap, 0, nextPlaceholderMarginTopValue);
        const nextReturnMarginTop = formatMobilePx(
          nextCompressedTopGapValue
            + (nextPlaceholderMarginTopValue - nextCompressedTopGapValue) * nextReturnProgressValue,
        );

        layout.style.setProperty('--anchor-strip-mobile-placeholder-height', nextPlaceholderHeight);
        layout.style.setProperty('--anchor-strip-mobile-return-progress', nextReturnProgress);
        layout.style.setProperty('--anchor-strip-mobile-return-height', nextReturnHeight);
        layout.style.setProperty('--anchor-strip-mobile-return-margin-bottom', nextReturnMargin);
        layout.style.setProperty('--anchor-strip-mobile-return-margin-top', nextReturnMarginTop);
        layout.style.setProperty('--anchor-strip-mobile-flow-margin-bottom', formatMobilePx(nextPlaceholderMarginValue));
        layout.style.setProperty('--anchor-strip-mobile-flow-margin-top', formatMobilePx(nextPlaceholderMarginTopValue));

        const applyTargetState = () => {
          if (nextDocked) {
            layout.dataset.anchorStripMobileBottomDocked = 'true';
          } else {
            delete layout.dataset.anchorStripMobileBottomDocked;
          }

          if (nextReturning) {
            layout.dataset.anchorStripMobileBottomReturning = 'true';
          } else {
            delete layout.dataset.anchorStripMobileBottomReturning;
          }
        };

        const scheduleTargetState = () => {
          if (mobileBottomPlaceholderFrame && mobileBottomPlaceholderFrameKey === targetKey) {
            return;
          }

          if (mobileBottomPlaceholderFrame) {
            cancelFrame(mobileBottomPlaceholderFrame);
          }

          mobileBottomPlaceholderFrameKey = targetKey;
          mobileBottomPlaceholderFrame = requestFrame(() => {
            mobileBottomPlaceholderFrame = 0;
            mobileBottomPlaceholderFrameKey = '';
            applyTargetState();
          });
        };

        // Чтобы браузер анимировал placeholder, сначала фиксируем старое
        // числовое состояние и только на следующем кадре переключаем dataset.
        // Иначе изменения height/min-height могут схлопнуться в один layout-pass
        // и выглядеть как резкая ступенька.
        if (nextDocked && !nextReturning && !hasDockedDataset) {
          delete layout.dataset.anchorStripMobileBottomDocked;
          delete layout.dataset.anchorStripMobileBottomReturning;
          void layout.offsetHeight;
          scheduleTargetState();
          return;
        }

        if (nextDocked && nextReturning && hasDockedDataset && !hasReturningDataset) {
          layout.dataset.anchorStripMobileBottomDocked = 'true';
          delete layout.dataset.anchorStripMobileBottomReturning;
          void layout.offsetHeight;
          scheduleTargetState();
          return;
        }

        if (mobileBottomPlaceholderFrame) {
          cancelFrame(mobileBottomPlaceholderFrame);
          mobileBottomPlaceholderFrame = 0;
          mobileBottomPlaceholderFrameKey = '';
        }

        applyTargetState();
      };

      const forceMobileBottomDockForAnchorScroll = (options = {}) => {
        if (!isMobileBottomMode()) {
          return false;
        }

        const shouldSettleInstantly = options.instantPlaceholder === true;
        const previousInlineTransition = layout.style.transition;

        if (shouldSettleInstantly) {
          // Кнопки-якоря могут находиться выше самого anchor strip. В этом случае
          // перед расчётом target-позиции нужно сразу схлопнуть mobile-placeholder,
          // иначе getBoundingClientRect() увидит промежуточную transition-высоту
          // и посадит секцию ниже, чем переход из уже docked меню страницы.
          layout.style.transition = 'none';
          void layout.offsetHeight;
        }

        const bottomGap = getMobileBottomGap();
        const layoutRect = layout.getBoundingClientRect();
        const shellHeight = shell.getBoundingClientRect().height;
        const placeholderHeight = Math.max(1, shellHeight);

        if (!mobileBottomFlowMargin) {
          mobileBottomFlowMargin = getMobilePlaceholderFlowMargin(bottomGap);
        }
        if (!mobileBottomFlowMarginTop) {
          mobileBottomFlowMarginTop = getMobilePlaceholderFlowMarginTop();
        }

        if (mobileBottomPlaceholderFrame) {
          cancelFrame(mobileBottomPlaceholderFrame);
          mobileBottomPlaceholderFrame = 0;
          mobileBottomPlaceholderFrameKey = '';
        }

        isMobileBottomDocked = true;
        isMobileBottomReturning = false;
        mobileBottomReturnStartedAt = 0;
        mobileBottomPlaceholderMode = '';

        layout.style.setProperty('--anchor-strip-mobile-placeholder-height', formatMobilePx(placeholderHeight, 1));
        layout.style.setProperty('--anchor-strip-mobile-return-progress', '0.000');
        layout.style.setProperty('--anchor-strip-mobile-return-height', '0px');
        layout.style.setProperty('--anchor-strip-mobile-return-margin-bottom', '0.00px');
        layout.style.setProperty('--anchor-strip-mobile-return-margin-top', formatMobilePx(getMobileCompressedTopGap()));
        layout.style.setProperty('--anchor-strip-mobile-flow-margin-bottom', formatMobilePx(mobileBottomFlowMargin));
        layout.style.setProperty('--anchor-strip-mobile-flow-margin-top', formatMobilePx(mobileBottomFlowMarginTop));
        layout.style.setProperty('--anchor-strip-mobile-left', `${Math.max(0, Math.round(layoutRect.left))}px`);
        layout.style.setProperty('--anchor-strip-mobile-width', `${Math.max(0, Math.round(layoutRect.width))}px`);

        layout.dataset.anchorStripMobileBottomDocked = 'true';
        delete layout.dataset.anchorStripMobileBottomReturning;

        if (shouldSettleInstantly) {
          void layout.offsetHeight;
          layout.style.transition = previousInlineTransition;
        }

        return true;
      };

      const updateMobileBottomDockState = () => {
        if (!isMobileBottomMode()) {
          clearMobileBottomDockState();
          return;
        }

        const viewportHeight = getViewportHeight();
        const shellHeight = shell.getBoundingClientRect().height;

        if (!viewportHeight || !Number.isFinite(shellHeight) || shellHeight <= 0) {
          clearMobileBottomDockState();
          return;
        }

        const now = window.performance?.now?.() ?? Date.now();
        const scrollY = Math.max(0, window.scrollY || 0);
        const bottomGap = getMobileBottomGap();
        const dockLift = getMobileDockLift();
        const visualBottomGap = bottomGap + dockLift;
        const layoutRect = layout.getBoundingClientRect();
        const dockTop = viewportHeight - shellHeight - visualBottomGap;
        const returnStartGap = getMobileReturnStartGap();
        const compressStartGap = getMobileCompressStartGap(returnStartGap);
        const returnStartTop = dockTop - returnStartGap;
        const compressStartTop = dockTop - compressStartGap;
        const flowTopDelta = layoutRect.top - dockTop;
        const rawReturnProgress = (layoutRect.top - returnStartTop) / returnStartGap;
        const rawCompressProgress = (layoutRect.top - compressStartTop) / compressStartGap;
        const scrollDrivenReturnProgress = clamp(rawReturnProgress, 0, 1);
        const scrollDrivenCompressProgress = clamp(rawCompressProgress, 0, 1);
        const isNearReturnPoint = layoutRect.top >= returnStartTop;
        const scrollDelta = scrollY - lastMobileBottomScrollY;
        const isScrollingUp = scrollDelta < -mobileDockScrollDelta;
        const isScrollingDown = scrollDelta > mobileDockScrollDelta;
        const placeholderHeight = Math.max(1, shellHeight);

        if (!isMobileBottomDocked) {
          mobileBottomFlowMargin = getMobilePlaceholderFlowMargin(bottomGap);
          mobileBottomFlowMarginTop = getMobilePlaceholderFlowMarginTop();
        } else {
          if (!mobileBottomFlowMargin) {
            mobileBottomFlowMargin = getRootFontSize() * 2 + bottomGap;
          }
          if (!mobileBottomFlowMarginTop) {
            mobileBottomFlowMarginTop = getRootFontSize() * 1.5;
          }
        }

        const placeholderMargin = mobileBottomFlowMargin;
        const placeholderMarginTop = mobileBottomFlowMarginTop;
        const compressedTopGap = getMobileCompressedTopGap();
        layout.style.setProperty('--anchor-strip-mobile-flow-margin-bottom', formatMobilePx(placeholderMargin));
        layout.style.setProperty('--anchor-strip-mobile-flow-margin-top', formatMobilePx(placeholderMarginTop));
        let nextDocked = isMobileBottomDocked;
        let nextReturning = isMobileBottomReturning;
        let nextReturnProgress = isMobileBottomReturning ? scrollDrivenReturnProgress : 0;
        let shouldStartSettling = false;
        let shouldFreezePlaceholderOnRelease = false;
        let releaseFlipBeforeRect = null;

        lastMobileBottomScrollY = scrollY;
        layout.style.setProperty('--anchor-strip-mobile-placeholder-height', formatMobilePx(placeholderHeight, 1));
        layout.style.setProperty('--anchor-strip-mobile-left', `${Math.max(0, Math.round(layoutRect.left))}px`);
        layout.style.setProperty('--anchor-strip-mobile-width', `${Math.max(0, Math.round(layoutRect.width))}px`);

        // В mobile/touch режиме placeholder теперь и раскрывается, и сжимается
        // рядом с точкой dock/release через scroll-driven progress 0..1.
        // Так обе стороны перехода используют одну плавную механику, а не
        // резкое переключение height/margin в момент flow ↔ fixed.
        if (isMobileAnchorScrollDockFrozen()) {
          // Во время программного перехода по якорю target-позиция уже посчитана
          // после принудительного bottom-dock. Если сразу после старта smooth-scroll
          // дать scroll-driven compression снова менять height/margin layout,
          // якорь сначала попадает правильно, а затем страница резко «докатывается».
          // Поэтому держим mobile-placeholder полностью схлопнутым до остановки
          // anchor-scroll; обычная ручная прокрутка остаётся на плавной механике.
          nextDocked = true;
          nextReturning = false;
          nextReturnProgress = 0;
          mobileBottomReturnStartedAt = 0;
          mobileBottomPlaceholderMode = 'anchor-scroll';
          layout.style.setProperty('--anchor-strip-mobile-docked-shift-y', '0px');
        } else if (!isMobileBottomDocked) {
          const flowHasReachedDockPoint = Number.isFinite(flowTopDelta) && flowTopDelta <= 0;
          nextDocked = flowHasReachedDockPoint;
          // При первом касании bottom-dock оставляем placeholder полностью раскрытым.
          // Дальше он сжимается тем же scroll-driven progress, как и раскрывается
          // при возврате меню на своё место. Так исчезает резкая фаза flow → fixed.
          nextReturning = nextDocked;
          nextReturnProgress = 1;
          mobileBottomReturnStartedAt = 0;
          mobileBottomPlaceholderMode = nextDocked ? 'compress' : '';
          layout.style.setProperty('--anchor-strip-mobile-docked-shift-y', '0px');
        } else {
          if (isScrollingDown) {
            nextReturnProgress = scrollDrivenCompressProgress;
            nextReturning = nextReturnProgress > 0.01;
            mobileBottomPlaceholderMode = nextReturning ? 'compress' : '';
            mobileBottomReturnStartedAt = 0;
          } else if (
            (isScrollingUp || (isMobileBottomReturning && mobileBottomPlaceholderMode === 'return'))
            && isNearReturnPoint
          ) {
            nextReturning = true;
            nextReturnProgress = scrollDrivenReturnProgress;
            mobileBottomPlaceholderMode = 'return';

            if (!mobileBottomReturnStartedAt) {
              mobileBottomReturnStartedAt = now;
            }
          } else if (!isMobileBottomReturning) {
            nextReturning = false;
            nextReturnProgress = 0;
            mobileBottomPlaceholderMode = '';
            mobileBottomReturnStartedAt = 0;
          }

          // Shell не двигаем отдельно от placeholder: визуальную плавность теперь
          // даёт само место anchorStripLayout, которое сжимается/раскрывается
          // через одинаковый scroll-driven progress.
          layout.style.setProperty('--anchor-strip-mobile-docked-shift-y', '0px');

          const isReturningToFlow = mobileBottomPlaceholderMode === 'return';
          const returnAnimationReady = isReturningToFlow
            && nextReturning
            && nextReturnProgress >= mobileReturnProgressReleaseThreshold;
          const flowHasReachedDockPoint = Number.isFinite(flowTopDelta) && flowTopDelta >= 0;

          if (returnAnimationReady && flowHasReachedDockPoint) {
            // Release делаем только после реального касания flow-точки.
            // Отрицательный pre-align запрещён: он поднимал fixed-shell на 1-4 px,
            // а затем меню визуально возвращалось вниз и выглядело как дёрганье.
            const releasePreAlignY = Math.max(0, flowTopDelta);
            layout.style.setProperty(
              '--anchor-strip-mobile-docked-shift-y',
              `${releasePreAlignY.toFixed(2)}px`,
            );
            // Принудительно применяем fixed-transform перед снятием docked-state.
            shell.getBoundingClientRect();

            nextDocked = false;
            nextReturning = false;
            nextReturnProgress = 1;
            mobileBottomReturnStartedAt = 0;
            mobileBottomPlaceholderMode = '';

            // После pre-align FLIP обычно получает нулевую разницу. Оставляем
            // его только как страховку от sub-pixel/viewport расхождений.
            shouldStartSettling = true;
            shouldFreezePlaceholderOnRelease = true;
            releaseFlipBeforeRect = shell.getBoundingClientRect();
          } else {
            nextDocked = true;
          }
        }

        isMobileBottomDocked = nextDocked;
        isMobileBottomReturning = nextReturning;

        const previousReleaseLayoutTransition = layout.style.transition;
        if (shouldFreezePlaceholderOnRelease) {
          // В момент release фиксируем сам layout-контейнер в финальном размере.
          // Иначе shell уже может быть выровнен, но anchorStripLayout продолжит
          // менять height/margin-bottom и даст микросдвиг на 1-3 px.
          layout.dataset.anchorStripMobileBottomReleaseLocked = 'true';
          layout.style.transition = 'none';
          layout.style.setProperty('--anchor-strip-mobile-return-progress', '1.000');
          layout.style.setProperty('--anchor-strip-mobile-return-height', formatMobilePx(placeholderHeight, 1));
          layout.style.setProperty('--anchor-strip-mobile-return-margin-bottom', formatMobilePx(placeholderMargin));
          layout.style.setProperty('--anchor-strip-mobile-return-margin-top', formatMobilePx(placeholderMarginTop));
          layout.style.setProperty('--anchor-strip-mobile-flow-margin-bottom', formatMobilePx(placeholderMargin));
          layout.style.setProperty('--anchor-strip-mobile-flow-margin-top', formatMobilePx(placeholderMarginTop));
          void layout.offsetHeight;
        }

        applyMobileBottomDockDatasetState(
          nextDocked,
          nextReturning,
          placeholderHeight,
          placeholderMargin,
          nextReturnProgress,
          placeholderMarginTop,
          compressedTopGap,
        );

        if (shouldFreezePlaceholderOnRelease) {
          void layout.offsetHeight;
          requestFrame(() => {
            layout.style.transition = previousReleaseLayoutTransition;
          });
        }

        if (shouldStartSettling && releaseFlipBeforeRect) {
          clearTimer(mobileBottomSettleTimer);

          const releaseFlipAfterRect = shell.getBoundingClientRect();
          const rawReleaseShiftY = releaseFlipBeforeRect.top - releaseFlipAfterRect.top;
          // Микро-FLIP на 1-4 px сам воспринимается как короткий подъём/просадка.
          // После contact-release и layout-lock лучше не анимировать такую разницу:
          // shell уже находится в правильной точке, а cleanup нужен только для state.
          const releaseShiftY = Math.abs(rawReleaseShiftY) > 4 ? rawReleaseShiftY : 0;

          if (Math.abs(releaseShiftY) > 0.5) {
            layout.dataset.anchorStripMobileBottomSettling = 'true';
            layout.dataset.anchorStripMobileBottomSettlePhase = 'instant';
            layout.style.setProperty('--anchor-strip-mobile-release-shift-y', `${releaseShiftY}px`);

            // Принудительно применяем стартовый FLIP-сдвиг без transition,
            // чтобы браузер не успел показать промежуточный скачок fixed → flow.
            shell.getBoundingClientRect();

            requestFrame(() => {
              delete layout.dataset.anchorStripMobileBottomSettlePhase;
              layout.style.setProperty('--anchor-strip-mobile-release-shift-y', '0px');
            });

            mobileBottomSettleTimer = setTimer(() => {
              mobileBottomSettleTimer = 0;
              delete layout.dataset.anchorStripMobileBottomSettling;
              delete layout.dataset.anchorStripMobileBottomSettlePhase;
              delete layout.dataset.anchorStripMobileBottomReleaseLocked;
              layout.style.removeProperty('--anchor-strip-mobile-release-shift-y');
              layout.style.removeProperty('--anchor-strip-mobile-docked-shift-y');
            }, mobileReturnSettleMs + 100);
          } else {
            delete layout.dataset.anchorStripMobileBottomSettling;
            delete layout.dataset.anchorStripMobileBottomSettlePhase;
            layout.style.removeProperty('--anchor-strip-mobile-release-shift-y');

            mobileBottomSettleTimer = setTimer(() => {
              mobileBottomSettleTimer = 0;
              delete layout.dataset.anchorStripMobileBottomReleaseLocked;
              layout.style.removeProperty('--anchor-strip-mobile-docked-shift-y');
            }, mobileReturnSettleMs + 100);
          }
        }
      };

      const measureCompactBaseScrollY = () => {
        // Базу compact считаем от sentinel перед sticky/layout-контейнером.
        // На desktop это реальная sticky-top позиция, а на mobile-bottom это
        // виртуальная верхняя точка: момент, когда меню коснулось бы navbar.
        compactBaseScrollY = window.scrollY + stickySentinel.getBoundingClientRect().top - getStickyTop();
      };

      const applyOffset = () => {
        const maxOffset = getMaxOffset();
        const hasOverflow = maxOffset > 2;
        offset = clamp(offset, 0, maxOffset);

        track.style.setProperty('--anchor-strip-offset', offset + 'px');
        root.dataset.anchorStripOverflow = hasOverflow ? 'true' : 'false';
        prev.disabled = !hasOverflow || offset <= 2;
        next.disabled = !hasOverflow || offset >= maxOffset - 2;
      };

      const setCompactState = (nextCompact, options = {}) => {
        if (nextCompact === isCompact) {
          return false;
        }

        const now = window.performance?.now?.() ?? Date.now();

        if (options.instant) {
          shell.dataset.anchorSettling = 'true';
        }

        isCompact = nextCompact;
        compactLockUntil = now + compactTransitionLockMs;
        shell.dataset.anchorStripCompact = isCompact ? 'true' : 'false';

        if (options.instant) {
          // Принудительно применяем финальную высоту до расчёта позиции якоря.
          void shell.offsetHeight;
          requestFrame(() => {
            delete shell.dataset.anchorSettling;
          });
        }

        requestFrame(() => {
          updateMobileBottomDockState();
          applyOffset();
        });
        setTimer(() => {
          updateMobileBottomDockState();
          applyOffset();
        }, compactTransitionLockMs + 80);
        return true;
      };

      const getExpectedCompactStateForScrollY = (nextScrollY, options = {}) => {
        const enterScrollY = compactBaseScrollY + compactStickyOffset;

        if (isMobileBottomMode() && !options.anchor) {
          // В мобильном bottom-dock режиме добавляем небольшой hysteresis,
          // чтобы около точки касания верхней панели меню не сжималось и
          // не раскрывалось туда-сюда от микродвижений scroll или смены высоты.
          const exitScrollY = compactBaseScrollY - mobileCompactExitGap;
          return isCompact ? nextScrollY > exitScrollY : nextScrollY > enterScrollY;
        }

        // Для desktop и программного перехода по якорю оставляем один
        // предсказуемый порог: ниже sticky-зоны меню compact, выше — expanded.
        return nextScrollY > enterScrollY;
      };

      const getDesktopExpandedAnchorScrollLimit = () => (
        Math.max(0, compactBaseScrollY + compactStickyOffset - 1)
      );

      const isAnchorHashRepresentedInStrip = (hash) => {
        if (!hash) {
          return false;
        }

        const normalizedHash = hash.startsWith('#') ? hash : `#${hash}`;
        return Array.from(root.querySelectorAll('a[href]')).some((link) => {
          const rawHref = link.getAttribute('href');

          if (!rawHref || rawHref === '#') {
            return false;
          }

          try {
            const linkUrl = new URL(rawHref, window.location.href);
            return linkUrl.origin === window.location.origin
              && linkUrl.pathname === window.location.pathname
              && linkUrl.hash === normalizedHash;
          } catch {
            return false;
          }
        });
      };

      const getPlannedDesktopExternalAnchorScrollY = (hash, target, targetScrollY) => {
        if (isMobileBottomMode() || !target || isAnchorHashRepresentedInStrip(hash)) {
          return targetScrollY;
        }

        // Внешние hero/page-кнопки могут вести к заголовкам, которые находятся
        // прямо в зоне раскрытого sticky-strip. Если дать smooth-scroll пройти
        // за compact-порог, меню сначала схлопнется, а затем визуально будет
        // спорить с целевым положением секции. Поэтому для таких якорей заранее
        // ограничиваем конечную scroll-позицию раскрытой стороной compact-границы.
        return Math.min(targetScrollY, getDesktopExpandedAnchorScrollLimit());
      };

      const updateCompactState = (options = {}) => {
        const now = window.performance?.now?.() ?? Date.now();

        if (!options.force && pendingDesktopAnchorCompactFreeze) {
          return;
        }

        if (!options.force && now < compactLockUntil) {
          return;
        }

        setCompactState(getExpectedCompactStateForScrollY(window.scrollY), options);
      };

      const scheduleCompactState = () => {
        if (compactFrame) {
          return;
        }

        compactFrame = requestFrame(() => {
          compactFrame = 0;
          updateMobileNavbarState();
          updateMobileBottomDockState();
          updateCompactState();
        });
      };

      const scheduleResizeWork = () => {
        if (resizeFrame) {
          return;
        }

        resizeFrame = requestFrame(() => {
          resizeFrame = 0;
          measureCompactBaseScrollY();
          updateMobileNavbarState({force: true});
          updateMobileBottomDockState();
          applyOffset();
          updateCompactState({force: true});
        });
      };

      const moveByPage = (direction) => {
        offset += direction * Math.max(180, viewport.clientWidth * 0.82);
        applyOffset();
      };

      let dragPointerId = null;
      let dragStartX = 0;
      let dragStartY = 0;
      let dragStartOffset = 0;
      let dragLastX = 0;
      let dragLastTime = 0;
      let dragVelocity = 0;
      let isStripDragging = false;
      let didStripDrag = false;
      let suppressStripClickUntil = 0;
      let pendingStripClickLink = null;
      let pendingStripClickUntil = 0;
      let dragStartLink = null;
      let momentumFrame = 0;
      let momentumLastTime = 0;
      let momentumVelocity = 0;

      const setStripDragging = (nextDragging) => {
        if (nextDragging) {
          root.dataset.anchorStripDragging = 'true';
          return;
        }

        delete root.dataset.anchorStripDragging;
      };

      const stopMomentumScroll = () => {
        if (momentumFrame) {
          cancelFrame(momentumFrame);
          momentumFrame = 0;
        }

        momentumLastTime = 0;
        momentumVelocity = 0;
      };

      const captureStripPointer = (event) => {
        if (dragPointerId === null || event?.pointerId !== dragPointerId || viewport.hasPointerCapture?.(dragPointerId)) {
          return;
        }

        viewport.setPointerCapture?.(dragPointerId);
      };

      const startMomentumScroll = (initialVelocity) => {
        const maxOffset = getMaxOffset();
        const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;

        stopMomentumScroll();

        if (prefersReducedMotion || maxOffset <= 2 || Math.abs(initialVelocity) < 0.34) {
          return;
        }

        momentumVelocity = clamp(initialVelocity, -2.4, 2.4);
        momentumLastTime = window.performance?.now?.() ?? Date.now();

        const tick = (timestamp) => {
          const now = timestamp || (window.performance?.now?.() ?? Date.now());
          const deltaTime = clamp(now - momentumLastTime, 0, 34);
          momentumLastTime = now;

          const nextMaxOffset = getMaxOffset();

          if (nextMaxOffset <= 2) {
            stopMomentumScroll();
            applyOffset();
            return;
          }

          offset = clamp(offset + momentumVelocity * deltaTime, 0, nextMaxOffset);
          applyOffset();

          const hitLeftEdge = offset <= 0 && momentumVelocity < 0;
          const hitRightEdge = offset >= nextMaxOffset && momentumVelocity > 0;

          if (hitLeftEdge || hitRightEdge) {
            stopMomentumScroll();
            return;
          }

          // Инерция затухает по времени, чтобы короткий слабый свайп почти сразу
          // останавливался, а быстрый флик заметно докатывался после отпускания.
          momentumVelocity *= Math.exp(-deltaTime / 360);

          if (Math.abs(momentumVelocity) < 0.025) {
            stopMomentumScroll();
            return;
          }

          momentumFrame = requestFrame(tick);
        };

        momentumFrame = requestFrame(tick);
      };

      const finishStripDrag = (event, options = {}) => {
        if (dragPointerId === null) {
          return;
        }

        const shouldSuppressClick = didStripDrag && !options.keepClick;
        const clickDistanceX = Math.abs((event?.clientX ?? dragStartX) - dragStartX);
        const clickDistanceY = Math.abs((event?.clientY ?? dragStartY) - dragStartY);
        const shouldRestoreAnchorClick = !shouldSuppressClick
          && dragStartLink
          && clickDistanceX < 8
          && clickDistanceY < 8;

        if (event?.pointerId === dragPointerId && viewport.hasPointerCapture?.(dragPointerId)) {
          viewport.releasePointerCapture(dragPointerId);
        }

        const releaseVelocity = shouldSuppressClick ? dragVelocity : 0;
        const restoreAnchorClickLink = shouldRestoreAnchorClick ? dragStartLink : null;

        dragPointerId = null;
        dragStartLink = null;
        isStripDragging = false;
        didStripDrag = false;
        dragVelocity = 0;
        setStripDragging(false);

        if (shouldSuppressClick) {
          suppressStripClickUntil = (window.performance?.now?.() ?? Date.now()) + 450;
          startMomentumScroll(releaseVelocity);
          return;
        }

        if (restoreAnchorClickLink) {
          const now = window.performance?.now?.() ?? Date.now();
          const shouldActivateImmediately = event?.pointerType === 'touch'
            || event?.pointerType === 'pen'
            || isMobileBottomMode();

          if (shouldActivateImmediately) {
            // На мобильном pointer capture + изменение dock/placeholder иногда
            // мешали браузеру сгенерировать первый click по ссылке меню.
            // Поэтому для настоящего tap по пункту strip запускаем якорь сразу
            // на pointerup, а следующий synthetic click подавляем ниже.
            suppressStripClickUntil = now + 450;
            activatePendingStripClickLink(restoreAnchorClickLink);
            return;
          }

          pendingStripClickLink = restoreAnchorClickLink;
          pendingStripClickUntil = now + 450;
        }
      };

      const handleViewportPointerDown = (event) => {
        if (!event.isPrimary || (typeof event.button === 'number' && event.button !== 0) || getMaxOffset() <= 2) {
          return;
        }

        stopMomentumScroll();
        dragPointerId = event.pointerId;
        dragStartX = event.clientX;
        dragStartY = event.clientY;
        dragStartOffset = offset;
        dragLastX = event.clientX;
        dragLastTime = window.performance?.now?.() ?? Date.now();
        dragVelocity = 0;
        isStripDragging = false;
        didStripDrag = false;
        dragStartLink = findAnchorLink(event.target);

        // Указатель захватываем сразу для всех типов ввода: так мышиный drag
        // не теряется за пределами ссылки, а обычный click по якорю ниже
        // восстанавливается через pendingStripClickLink.
        captureStripPointer(event);
      };

      const handleViewportDragStart = (event) => {
        const eventTarget = event.target instanceof Element ? event.target : event.target?.parentElement;

        if (!eventTarget?.closest?.('a[href]')) {
          return;
        }

        // Браузеры могут запускать нативное перетаскивание ссылки раньше,
        // чем наш pointer-drag набрал порог. Из-за этого drag мышкой
        // работал только в зазорах между карточками.
        event.preventDefault();
      };

      const handleViewportPointerMove = (event) => {
        if (dragPointerId !== event.pointerId) {
          return;
        }

        const deltaX = event.clientX - dragStartX;
        const deltaY = event.clientY - dragStartY;
        const absX = Math.abs(deltaX);
        const absY = Math.abs(deltaY);

        if (!isStripDragging) {
          if (absX < 8 && absY < 8) {
            return;
          }

          if (absY > absX * 1.15) {
            finishStripDrag(event, {keepClick: true});
            return;
          }

          if (absX <= absY || absX < 10) {
            return;
          }

          isStripDragging = true;
          didStripDrag = true;
          setStripDragging(true);
          captureStripPointer(event);
          stopAnchorScrollState({stopNativeScroll: true});
        }

        event.preventDefault();
        const now = window.performance?.now?.() ?? Date.now();
        const sampleDeltaTime = now - dragLastTime;
        const sampleDeltaOffset = dragLastX - event.clientX;

        offset = clamp(dragStartOffset - deltaX, 0, getMaxOffset());

        if (sampleDeltaTime > 0 && sampleDeltaTime < 120) {
          const instantVelocity = sampleDeltaOffset / sampleDeltaTime;
          dragVelocity = dragVelocity === 0
            ? instantVelocity
            : (dragVelocity * 0.35) + (instantVelocity * 0.65);
        }

        dragLastX = event.clientX;
        dragLastTime = now;
        applyOffset();
      };

      const handleViewportPointerUp = (event) => {
        if (dragPointerId === event.pointerId) {
          finishStripDrag(event);
        }
      };

      const handleViewportClickCapture = (event) => {
        const now = window.performance?.now?.() ?? Date.now();

        if (now <= suppressStripClickUntil) {
          event.preventDefault();
          event.stopPropagation();
          pendingStripClickLink = null;
          pendingStripClickUntil = 0;
          return;
        }

        const eventTarget = event.target instanceof Element ? event.target : event.target?.parentElement;
        const clickedLink = eventTarget?.closest?.('a[href]');

        if (clickedLink) {
          pendingStripClickLink = null;
          pendingStripClickUntil = 0;

          // Не полагаемся на document bubbling для пунктов самого strip:
          // Docusaurus/браузерный hash-scroll может сработать иначе, а на
          // mobile после pointer capture первый click иногда терялся.
          // Внутренние пункты меню обрабатываем здесь, после drag-guard.
          const runtimeLink = findRuntimeAnchorLink(clickedLink);
          if (runtimeLink && root.contains(runtimeLink)) {
            handleAnchorLinkActivation(event, runtimeLink);
          }

          return;
        }

        if (pendingStripClickLink && now <= pendingStripClickUntil) {
          const link = pendingStripClickLink;
          pendingStripClickLink = null;
          pendingStripClickUntil = 0;
          event.preventDefault();
          event.stopPropagation();
          activatePendingStripClickLink(link);
          return;
        }

        pendingStripClickLink = null;
        pendingStripClickUntil = 0;
      };

      const normalizeWheelDelta = (delta, event) => {
        if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) {
          return delta * 18;
        }

        if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) {
          return delta * Math.max(180, viewport.clientWidth * 0.82);
        }

        return delta;
      };

      const getVelocityAwareWheelDelta = (delta, event) => {
        const normalizedDelta = normalizeWheelDelta(delta, event);
        const direction = Math.sign(normalizedDelta);
        const absDelta = Math.abs(normalizedDelta);

        if (!direction || absDelta <= 0) {
          return 0;
        }

        const pageSize = Math.max(180, viewport.clientWidth * 0.82);
        const baseDelta = Math.min(absDelta, pageSize * 0.92);
        const velocityBoost = clamp(absDelta / 260, 0, 1.75);

        // Маленькая прокрутка остаётся точной, а сильный флик получает ускорение.
        return direction * Math.min(pageSize * 1.35, baseDelta * (1 + velocityBoost));
      };

      const handleViewportWheel = (event) => {
        const maxOffset = getMaxOffset();

        if (maxOffset <= 2) {
          return;
        }

        const horizontalDelta = event.shiftKey && Math.abs(event.deltaX) < Math.abs(event.deltaY)
          ? event.deltaY
          : event.deltaX;

        if (Math.abs(horizontalDelta) <= Math.abs(event.deltaY) && !event.shiftKey) {
          return;
        }

        const scrollDelta = getVelocityAwareWheelDelta(horizontalDelta, event);

        if (!scrollDelta) {
          return;
        }

        event.preventDefault();
        stopMomentumScroll();
        stopAnchorScrollState({stopNativeScroll: true});
        offset = clamp(offset + scrollDelta, 0, maxOffset);
        applyOffset();
      };

      let pendingAnchorTarget = null;
      let pendingAnchorReleaseTimer = 0;
      let pendingAnchorScrollActive = false;
      let pendingAnchorHighlightDone = false;
      let pendingAnchorHighlightTarget = null;
      let pendingAnchorHighlightObserver = null;
      let pendingAnchorHighlightTimer = 0;
      let pendingAnchorHighlightFrame = 0;
      let pendingAnchorHighlightLastScrollY = null;
      let pendingAnchorHighlightStableFrames = 0;
      let pendingAnchorHighlightStartedAt = 0;
      const anchorHighlightStableFrameThreshold = 5;
      const anchorHighlightScrollStopTimeoutMs = 3200;
      let anchorStripHeightLocked = false;

      const getLayoutFlowHeight = () => {
        const layoutHeight = layout.getBoundingClientRect().height;
        const shellHeight = shell.getBoundingClientRect().height;
        return layoutHeight || shellHeight;
      };

      const lockAnchorStripHeightForAnchorScroll = () => {
        if (anchorStripHeightLocked) {
          return;
        }

        // Layout-lock держим на внешнем контейнере без стеклянной подложки.
        // Сам shell продолжает визуально сжиматься, а место в потоке страницы
        // временно удерживает прозрачный layout-контейнер.
        const lockedHeight = Math.ceil(getLayoutFlowHeight());

        if (!Number.isFinite(lockedHeight) || lockedHeight <= 0) {
          return;
        }

        layout.style.setProperty('--anchor-strip-locked-height', `${lockedHeight}px`);
        layout.dataset.anchorStripHeightLocked = 'true';
        anchorStripHeightLocked = true;
      };

      const unlockAnchorStripHeightForAnchorScroll = (options = {}) => {
        if (!anchorStripHeightLocked) {
          return;
        }

        const preserveTarget = options.preserveTarget;
        const previousTargetTop = preserveTarget && document.contains(preserveTarget)
          ? preserveTarget.getBoundingClientRect().top
          : null;

        anchorStripHeightLocked = false;
        delete layout.dataset.anchorStripHeightLocked;
        layout.style.removeProperty('--anchor-strip-locked-height');

        if (previousTargetTop !== null) {
          void layout.offsetHeight;
          const nextTargetTop = preserveTarget.getBoundingClientRect().top;
          const delta = nextTargetTop - previousTargetTop;

          if (Math.abs(delta) > 0.5) {
            window.scrollTo({
              top: Math.max(0, window.scrollY + delta),
              behavior: 'auto',
            });
          }
        }
      };

      const getTargetOffset = (target) => {
        // Offset якоря берём из scroll-margin-top самого target.
        // Важно: не используем высоту layout/spacer, потому что он может быть
        // временно залочен; визуально контент перекрывает только sticky shell.
        const scrollMarginTop = Number.parseFloat(window.getComputedStyle(target).scrollMarginTop);
        return Number.isFinite(scrollMarginTop) ? scrollMarginTop : 0;
      };

      const getTargetScrollY = (target) => (
        Math.max(0, window.scrollY + target.getBoundingClientRect().top - getTargetOffset(target))
      );

      const getViewportHeight = () => (
        window.innerHeight || document.documentElement?.clientHeight || 0
      );

      const getAnchorHighlightVisibilityNode = (target) => (
        target?.querySelector?.('[data-anchor-highlight-title]')
          || target?.querySelector?.('[data-anchor-highlight-chip]')
          || target
      );

      const isAnchorTargetVisible = (target) => {
        if (!target || !document.contains(target)) {
          return false;
        }

        const visibilityNode = getAnchorHighlightVisibilityNode(target);

        if (!visibilityNode || !document.contains(visibilityNode)) {
          return false;
        }

        const rect = visibilityNode.getBoundingClientRect();
        const viewportHeight = getViewportHeight();

        if (!viewportHeight || rect.width <= 0 || rect.height <= 0) {
          return false;
        }

        const topSafeZone = Math.min(
          viewportHeight,
          Math.max(0, getTargetOffset(target) - 12),
        );
        const bottomSafeZone = Math.max(topSafeZone, viewportHeight - 16);
        const visibleTop = Math.max(rect.top, topSafeZone);
        const visibleBottom = Math.min(rect.bottom, bottomSafeZone);
        const visibleHeight = Math.max(0, visibleBottom - visibleTop);
        const requiredVisibleHeight = Math.min(
          96,
          Math.max(42, rect.height * 0.18),
        );

        return visibleHeight >= requiredVisibleHeight
          || (rect.top >= topSafeZone && rect.top <= bottomSafeZone - 40);
      };

      const clearAnchorHighlightWatch = () => {
        pendingAnchorHighlightObserver?.disconnect?.();
        pendingAnchorHighlightObserver = null;

        if (pendingAnchorHighlightTimer) {
          clearTimer(pendingAnchorHighlightTimer);
          pendingAnchorHighlightTimer = 0;
        }

        if (pendingAnchorHighlightFrame) {
          cancelFrame(pendingAnchorHighlightFrame);
          pendingAnchorHighlightFrame = 0;
        }

        pendingAnchorHighlightTarget = null;
        pendingAnchorHighlightLastScrollY = null;
        pendingAnchorHighlightStableFrames = 0;
        pendingAnchorHighlightStartedAt = 0;
      };

      const clearAnchorReleaseTimer = () => {
        if (pendingAnchorReleaseTimer) {
          clearTimer(pendingAnchorReleaseTimer);
          pendingAnchorReleaseTimer = 0;
        }
      };

      const triggerAnchorHighlight = (target) => {
        if (!target?.matches?.('[data-anchor-highlight-target]')) {
          return;
        }

        target.removeAttribute('data-anchor-highlight');
        void target.offsetWidth;
        target.dataset.anchorHighlight = 'true';

        const clearHighlight = () => {
          target.removeAttribute('data-anchor-highlight');
          target.removeEventListener('animationend', clearHighlight);
        };

        target.addEventListener('animationend', clearHighlight);
        setTimer(clearHighlight, 1400);

        if (mobileAnchorScrollDockFreezeTarget === target) {
          setTimer(() => {
            if (mobileAnchorScrollDockFreezeTarget === target) {
              clearMobileAnchorScrollDockFreeze();
              updateMobileBottomDockState();
            }
          }, 80);
        }
      };

      const tryTriggerAnchorHighlightAfterScrollStop = (target) => {
        if (pendingAnchorHighlightDone || pendingAnchorHighlightTarget !== target) {
          return true;
        }

        if (!target || !document.contains(target)) {
          clearAnchorHighlightWatch();
          return true;
        }

        const now = window.performance?.now?.() || Date.now();
        const scrollY = Math.max(0, window.scrollY || 0);
        const previousScrollY = pendingAnchorHighlightLastScrollY;
        const scrollIsStable = previousScrollY !== null && Math.abs(scrollY - previousScrollY) <= 0.45;

        pendingAnchorHighlightLastScrollY = scrollY;
        pendingAnchorHighlightStableFrames = scrollIsStable
          ? pendingAnchorHighlightStableFrames + 1
          : 0;

        const targetScrollY = getTargetScrollY(target);
        const targetIsReached = Math.abs(scrollY - targetScrollY) <= 3 || isAnchorTargetVisible(target);
        const heightLockReleased = pendingAnchorReleaseTimer === 0;
        const scrollHasStopped = pendingAnchorHighlightStableFrames >= anchorHighlightStableFrameThreshold;
        const isTimedOut = now - pendingAnchorHighlightStartedAt >= anchorHighlightScrollStopTimeoutMs;

        if ((!heightLockReleased || !scrollHasStopped || !targetIsReached) && !isTimedOut) {
          return false;
        }

        if (!isAnchorTargetVisible(target) && !targetIsReached) {
          return false;
        }

        pendingAnchorHighlightDone = true;
        clearAnchorHighlightWatch();
        triggerAnchorHighlight(target);
        return true;
      };

      const scheduleAnchorHighlightScrollStopCheck = (target) => {
        if (!target || pendingAnchorHighlightFrame) {
          return;
        }

        pendingAnchorHighlightFrame = requestFrame(() => {
          pendingAnchorHighlightFrame = 0;

          if (!tryTriggerAnchorHighlightAfterScrollStop(target) && pendingAnchorHighlightTarget === target) {
            scheduleAnchorHighlightScrollStopCheck(target);
          }
        });
      };

      const scheduleAnchorHighlightWhenVisible = (target) => {
        if (!target?.matches?.('[data-anchor-highlight-target]') || pendingAnchorHighlightDone) {
          return;
        }

        clearAnchorHighlightWatch();
        pendingAnchorHighlightTarget = target;
        pendingAnchorHighlightLastScrollY = null;
        pendingAnchorHighlightStableFrames = 0;
        pendingAnchorHighlightStartedAt = window.performance?.now?.() || Date.now();

        scheduleAnchorHighlightScrollStopCheck(target);

        // Страховка: если браузер не даёт стабильной серии кадров smooth-scroll,
        // ещё раз проверяем target после максимального времени ожидания.
        pendingAnchorHighlightTimer = setTimer(() => {
          if (pendingAnchorHighlightTarget === target && !pendingAnchorHighlightDone) {
            pendingAnchorHighlightLastScrollY = Math.max(0, window.scrollY || 0);
            pendingAnchorHighlightStableFrames = anchorHighlightStableFrameThreshold;
            tryTriggerAnchorHighlightAfterScrollStop(target);
          }
        }, anchorHighlightScrollStopTimeoutMs + 120);
      };

      const clearDesktopAnchorCompactFreeze = () => {
        pendingDesktopAnchorCompactFreeze = false;
        pendingDesktopAnchorCompactFreezeTarget = null;
        pendingDesktopAnchorCompactFreezeLastScrollY = null;
        pendingDesktopAnchorCompactFreezeStableFrames = 0;
        pendingDesktopAnchorCompactFreezeStartedAt = 0;

        if (pendingDesktopAnchorCompactFreezeFrame) {
          cancelFrame(pendingDesktopAnchorCompactFreezeFrame);
          pendingDesktopAnchorCompactFreezeFrame = 0;
        }

        if (pendingDesktopAnchorCompactFreezeTimer) {
          clearTimer(pendingDesktopAnchorCompactFreezeTimer);
          pendingDesktopAnchorCompactFreezeTimer = 0;
        }
      };

      const releaseDesktopAnchorCompactFreeze = (target) => {
        if (target && pendingDesktopAnchorCompactFreezeTarget && pendingDesktopAnchorCompactFreezeTarget !== target) {
          return;
        }

        clearDesktopAnchorCompactFreeze();
        compactLockUntil = 0;
        measureCompactBaseScrollY();
        updateCompactState({force: true});
        applyOffset();
      };

      const tryReleaseDesktopAnchorCompactFreezeAfterScrollStop = (target) => {
        if (!pendingDesktopAnchorCompactFreeze || pendingDesktopAnchorCompactFreezeTarget !== target) {
          return true;
        }

        if (!target || !document.contains(target)) {
          releaseDesktopAnchorCompactFreeze(target);
          return true;
        }

        const now = window.performance?.now?.() || Date.now();
        const scrollY = Math.max(0, window.scrollY || 0);
        const previousScrollY = pendingDesktopAnchorCompactFreezeLastScrollY;
        const scrollIsStable = previousScrollY !== null && Math.abs(scrollY - previousScrollY) <= 0.45;

        pendingDesktopAnchorCompactFreezeLastScrollY = scrollY;
        pendingDesktopAnchorCompactFreezeStableFrames = scrollIsStable
          ? pendingDesktopAnchorCompactFreezeStableFrames + 1
          : 0;

        const targetScrollY = getTargetScrollY(target);
        const targetIsReached = Math.abs(scrollY - targetScrollY) <= 3 || isAnchorTargetVisible(target);
        const scrollHasStopped = pendingDesktopAnchorCompactFreezeStableFrames >= anchorHighlightStableFrameThreshold;
        const isTimedOut = now - pendingDesktopAnchorCompactFreezeStartedAt >= anchorHighlightScrollStopTimeoutMs;

        if ((scrollHasStopped && targetIsReached) || isTimedOut) {
          releaseDesktopAnchorCompactFreeze(target);
          return true;
        }

        return false;
      };

      const scheduleDesktopAnchorCompactFreezeCheck = (target) => {
        if (!target || pendingDesktopAnchorCompactFreezeFrame) {
          return;
        }

        pendingDesktopAnchorCompactFreezeFrame = requestFrame(() => {
          pendingDesktopAnchorCompactFreezeFrame = 0;

          if (!tryReleaseDesktopAnchorCompactFreezeAfterScrollStop(target) && pendingDesktopAnchorCompactFreezeTarget === target) {
            scheduleDesktopAnchorCompactFreezeCheck(target);
          }
        });
      };

      const startDesktopAnchorCompactFreezeForExternalLink = (target) => {
        if (isMobileBottomMode() || !target) {
          return;
        }

        clearDesktopAnchorCompactFreeze();
        pendingDesktopAnchorCompactFreeze = true;
        pendingDesktopAnchorCompactFreezeTarget = target;
        pendingDesktopAnchorCompactFreezeLastScrollY = null;
        pendingDesktopAnchorCompactFreezeStableFrames = 0;
        pendingDesktopAnchorCompactFreezeStartedAt = window.performance?.now?.() || Date.now();

        // Внешние hero/page-кнопки могут вести в зону около sticky-порога.
        // На время auto-scroll держим текущее desktop compact-состояние, чтобы
        // strip не схлопывался сразу при клике и не раскрывался обратно у цели.
        compactLockUntil = Math.max(
          compactLockUntil,
          pendingDesktopAnchorCompactFreezeStartedAt + anchorHighlightScrollStopTimeoutMs + 240,
        );

        scheduleDesktopAnchorCompactFreezeCheck(target);
        pendingDesktopAnchorCompactFreezeTimer = setTimer(() => {
          if (pendingDesktopAnchorCompactFreezeTarget === target) {
            releaseDesktopAnchorCompactFreeze(target);
          }
        }, anchorHighlightScrollStopTimeoutMs + 320);
      };

      const scheduleAnchorHighlightVisibilityCheck = () => {
        const target = pendingAnchorHighlightTarget;

        if (!target) {
          return;
        }

        // Секции подсвечиваем только после остановки auto-scroll. Scroll-событие
        // здесь не запускает highlight напрямую, а лишь гарантирует активную
        // проверку остановки, если кадр был потерян браузером.
        scheduleAnchorHighlightScrollStopCheck(target);
      };

      const stopAnchorScrollState = (options = {}) => {
        const hadPendingAnchorScroll = pendingAnchorScrollActive || pendingAnchorTarget || pendingAnchorReleaseTimer;

        pendingAnchorTarget = null;
        pendingAnchorScrollActive = false;
        pendingAnchorHighlightDone = false;
        clearAnchorReleaseTimer();
        clearAnchorHighlightWatch();
        clearDesktopAnchorCompactFreeze();
        clearMobileAnchorScrollDockFreeze();
        releaseMobileAnchorScrollNavbarLock();
        unlockAnchorStripHeightForAnchorScroll();
        clearDesktopAnchorCompactFreeze();

        if (hadPendingAnchorScroll && options.stopNativeScroll) {
          // Прерываем нативный smooth-scroll, если пользователь начал ручную прокрутку.
          window.scrollTo({
            top: window.scrollY,
            behavior: 'auto',
          });
        }
      };

      const cancelAnchorScrollOnUserInput = (event) => {
        if (event.type === 'keydown') {
          const scrollKeys = ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '];

          if (!scrollKeys.includes(event.key)) {
            return;
          }
        }

        stopAnchorScrollState({stopNativeScroll: true});
      };

      const scheduleAnchorHeightUnlock = (target, options = {}) => {
        clearAnchorReleaseTimer();

        if (!options.releaseHeightLock) {
          pendingAnchorTarget = null;
          pendingAnchorScrollActive = false;
          requestFrame(() => {
            measureCompactBaseScrollY();
            updateMobileNavbarState();
            updateMobileBottomDockState();
            applyOffset();
          });
          return;
        }

        pendingAnchorTarget = target;
        pendingAnchorReleaseTimer = setTimer(() => {
          pendingAnchorReleaseTimer = 0;

          if (pendingAnchorTarget !== target) {
            return;
          }

          unlockAnchorStripHeightForAnchorScroll({preserveTarget: target});
          pendingAnchorTarget = null;
          pendingAnchorScrollActive = false;

          requestFrame(() => {
            measureCompactBaseScrollY();
            updateMobileNavbarState();
            updateMobileBottomDockState();
            applyOffset();
          });
        }, compactTransitionLockMs + 80);
      };

      const performAnchorScroll = (target, hash, options = {}) => {
        const targetTop = Number.isFinite(options.targetScrollY)
          ? Math.max(0, options.targetScrollY)
          : getTargetScrollY(target);
        pendingAnchorScrollActive = true;
        startMobileAnchorScrollNavbarLock(targetTop);

        if (options.updateHistory !== false && window.location.hash !== hash) {
          window.history.pushState(null, '', hash);
        }

        window.scrollTo({
          top: targetTop,
          behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ? 'auto' : 'smooth',
        });

        pendingAnchorTarget = target;
        scheduleAnchorHeightUnlock(target, {
          releaseHeightLock: options.releaseHeightLock,
        });

        scheduleAnchorHighlightWhenVisible(target);

        requestFrame(() => {
          measureCompactBaseScrollY();
          updateMobileNavbarState();
          updateMobileBottomDockState();
          applyOffset();
        });
      };

      const scrollToAnchor = (hash, options = {}) => {
        const targetId = safeDecodeHash(hash);

        if (!targetId) {
          return false;
        }

        const target = document.getElementById(targetId);

        if (!target) {
          return false;
        }

        stopAnchorScrollState({stopNativeScroll: pendingAnchorScrollActive});
        measureCompactBaseScrollY();
        updateMobileBottomDockState();

        let preliminaryTargetTop = getTargetScrollY(target);
        const shouldUseDesktopExternalAnchorPlanning = options.externalAnchorLink === true && !isMobileBottomMode();
        const shouldUseDesktopExternalStripAnchorPrecompact = shouldUseDesktopExternalAnchorPlanning
          && isAnchorHashRepresentedInStrip(hash);

        if (shouldUseDesktopExternalStripAnchorPrecompact) {
          // Внешние кнопки, ведущие к пунктам самого anchor-strip, должны
          // считаться сразу в финальной desktop compact-геометрии. Иначе
          // браузер сначала попадает в позицию раскрытого меню, а затем после
          // сжатия strip получает вторую короткую «докатку» к тому же якорю.
          setCompactState(true, {instant: true});
          measureCompactBaseScrollY();
          updateMobileBottomDockState();
          applyOffset();
          preliminaryTargetTop = getTargetScrollY(target);
        }

        const plannedTargetTop = shouldUseDesktopExternalAnchorPlanning
          ? getPlannedDesktopExternalAnchorScrollY(hash, target, preliminaryTargetTop)
          : preliminaryTargetTop;
        const shouldCompactForTarget = isMobileBottomMode()
          ? targetId !== 'overview'
          : shouldUseDesktopExternalStripAnchorPrecompact
            ? true
            : getExpectedCompactStateForScrollY(plannedTargetTop, {anchor: true});
        const shouldForceMobileDockForTarget = isMobileBottomMode() && shouldCompactForTarget;
        const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
        const shouldAnimateCompact = options.smoothCompact === true
          && !prefersReducedMotion
          && shouldCompactForTarget !== isCompact;

        if (!shouldAnimateCompact) {
          setCompactState(shouldCompactForTarget, {instant: true});
          if (shouldForceMobileDockForTarget) {
            forceMobileBottomDockForAnchorScroll({instantPlaceholder: true});
            startMobileAnchorScrollDockFreeze(target);
          }
          performAnchorScroll(target, hash, {
            ...options,
            ...(shouldUseDesktopExternalAnchorPlanning ? {targetScrollY: plannedTargetTop} : {}),
          });
          return true;
        }

        pendingAnchorTarget = target;
        pendingAnchorScrollActive = true;
        pendingAnchorHighlightDone = false;

        const shouldLockFlowHeight = shouldCompactForTarget !== isCompact && !shouldForceMobileDockForTarget;

        if (shouldLockFlowHeight) {
          lockAnchorStripHeightForAnchorScroll();
        }

        // При клике compact/expanded и scroll стартуют сразу вместе.
        // Если состояние меню меняется, временно фиксируем layout-высоту:
        // shell визуально сжимается или раскрывается плавно, а секции ниже
        // не меняют flow-позицию во время smooth-scroll к якорю; стеклянная
        // подложка shell при этом не растягивается layout-lock'ом.
        setCompactState(shouldCompactForTarget);
        if (shouldForceMobileDockForTarget) {
          forceMobileBottomDockForAnchorScroll({instantPlaceholder: true});
          startMobileAnchorScrollDockFreeze(target);
        }
        performAnchorScroll(target, hash, {
          ...options,
          ...(shouldUseDesktopExternalAnchorPlanning ? {targetScrollY: plannedTargetTop} : {}),
          releaseHeightLock: shouldLockFlowHeight,
        });

        return true;
      };

      const activatePendingStripClickLink = (link) => {
        if (!link || !document.contains(link)) {
          return;
        }

        const rawHref = link.getAttribute('href');

        if (!rawHref || rawHref === '#') {
          return;
        }

        let linkUrl;

        try {
          linkUrl = new URL(rawHref, window.location.href);
        } catch {
          return;
        }

        if (linkUrl.origin === window.location.origin && linkUrl.pathname === window.location.pathname && linkUrl.hash) {
          scrollToAnchor(linkUrl.hash, {smoothCompact: true});
          return;
        }

        window.location.assign(linkUrl.href);
      };

      const handleAnchorLinkActivation = (event, link, options = {}) => {
        const rawHref = link.getAttribute('href');

        if (!rawHref || rawHref === '#') {
          return false;
        }

        let linkUrl;

        try {
          linkUrl = new URL(rawHref, window.location.href);
        } catch {
          return false;
        }

        if (linkUrl.origin !== window.location.origin || linkUrl.pathname !== window.location.pathname || !linkUrl.hash) {
          return false;
        }

        const targetId = safeDecodeHash(linkUrl.hash);

        if (!targetId || !document.getElementById(targetId)) {
          return false;
        }

        event.preventDefault();
        scrollToAnchor(linkUrl.hash, {smoothCompact: true, ...options});
        return true;
      };

      const shouldHandleAnchorClickEvent = (event, options = {}) => (
        (options.allowDefaultPrevented === true || !event.defaultPrevented)
        && event.button === 0
        && !event.metaKey
        && !event.ctrlKey
        && !event.shiftKey
        && !event.altKey
      );

      const handleExternalAnchorLinkClickCapture = (event) => {
        if (!shouldHandleAnchorClickEvent(event, {allowDefaultPrevented: true})) {
          return;
        }

        const eventTarget = event.target instanceof Element ? event.target : event.target?.parentElement;
        const link = findRuntimeAnchorLink(eventTarget);

        if (!link || root.contains(link)) {
          return;
        }

        // Внешние кнопки-якоря живут вне scrollable strip, поэтому для них
        // запускаем тот же mobile anchor-scroll в capture-фазе. Ссылки внутри
        // strip остаются на отдельной схеме click/drag, чтобы не ломать swipe.
        if (handleAnchorLinkActivation(event, link, {externalAnchorLink: true})) {
          event.stopImmediatePropagation?.();
          event.stopPropagation();
        }
      };

      const handleDocumentClick = (event) => {
        if (!shouldHandleAnchorClickEvent(event)) {
          return;
        }

        const eventTarget = event.target instanceof Element ? event.target : event.target?.parentElement;
        const link = findRuntimeAnchorLink(eventTarget);

        if (!link) {
          return;
        }

        handleAnchorLinkActivation(event, link, root.contains(link) ? {} : {externalAnchorLink: true});
      };

      const handleDirectExternalAnchorLinkClickCapture = (event) => {
        if (!shouldHandleAnchorClickEvent(event, {allowDefaultPrevented: true})) {
          return;
        }

        const link = event.currentTarget instanceof Element
          ? event.currentTarget
          : findRuntimeAnchorLink(event.target);

        if (!link || root.contains(link)) {
          return;
        }

        if (handleAnchorLinkActivation(event, link, {externalAnchorLink: true})) {
          event.stopImmediatePropagation?.();
          event.stopPropagation();
        }
      };

      const unbindExternalAnchorLinks = () => {
        externalAnchorLinks.forEach((link) => {
          link.removeEventListener('click', handleDirectExternalAnchorLinkClickCapture, true);
        });
        externalAnchorLinks = [];
      };

      const bindExternalAnchorLinks = () => {
        unbindExternalAnchorLinks();
        externalAnchorLinks = Array.from(document.querySelectorAll('a[href][data-anchor-link]'))
          .filter((link) => !root.contains(link));
        externalAnchorLinks.forEach((link) => {
          link.addEventListener('click', handleDirectExternalAnchorLinkClickCapture, true);
        });
      };

      const scheduleExternalAnchorLinkBinding = () => {
        if (externalAnchorLinkBindFrame) {
          return;
        }

        externalAnchorLinkBindFrame = requestFrame(() => {
          externalAnchorLinkBindFrame = 0;
          bindExternalAnchorLinks();
        });
      };

      const handlePrevClick = () => {
        stopMomentumScroll();
        moveByPage(-1);
      };
      const handleNextClick = () => {
        stopMomentumScroll();
        moveByPage(1);
      };
      const handleViewportKeyDown = (event) => {
        if (event.key === 'ArrowLeft') {
          event.preventDefault();
          moveByPage(-1);
        }
        if (event.key === 'ArrowRight') {
          event.preventDefault();
          moveByPage(1);
        }
      };
      const handleHashChange = () => {
        if (window.location.hash && scrollToAnchor(window.location.hash, {updateHistory: false})) {
          return;
        }

        requestFrame(() => {
          measureCompactBaseScrollY();
          updateMobileNavbarState({force: true});
          updateMobileBottomDockState();
          updateCompactState({force: true});
          applyOffset();
        });
      };

      prev.addEventListener('click', handlePrevClick);
      next.addEventListener('click', handleNextClick);
      viewport.addEventListener('keydown', handleViewportKeyDown);
      viewport.addEventListener('pointerdown', handleViewportPointerDown);
      viewport.addEventListener('pointermove', handleViewportPointerMove);
      viewport.addEventListener('pointerup', handleViewportPointerUp);
      viewport.addEventListener('pointercancel', handleViewportPointerUp);
      viewport.addEventListener('lostpointercapture', handleViewportPointerUp);
      viewport.addEventListener('click', handleViewportClickCapture, true);
      viewport.addEventListener('wheel', handleViewportWheel, {passive: false});
      document.addEventListener('click', handleExternalAnchorLinkClickCapture, true);
      document.addEventListener('click', handleDocumentClick);
      bindExternalAnchorLinks();
      if ('MutationObserver' in window && document.body) {
        externalAnchorLinkObserver = new MutationObserver(scheduleExternalAnchorLinkBinding);
        externalAnchorLinkObserver.observe(document.body, {childList: true, subtree: true});
      }
      window.addEventListener('resize', scheduleResizeWork);
      window.addEventListener('scroll', scheduleCompactState, {passive: true});
      window.addEventListener('scroll', scheduleAnchorHighlightVisibilityCheck, {passive: true});
      window.addEventListener('wheel', cancelAnchorScrollOnUserInput, {passive: true});
      window.addEventListener('touchstart', cancelAnchorScrollOnUserInput, {passive: true});
      window.addEventListener('pointerdown', cancelAnchorScrollOnUserInput, {passive: true});
      window.addEventListener('keydown', cancelAnchorScrollOnUserInput);
      viewport.addEventListener('dragstart', handleViewportDragStart);
      window.addEventListener('hashchange', handleHashChange);
      mobileBottomModeQuery?.addEventListener?.('change', scheduleResizeWork);

      const stripLinkDraggableStates = Array.from(viewport.querySelectorAll('a[href][data-anchor-link]')).map((link) => {
        const draggableAttribute = link.getAttribute('draggable');
        link.setAttribute('draggable', 'false');
        return [link, draggableAttribute];
      });

      if ('ResizeObserver' in window) {
        resizeObserver = new ResizeObserver(() => {
          applyOffset();
        });
        resizeObserver.observe(viewport);
        resizeObserver.observe(track);
      }

      measureCompactBaseScrollY();
      updateMobileNavbarState({force: true});
      updateMobileBottomDockState();
      applyOffset();
      updateCompactState({force: true});
      requestFrame(() => {
        measureCompactBaseScrollY();
        updateMobileNavbarState({force: true});
        updateMobileBottomDockState();
        applyOffset();
        updateCompactState({force: true});

        if (window.location.hash) {
          scrollToAnchor(window.location.hash, {updateHistory: false});
        }
      });

      return () => {
        isDisposed = true;
        clearAnchorReleaseTimer();
        clearAnchorHighlightWatch();
        stopMomentumScroll();
        if (compactFrame) {
          cancelFrame(compactFrame);
          compactFrame = 0;
        }
        if (resizeFrame) {
          cancelFrame(resizeFrame);
          resizeFrame = 0;
        }
        clearDeferredWork();
        if (externalAnchorLinkBindFrame) {
          cancelFrame(externalAnchorLinkBindFrame);
          externalAnchorLinkBindFrame = 0;
        }
        externalAnchorLinkObserver?.disconnect?.();
        externalAnchorLinkObserver = null;
        unbindExternalAnchorLinks();
        resizeObserver?.disconnect?.();
        prev.removeEventListener('click', handlePrevClick);
        next.removeEventListener('click', handleNextClick);
        viewport.removeEventListener('keydown', handleViewportKeyDown);
        viewport.removeEventListener('pointerdown', handleViewportPointerDown);
        viewport.removeEventListener('pointermove', handleViewportPointerMove);
        viewport.removeEventListener('pointerup', handleViewportPointerUp);
        viewport.removeEventListener('pointercancel', handleViewportPointerUp);
        viewport.removeEventListener('lostpointercapture', handleViewportPointerUp);
        viewport.removeEventListener('click', handleViewportClickCapture, true);
        viewport.removeEventListener('wheel', handleViewportWheel);
        document.removeEventListener('click', handleExternalAnchorLinkClickCapture, true);
        document.removeEventListener('click', handleDocumentClick);
        window.removeEventListener('resize', scheduleResizeWork);
        window.removeEventListener('scroll', scheduleCompactState);
        window.removeEventListener('scroll', scheduleAnchorHighlightVisibilityCheck);
        window.removeEventListener('wheel', cancelAnchorScrollOnUserInput);
        window.removeEventListener('touchstart', cancelAnchorScrollOnUserInput);
        window.removeEventListener('pointerdown', cancelAnchorScrollOnUserInput);
        window.removeEventListener('keydown', cancelAnchorScrollOnUserInput);
        viewport.removeEventListener('dragstart', handleViewportDragStart);
        window.removeEventListener('hashchange', handleHashChange);
        mobileBottomModeQuery?.removeEventListener?.('change', scheduleResizeWork);
        stripLinkDraggableStates.forEach(([link, draggableAttribute]) => {
          if (!link.isConnected) {
            return;
          }

          if (draggableAttribute === null) {
            link.removeAttribute('draggable');
            return;
          }

          link.setAttribute('draggable', draggableAttribute);
        });
        stickySentinel.remove();
        delete root.dataset.anchorStripReady;
        delete root.dataset.anchorStripOverflow;
        delete root.dataset.anchorStripDragging;
        delete shell.dataset.anchorStripCompact;
        delete shell.dataset.anchorSettling;
        delete layout.dataset.anchorStripHeightLocked;
        layout.style.removeProperty('--anchor-strip-locked-height');
        clearMobileBottomDockState();
        clearMobileNavbarState();
        track.style.removeProperty('--anchor-strip-offset');
      };
    };

    document.querySelectorAll('[data-anchor-strip]').forEach((root) => {
      const cleanup = initAnchorStrip(root);
      if (cleanup) {
        cleanupHandlers.push(cleanup);
      }
    });

    return () => {
      cleanupHandlers.forEach((cleanup) => cleanup());
    };
  }, []);

  return null;
}
