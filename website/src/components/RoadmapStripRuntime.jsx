import {useEffect} from 'react';

export default function RoadmapStripRuntime() {
  useEffect(() => {
    const cleanupHandlers = [];

    const initRoadmapStrip = (root) => {
      const shell = root.closest('[data-roadmap-strip-shell]') || root.parentElement;
      const viewport = root.querySelector('[data-roadmap-strip-scroller]');
      const track = viewport?.firstElementChild;
      const prev = root.querySelector('[data-roadmap-strip-prev]');
      const next = root.querySelector('[data-roadmap-strip-next]');

      if (!shell || !viewport || !track || !prev || !next || root.dataset.roadmapStripReady === 'true') {
        return null;
      }

      root.dataset.roadmapStripReady = 'true';
      let offset = 0;
      let compactFrame = 0;
      let resizeFrame = 0;
      let isCompact = shell.dataset.roadmapStripCompact === 'true';
      let compactBaseScrollY = 0;
      const compactEnterOffset = 250;
      const compactExitOffset = 8;
      const compactTransitionLockMs = 840;
      let compactLockUntil = 0;
      let resizeObserver = null;

      const stickySentinel = document.createElement('span');
      stickySentinel.dataset.roadmapStripStickySentinel = 'true';
      stickySentinel.setAttribute('aria-hidden', 'true');
      stickySentinel.style.cssText = 'display:block;width:0;height:0;overflow:hidden;pointer-events:none;';
      shell.before(stickySentinel);
      shell.dataset.roadmapStripCompact = isCompact ? 'true' : 'false';

      const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
      const getMaxOffset = () => Math.max(0, track.scrollWidth - viewport.clientWidth);

      const getStickyTop = () => {
        const stickyTop = Number.parseFloat(window.getComputedStyle(shell).top);
        return Number.isFinite(stickyTop) ? stickyTop : 0;
      };

      const measureCompactBaseScrollY = () => {
        compactBaseScrollY = window.scrollY + stickySentinel.getBoundingClientRect().top - getStickyTop();
      };

      const applyOffset = () => {
        const maxOffset = getMaxOffset();
        const hasOverflow = maxOffset > 2;
        offset = clamp(offset, 0, maxOffset);

        track.style.setProperty('--roadmap-strip-offset', offset + 'px');
        root.dataset.roadmapStripOverflow = hasOverflow ? 'true' : 'false';
        prev.disabled = !hasOverflow || offset <= 2;
        next.disabled = !hasOverflow || offset >= maxOffset - 2;
      };

      const setCompactState = (nextCompact, options = {}) => {
        if (nextCompact === isCompact) {
          return false;
        }

        const now = window.performance?.now?.() ?? Date.now();

        if (options.instant) {
          shell.dataset.roadmapAnchorSettling = 'true';
        }

        isCompact = nextCompact;
        compactLockUntil = now + compactTransitionLockMs;
        shell.dataset.roadmapStripCompact = isCompact ? 'true' : 'false';

        if (options.instant) {
          // Принудительно применяем финальную высоту до расчёта позиции якоря.
          void shell.offsetHeight;
          window.requestAnimationFrame(() => {
            delete shell.dataset.roadmapAnchorSettling;
          });
        }

        window.requestAnimationFrame(applyOffset);
        window.setTimeout(applyOffset, compactTransitionLockMs + 80);
        return true;
      };

      const getExpectedCompactStateForScrollY = (nextScrollY) => {
        const enterScrollY = compactBaseScrollY + compactEnterOffset;
        const exitScrollY = compactBaseScrollY + compactExitOffset;

        return isCompact
          ? nextScrollY > exitScrollY
          : nextScrollY >= enterScrollY;
      };

      const updateCompactState = (options = {}) => {
        const now = window.performance?.now?.() ?? Date.now();

        if (!options.force && now < compactLockUntil) {
          return;
        }

        setCompactState(getExpectedCompactStateForScrollY(window.scrollY), options);
      };

      const scheduleCompactState = () => {
        if (compactFrame) {
          return;
        }

        compactFrame = window.requestAnimationFrame(() => {
          compactFrame = 0;
          updateCompactState();
        });
      };

      const scheduleResizeWork = () => {
        if (resizeFrame) {
          return;
        }

        resizeFrame = window.requestAnimationFrame(() => {
          resizeFrame = 0;
          measureCompactBaseScrollY();
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
      let isStripDragging = false;
      let didStripDrag = false;
      let suppressStripClickUntil = 0;

      const setStripDragging = (nextDragging) => {
        if (nextDragging) {
          root.dataset.roadmapStripDragging = 'true';
          return;
        }

        delete root.dataset.roadmapStripDragging;
      };

      const finishStripDrag = (event, options = {}) => {
        if (dragPointerId === null) {
          return;
        }

        const shouldSuppressClick = didStripDrag && !options.keepClick;

        if (event?.pointerId === dragPointerId && viewport.hasPointerCapture?.(dragPointerId)) {
          viewport.releasePointerCapture(dragPointerId);
        }

        dragPointerId = null;
        isStripDragging = false;
        didStripDrag = false;
        setStripDragging(false);

        if (shouldSuppressClick) {
          suppressStripClickUntil = (window.performance?.now?.() ?? Date.now()) + 450;
        }
      };

      const handleViewportPointerDown = (event) => {
        if (!event.isPrimary || (typeof event.button === 'number' && event.button !== 0) || getMaxOffset() <= 2) {
          return;
        }

        dragPointerId = event.pointerId;
        dragStartX = event.clientX;
        dragStartY = event.clientY;
        dragStartOffset = offset;
        isStripDragging = false;
        didStripDrag = false;
        viewport.setPointerCapture?.(dragPointerId);
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
          stopAnchorScrollCorrection({stopNativeScroll: true});
        }

        event.preventDefault();
        offset = clamp(dragStartOffset - deltaX, 0, getMaxOffset());
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
        }
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

        event.preventDefault();
        stopAnchorScrollCorrection({stopNativeScroll: true});
        offset = clamp(offset + horizontalDelta, 0, maxOffset);
        applyOffset();
      };

      let pendingAnchorTarget = null;
      let pendingAnchorTimers = [];
      let pendingAnchorScrollActive = false;
      let pendingAnchorHighlightDone = false;

      const getTargetOffset = (target) => {
        const scrollMarginTop = Number.parseFloat(window.getComputedStyle(target).scrollMarginTop);
        return Number.isFinite(scrollMarginTop) ? scrollMarginTop : 0;
      };

      const getTargetScrollY = (target) => (
        Math.max(0, window.scrollY + target.getBoundingClientRect().top - getTargetOffset(target))
      );

      const clearAnchorCorrections = () => {
        pendingAnchorTimers.forEach((timerId) => window.clearTimeout(timerId));
        pendingAnchorTimers = [];
      };

      const triggerAnchorHighlight = (target) => {
        if (!target?.matches?.('[data-roadmap-anchor-highlight-target]')) {
          return;
        }

        target.removeAttribute('data-roadmap-anchor-highlight');
        void target.offsetWidth;
        target.dataset.roadmapAnchorHighlight = 'true';

        const clearHighlight = () => {
          target.removeAttribute('data-roadmap-anchor-highlight');
          target.removeEventListener('animationend', clearHighlight);
        };

        target.addEventListener('animationend', clearHighlight);
        window.setTimeout(clearHighlight, 1400);
      };

      const stopAnchorScrollCorrection = (options = {}) => {
        const hadPendingAnchorScroll = pendingAnchorScrollActive || pendingAnchorTarget || pendingAnchorTimers.length > 0;

        pendingAnchorTarget = null;
        pendingAnchorScrollActive = false;
        pendingAnchorHighlightDone = false;
        clearAnchorCorrections();

        if (hadPendingAnchorScroll && options.stopNativeScroll) {
          // Прерываем нативный smooth scroll, чтобы отложенные корректировки не спорили с ручной прокруткой.
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

        stopAnchorScrollCorrection({stopNativeScroll: true});
      };

      const correctAnchorScroll = (target) => {
        if (!target || !document.contains(target)) {
          return;
        }

        const targetTop = getTargetScrollY(target);

        if (Math.abs(window.scrollY - targetTop) > 1) {
          window.scrollTo({
            top: targetTop,
            behavior: 'auto',
          });
        }

        measureCompactBaseScrollY();
        applyOffset();
      };

      const scheduleAnchorCorrections = (target) => {
        pendingAnchorTarget = target;
        pendingAnchorHighlightDone = false;
        clearAnchorCorrections();

        // Делаем несколько коротких корректировок: после применения compact-состояния,
        // после завершения transition и после возможного завершения native smooth scroll.
        [80, compactTransitionLockMs + 120, compactTransitionLockMs + 520].forEach((delay, index, delays) => {
          const timerId = window.setTimeout(() => {
            if (pendingAnchorTarget !== target) {
              return;
            }

            correctAnchorScroll(target);

            if (!pendingAnchorHighlightDone) {
              pendingAnchorHighlightDone = true;
              triggerAnchorHighlight(target);
            }

            if (index === delays.length - 1) {
              pendingAnchorTarget = null;
              pendingAnchorScrollActive = false;
              clearAnchorCorrections();
            }
          }, delay);

          pendingAnchorTimers.push(timerId);
        });
      };

      const scrollToAnchor = (hash) => {
        const targetId = decodeURIComponent(hash.slice(1));
        const target = document.getElementById(targetId);

        if (!target) {
          return false;
        }

        measureCompactBaseScrollY();

        const preliminaryTargetTop = getTargetScrollY(target);
        const shouldCompactForTarget = getExpectedCompactStateForScrollY(preliminaryTargetTop);
        setCompactState(shouldCompactForTarget, {instant: true});

        const targetTop = getTargetScrollY(target);
        pendingAnchorScrollActive = true;
        window.history.pushState(null, '', hash);
        window.scrollTo({
          top: targetTop,
          behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ? 'auto' : 'smooth',
        });

        scheduleAnchorCorrections(target);

        window.requestAnimationFrame(() => {
          measureCompactBaseScrollY();
          applyOffset();
        });

        return true;
      };

      const handleDocumentClick = (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }

        const eventTarget = event.target instanceof Element ? event.target : event.target?.parentElement;
        const link = eventTarget?.closest?.('a[href]');

        if (!link) {
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

        if (linkUrl.origin !== window.location.origin || linkUrl.pathname !== window.location.pathname || !linkUrl.hash) {
          return;
        }

        const targetId = decodeURIComponent(linkUrl.hash.slice(1));

        if (!targetId || !document.getElementById(targetId)) {
          return;
        }

        event.preventDefault();
        scrollToAnchor(linkUrl.hash);
      };

      const handlePrevClick = () => moveByPage(-1);
      const handleNextClick = () => moveByPage(1);
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
        window.requestAnimationFrame(() => {
          measureCompactBaseScrollY();
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
      document.addEventListener('click', handleDocumentClick);
      window.addEventListener('resize', scheduleResizeWork);
      window.addEventListener('scroll', scheduleCompactState, {passive: true});
      window.addEventListener('wheel', cancelAnchorScrollOnUserInput, {passive: true});
      window.addEventListener('touchstart', cancelAnchorScrollOnUserInput, {passive: true});
      window.addEventListener('pointerdown', cancelAnchorScrollOnUserInput, {passive: true});
      window.addEventListener('keydown', cancelAnchorScrollOnUserInput);
      window.addEventListener('hashchange', handleHashChange);

      if ('ResizeObserver' in window) {
        resizeObserver = new ResizeObserver(() => {
          applyOffset();
        });
        resizeObserver.observe(viewport);
        resizeObserver.observe(track);
      }

      measureCompactBaseScrollY();
      applyOffset();
      updateCompactState({force: true});
      window.requestAnimationFrame(() => {
        measureCompactBaseScrollY();
        applyOffset();
        updateCompactState({force: true});
      });

      return () => {
        clearAnchorCorrections();
        if (compactFrame) {
          window.cancelAnimationFrame(compactFrame);
        }
        if (resizeFrame) {
          window.cancelAnimationFrame(resizeFrame);
        }
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
        document.removeEventListener('click', handleDocumentClick);
        window.removeEventListener('resize', scheduleResizeWork);
        window.removeEventListener('scroll', scheduleCompactState);
        window.removeEventListener('wheel', cancelAnchorScrollOnUserInput);
        window.removeEventListener('touchstart', cancelAnchorScrollOnUserInput);
        window.removeEventListener('pointerdown', cancelAnchorScrollOnUserInput);
        window.removeEventListener('keydown', cancelAnchorScrollOnUserInput);
        window.removeEventListener('hashchange', handleHashChange);
        stickySentinel.remove();
        delete root.dataset.roadmapStripReady;
        delete root.dataset.roadmapStripOverflow;
        delete root.dataset.roadmapStripDragging;
        delete shell.dataset.roadmapStripCompact;
        delete shell.dataset.roadmapAnchorSettling;
        track.style.removeProperty('--roadmap-strip-offset');
      };
    };

    document.querySelectorAll('[data-roadmap-strip]').forEach((root) => {
      const cleanup = initRoadmapStrip(root);
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
