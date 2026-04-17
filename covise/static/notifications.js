(function () {
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let index = 0; index < cookies.length; index += 1) {
                const cookie = cookies[index].trim();
                if (cookie.substring(0, name.length + 1) === (name + "=")) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function escapeHtml(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function renderNotifications(panel, notifications, unreadCount) {
        const badge = document.querySelector(".notification-badge");
        const meta = panel.querySelector(".notif-panel-meta");
        const feed = panel.querySelector(".activity-feed");
        const head = panel.querySelector(".notif-panel-head");
        const showAll = panel.dataset.showAll === "true";
        if (!feed) return;

        feed.style.maxHeight = showAll ? "420px" : "320px";
        feed.style.overflowY = "auto";

        if (badge) {
            badge.textContent = unreadCount;
            badge.style.display = unreadCount > 0 ? "inline-flex" : "none";
        }
        if (meta) {
            meta.textContent = "";
            meta.style.display = "none";
        }
        if (head) {
            let actionsWrap = head.querySelector("[data-notif-actions]");
            if (!actionsWrap) {
                actionsWrap = document.createElement("div");
                actionsWrap.setAttribute("data-notif-actions", "true");
                actionsWrap.style.display = "flex";
                actionsWrap.style.alignItems = "center";
                actionsWrap.style.gap = "0";
                actionsWrap.style.marginLeft = "auto";
                head.appendChild(actionsWrap);
            }
            let showAllButton = actionsWrap.querySelector("[data-show-all]");
            if (!showAllButton) {
                showAllButton = document.createElement("button");
                showAllButton.type = "button";
                showAllButton.setAttribute("data-show-all", "true");
                showAllButton.style.border = "0";
                showAllButton.style.background = "transparent";
                showAllButton.style.color = "inherit";
                showAllButton.style.fontSize = "12px";
                showAllButton.style.fontWeight = "700";
                showAllButton.style.cursor = "pointer";
                showAllButton.style.opacity = "0.82";
                showAllButton.style.padding = "0";
                showAllButton.style.whiteSpace = "nowrap";
                showAllButton.addEventListener("click", async function (event) {
                    event.stopPropagation();
                    panel.dataset.showAll = panel.dataset.showAll === "true" ? "false" : "true";
                    loadNotifications(panel);
                });
                actionsWrap.appendChild(showAllButton);
            }
            let actionButton = head.querySelector("[data-mark-all-read]");
            if (!actionButton) {
                actionButton = document.createElement("button");
                actionButton.type = "button";
                actionButton.setAttribute("data-mark-all-read", "true");
                actionButton.textContent = "Mark all read";
                actionButton.style.border = "0";
                actionButton.style.background = "transparent";
                actionButton.style.color = "inherit";
                actionButton.style.fontSize = "12px";
                actionButton.style.fontWeight = "700";
                actionButton.style.cursor = "pointer";
                actionButton.style.opacity = "0.74";
                actionButton.style.padding = "0";
                actionButton.style.whiteSpace = "nowrap";
                actionButton.addEventListener("click", async function (event) {
                    event.stopPropagation();
                    try {
                        await fetch("/notifications/read-all/", {
                            method: "POST",
                            headers: {
                                "X-CSRFToken": getCookie("csrftoken"),
                            },
                        });
                    } catch (error) {
                        // Keep the current state if the request fails.
                    }
                    loadNotifications(panel);
                });
            }
            showAllButton.textContent = showAll ? "Show less" : "Show all";
            showAllButton.style.display = unreadCount > 4 ? "inline-block" : "none";
            actionButton.style.display = "none";

            let footer = panel.querySelector("[data-notif-footer]");
            if (!footer) {
                footer = document.createElement("div");
                footer.setAttribute("data-notif-footer", "true");
                footer.style.display = "flex";
                footer.style.alignItems = "center";
                footer.style.justifyContent = "space-between";
                footer.style.gap = "12px";
                footer.style.padding = "10px 14px 12px";
                panel.appendChild(footer);
            }
            footer.innerHTML = "";
            const footerMeta = document.createElement("span");
            footerMeta.textContent = unreadCount > 0 ? `${unreadCount} unread` : "Up to date";
            footerMeta.style.fontSize = "12px";
            footerMeta.style.fontWeight = "700";
            footerMeta.style.opacity = "0.72";
            footerMeta.style.whiteSpace = "nowrap";
            footer.appendChild(footerMeta);
            if (notifications.length) {
                footer.appendChild(actionButton);
                actionButton.style.display = "inline-block";
            }
            footer.style.display = notifications.length ? "flex" : "none";
        }

        if (!notifications.length) {
            feed.innerHTML = '<div class="feed-item"><div class="feed-text"><strong>No notifications yet</strong><br>You are all caught up for now.</div><div class="feed-time">Now</div></div>';
            return;
        }

        feed.innerHTML = notifications.map((notification) => (
            `<div class="feed-item" data-notification-id="${notification.id}" data-target-url="${escapeHtml(notification.target_url || "")}" style="cursor:pointer; padding:10px 14px; gap:8px; align-items:flex-start;">` +
                `<div class="feed-text" style="min-width:0; line-height:1.28; font-size:0.8rem;"><strong style="display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-bottom:2px;">${escapeHtml(notification.title)}</strong><span style="display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(notification.body)}</span></div>` +
                `<div class="feed-time" style="font-size:0.68rem; color:rgba(163, 184, 219, 0.62);">${escapeHtml(notification.relative_time)}</div>` +
            `</div>`
        )).join("");

        feed.querySelectorAll("[data-notification-id]").forEach((item) => {
            item.addEventListener("click", () => {
                const notificationId = item.getAttribute("data-notification-id");
                const targetUrl = item.getAttribute("data-target-url") || "/notifications/";
                fetch(`/notifications/${notificationId}/read/`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                }).finally(() => {
                    window.location.href = targetUrl || "/home/";
                });
            });
        });
    }

    async function loadNotifications(panel) {
        try {
            const showAll = panel.dataset.showAll === "true" ? "1" : "0";
            const response = await fetch(`/notifications/?all=${showAll}`, {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            if (!response.ok) return;
            const data = await response.json();
            renderNotifications(panel, data.notifications || [], data.unread_count || 0);
        } catch (error) {
            // Leave the existing panel state unchanged if the request fails.
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const panel = document.getElementById("notifPanel");
        const bell = document.getElementById("notifBell");
        if (!panel || !bell) return;
        panel.dataset.showAll = "false";

        loadNotifications(panel);
        bell.addEventListener("click", () => {
            window.setTimeout(() => loadNotifications(panel), 0);
        });
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) {
                loadNotifications(panel);
            }
        });
        window.addEventListener("focus", () => {
            loadNotifications(panel);
        });
        window.setInterval(() => {
            if (!document.hidden) {
                loadNotifications(panel);
            }
        }, 15000);
    });
})();
