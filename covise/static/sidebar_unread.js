(function () {
    var POLL_INTERVAL = 30000;
    var BADGE_CLASS = 'sidebar-unread-badge';

    function injectBadgeStyles() {
        if (document.getElementById('sidebarUnreadStyles')) return;
        var style = document.createElement('style');
        style.id = 'sidebarUnreadStyles';
        style.textContent = [
            '.sidebar-link { position: relative; }',
            '.app-mobile-nav__link { position: relative; }',
            '.' + BADGE_CLASS + ' {',
            '  position: absolute;',
            '  top: -3px;',
            '  right: 1px;',
            '  min-width: 19px;',
            '  height: 20px;',
            '  border-radius: 999px;',
            '  background: linear-gradient(180deg, #ff5b6e 0%, #e11d48 100%);',
            '  color: #fff;',
            '  font-size: 0.64rem;',
            '  font-weight: 600;',
            '  line-height: 19px;',
            '  text-align: center;',
            '  align-self: center;',
            '  padding: 0 5px;',
            '  pointer-events: none;',
            '  border: 2px solid var(--bg, #05060b);',
            '  box-shadow: 0 6px 14px rgba(225, 29, 72, 0.32);',
            '  letter-spacing: -0.01em;',
            '  box-sizing: border-box;',
            '}',
            '.' + BADGE_CLASS + '[hidden] { display: none !important; }'
        ].join('\n');
        document.head.appendChild(style);
    }

    function getOrCreateBadge(link) {
        var badge = link.querySelector('.' + BADGE_CLASS);
        if (!badge) {
            badge = document.createElement('span');
            badge.className = BADGE_CLASS;
            badge.setAttribute('aria-hidden', 'true');
            badge.hidden = true;
            link.appendChild(badge);
        }
        return badge;
    }

    function updateBadges(count) {
        var links = document.querySelectorAll(
            '.sidebar-link[href*="/messages/"], .app-mobile-nav__link[href*="/messages/"]'
        );
        links.forEach(function (link) {
            var badge = getOrCreateBadge(link);
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : String(count);
                badge.hidden = false;
            } else {
                badge.hidden = true;
            }
        });
    }

    function fetchCount() {
        fetch('/messages/unread-count/', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (data && typeof data.count === 'number') {
                    updateBadges(data.count);
                }
            })
            .catch(function () {});
    }

    injectBadgeStyles();
    fetchCount();
    setInterval(fetchCount, POLL_INTERVAL);
})();
