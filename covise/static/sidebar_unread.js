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
            '.sidebar-link .' + BADGE_CLASS + ' { top: 0; right: 0; transform: translate(22%, -22%); }',
            '.app-mobile-nav__link .' + BADGE_CLASS + ' { top: 0; right: 0; transform: translate(14%, -14%); }',
            '.' + BADGE_CLASS + ' {',
            '  position: absolute;',
            '  min-width: 18px;',
            '  height: 18px;',
            '  padding: 0 5px;',
            '  border-radius: 999px;',
            '  background: var(--notif-badge-bg, #ef2f43);',
            '  color: var(--notif-badge-text, #ffffff);',
            '  font-size: 11px;',
            '  font-weight: 700;',
            '  line-height: 18px;',
            '  text-align: center;',
            '  pointer-events: none;',
            '  border: 1px solid var(--notif-badge-border, rgba(7, 10, 20, 0.85));',
            '  box-sizing: border-box;',
            '  display: inline-flex;',
            '  align-items: center;',
            '  justify-content: center;',
            '  transform-origin: top right;',
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
