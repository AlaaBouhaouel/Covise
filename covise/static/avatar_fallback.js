(function () {
    var ROTATION_MS = 2 * 60 * 1000;
    var TRANSITION_MS = 900;
    var PALETTES = [
        {
            start: [54, 92, 176],
            end: [24, 40, 104],
            border: [116, 150, 240],
            shadow: [11, 21, 58],
        },
        {
            start: [92, 74, 168],
            end: [46, 31, 98],
            border: [150, 130, 232],
            shadow: [30, 18, 66],
        },
        {
            start: [146, 64, 112],
            end: [90, 28, 62],
            border: [219, 118, 162],
            shadow: [68, 18, 40],
        },
        {
            start: [164, 92, 44],
            end: [98, 51, 18],
            border: [228, 160, 108],
            shadow: [74, 36, 12],
        },
        {
            start: [74, 88, 122],
            end: [33, 41, 64],
            border: [136, 153, 196],
            shadow: [18, 24, 39],
        },
    ];

    function hashSeed(value) {
        var hash = 2166136261;
        for (var index = 0; index < value.length; index += 1) {
            hash ^= value.charCodeAt(index);
            hash = Math.imul(hash, 16777619);
        }
        return hash >>> 0;
    }

    function paletteFor(seed, bucket) {
        var hash = hashSeed(seed + ':' + bucket);
        return PALETTES[hash % PALETTES.length];
    }

    function mixChannel(from, to, progress) {
        return Math.round(from + ((to - from) * progress));
    }

    function mixColor(from, to, progress) {
        return [
            mixChannel(from[0], to[0], progress),
            mixChannel(from[1], to[1], progress),
            mixChannel(from[2], to[2], progress),
        ];
    }

    function colorString(rgb, alpha) {
        return 'rgba(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + ', ' + alpha + ')';
    }

    function renderPalette(element, palette) {
        element.style.background =
            'linear-gradient(135deg, ' +
            colorString(palette.start, 0.94) +
            ' 0%, ' +
            colorString(palette.end, 0.78) +
            ' 100%)';
        element.style.borderColor = colorString(palette.border, 0.74);
        element.style.boxShadow = '0 10px 24px ' + colorString(palette.shadow, 0.34);
        element.style.color = '#f8fbff';
    }

    function animatePalette(element, fromPalette, toPalette) {
        if (element._avatarAnimationFrame) {
            window.cancelAnimationFrame(element._avatarAnimationFrame);
        }

        var startTime = null;

        function step(timestamp) {
            if (startTime === null) startTime = timestamp;
            var elapsed = timestamp - startTime;
            var rawProgress = Math.min(elapsed / TRANSITION_MS, 1);
            var progress = 1 - Math.pow(1 - rawProgress, 3);

            renderPalette(element, {
                start: mixColor(fromPalette.start, toPalette.start, progress),
                end: mixColor(fromPalette.end, toPalette.end, progress),
                border: mixColor(fromPalette.border, toPalette.border, progress),
                shadow: mixColor(fromPalette.shadow, toPalette.shadow, progress),
            });

            if (rawProgress < 1) {
                element._avatarAnimationFrame = window.requestAnimationFrame(step);
            } else {
                element._avatarAnimationFrame = null;
                element._avatarPalette = toPalette;
            }
        }

        element._avatarAnimationFrame = window.requestAnimationFrame(step);
    }

    function paintAvatar(element, bucket) {
        var seed = (element.getAttribute('data-avatar-seed') || element.textContent || 'CV').trim();
        var nextPalette = paletteFor(seed, bucket);

        if (!element.dataset.avatarTransitionReady) {
            element.style.transition = 'transform 0.18s ease';
            element.dataset.avatarTransitionReady = 'true';
        }

        if (!element._avatarPalette) {
            renderPalette(element, nextPalette);
            element._avatarPalette = nextPalette;
            return;
        }

        animatePalette(element, element._avatarPalette, nextPalette);
    }

    function paintAllAvatars() {
        var bucket = Math.floor(Date.now() / ROTATION_MS);
        document.querySelectorAll('[data-rotating-avatar]').forEach(function (element) {
            paintAvatar(element, bucket);
        });
    }

    function scheduleNextRotation() {
        var delay = ROTATION_MS - (Date.now() % ROTATION_MS);
        window.setTimeout(function () {
            paintAllAvatars();
            window.setInterval(paintAllAvatars, ROTATION_MS);
        }, delay);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            paintAllAvatars();
            scheduleNextRotation();
        }, { once: true });
    } else {
        paintAllAvatars();
        scheduleNextRotation();
    }
})();
