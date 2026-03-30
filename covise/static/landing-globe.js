(function () {
  'use strict';

  if (typeof window === 'undefined' || typeof Globe === 'undefined') {
    return;
  }

  function buildArcData(count, seedOffset) {
    var palette = [
      ['rgba(110, 188, 255, 0.08)', 'rgba(220, 242, 255, 0.8)'],
      ['rgba(88, 155, 255, 0.07)', 'rgba(184, 223, 255, 0.76)'],
      ['rgba(132, 206, 255, 0.06)', 'rgba(245, 251, 255, 0.78)'],
      ['rgba(78, 167, 255, 0.15)', 'rgba(210, 239, 255, 0.95)'],
      ['rgba(72, 130, 255, 0.12)', 'rgba(158, 214, 255, 0.9)'],
      ['rgba(104, 196, 255, 0.1)', 'rgba(244, 251, 255, 0.92)']
    ];

    var gccHubs = [
      { lat: 24.71, lng: 46.67 },
      { lat: 25.20, lng: 55.27 },
      { lat: 25.29, lng: 51.53 },
      { lat: 23.59, lng: 58.41 }
    ];

    var globalHubs = [
      { lat: 51.51, lng: -0.13 },
      { lat: 40.71, lng: -74.00 },
      { lat: 1.35, lng: 103.82 },
      { lat: 35.68, lng: 139.69 },
      { lat: 19.08, lng: 72.88 },
      { lat: 30.04, lng: 31.24 },
      { lat: -33.87, lng: 151.21 },
      { lat: 37.77, lng: -122.42 }
    ];

    var data = [];
    for (var i = 0; i < count; i += 1) {
      var from;
      var to;

      if (i % 7 === 0) {
        from = gccHubs[(i + seedOffset) % gccHubs.length];
        to = gccHubs[(i + 1 + seedOffset) % gccHubs.length];
      } else if (i % 3 === 0) {
        from = globalHubs[(i + seedOffset) % globalHubs.length];
        to = globalHubs[(i * 3 + 5 + seedOffset) % globalHubs.length];
        if (from === to) {
          to = globalHubs[(i * 3 + 6 + seedOffset) % globalHubs.length];
        }
      } else {
        from = gccHubs[(i + seedOffset) % gccHubs.length];
        to = globalHubs[(i * 2 + seedOffset) % globalHubs.length];
      }

      var color = palette[i % palette.length];
      data.push({
        startLat: from.lat,
        startLng: from.lng,
        endLat: to.lat,
        endLng: to.lng,
        color: color,
        altitude: 0.1 + (i % 5) * 0.035,
        dashLength: 0.34 + (i % 4) * 0.05,
        dashGap: 0.58 + (i % 3) * 0.08,
        animateTime: 2600 + (i % 6) * 260
      });
    }
    return data;
  }

  function mountGlobe(el, options) {
    if (!el) return;

    var rect = el.getBoundingClientRect();
    var width = Math.max(1, Math.round(rect.width));
    var height = Math.max(1, Math.round(rect.height));
    var globe = new Globe(el)
      .width(width)
      .height(height)
      .backgroundColor('rgba(0,0,0,0)')
      .showAtmosphere(true)
      .atmosphereColor(options.atmosphereColor || '#9fd2ff')
      .atmosphereAltitude(options.atmosphereAltitude || 0.16)
      .globeImageUrl('//cdn.jsdelivr.net/npm/three-globe/example/img/earth-night.jpg')
      .arcsData(buildArcData(options.arcCount || 24, options.seedOffset || 0))
      .arcColor('color')
      .arcAltitude('altitude')
      .arcStroke(0.42)
      .arcDashLength('dashLength')
      .arcDashGap('dashGap')
      .arcDashAnimateTime('animateTime');

    var controls = globe.controls();
    controls.autoRotate = true;
    controls.autoRotateSpeed = options.rotateSpeed || 0.45;
    controls.enablePan = false;
    controls.enableZoom = false;
    controls.minDistance = options.distance || 240;
    controls.maxDistance = options.distance || 240;

    globe.pointOfView({
      lat: options.lat || 18,
      lng: options.lng || 28,
      altitude: options.altitude || 1.95
    });

    function resize() {
      var nextRect = el.getBoundingClientRect();
      globe.width(Math.max(1, Math.round(nextRect.width)));
      globe.height(Math.max(1, Math.round(nextRect.height)));
    }

    if (typeof ResizeObserver !== 'undefined') {
      var observer = new ResizeObserver(resize);
      observer.observe(el);
    } else {
      window.addEventListener('resize', resize);
    }
  }

  function initLandingGlobes() {
    var hero = document.querySelector('[data-globe-container="hero"]');
    var cta = document.querySelector('[data-globe-container="cta"]');
    var sharedConfig = {
      lat: 20,
      lng: 34,
      altitude: 2.15,
      distance: 240,
      rotateSpeed: 0.4,
      atmosphereAltitude: 0.14,
      atmosphereColor: '#a8d6ff',
      arcCount: 42,
      seedOffset: 0
    };

    mountGlobe(hero, sharedConfig);
    mountGlobe(cta, sharedConfig);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLandingGlobes, { once: true });
  } else {
    initLandingGlobes();
  }
})();
