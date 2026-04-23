(function () {
    const conversationSummariesScript = document.getElementById("conversation-summaries");
    const activeConversationScript = document.getElementById("active-conversation");
    const friendOptionsScript = document.getElementById("friend-options");
    const activeConversationIdScript = document.getElementById("active-conversation-id");
    const messageErrorScript = document.getElementById("message-error");
    const currentUserIdScript = document.getElementById("current-user-id");

    if (!conversationSummariesScript || !friendOptionsScript || !activeConversationIdScript || !currentUserIdScript) {
        return;
    }

    let conversationSummaries = JSON.parse(conversationSummariesScript.textContent || "[]");
    let activeConversationData = activeConversationScript ? JSON.parse(activeConversationScript.textContent || "null") : null;
    let friendOptions = JSON.parse(friendOptionsScript.textContent || "[]");
    let activeConversationId = JSON.parse(activeConversationIdScript.textContent || "\"\"");
    const initialMessageError = messageErrorScript ? JSON.parse(messageErrorScript.textContent || "\"\"") : "";
    const currentUserId = JSON.parse(currentUserIdScript.textContent || "\"\"");

    const app = document.getElementById("messagesApp");
    const directList = document.getElementById("directList");
    const groupsList = document.getElementById("groupsList");
    const searchInput = document.getElementById("conversationSearch");
    const directTabBtn = document.getElementById("directTabBtn");
    const groupsTabBtn = document.getElementById("groupsTabBtn");
    const createGroupBtn = document.getElementById("createGroupBtn");
    const panelMoreMenuBtn = document.getElementById("panelMoreMenuBtn");
    const panelMoreMenu = document.getElementById("panelMoreMenu");
    const messagesStream = document.getElementById("messagesStream");
    const pinnedText = document.getElementById("pinnedText");
    const chatName = document.getElementById("chatName");
    const chatNameLink = document.getElementById("chatNameLink");
    const chatStatus = document.getElementById("chatStatus");
    const chatAvatar = document.getElementById("chatAvatar");
    const chatInputBar = document.getElementById("chatInputBar");
    const sendBtn = document.getElementById("sendBtn");
    const chatInput = document.getElementById("chatInput");
    const inputAttachBtn = document.getElementById("inputAttachBtn");
    const chatFileInput = document.getElementById("chatFileInput");
    const voiceRecordBtn = document.getElementById("voiceRecordBtn");
    const recordingIndicator = document.getElementById("recordingIndicator");
    const emojiPickerBtn = document.getElementById("emojiPickerBtn");
    const emojiPickerPanel = document.getElementById("emojiPickerPanel");
    const emojiFacesGrid = document.getElementById("emojiFacesGrid");
    const emojiHandsGrid = document.getElementById("emojiHandsGrid");
    const emojiIdeasGrid = document.getElementById("emojiIdeasGrid");
    const composerLockOverlay = document.getElementById("composerLockOverlay");
    const composerLockTitle = document.getElementById("composerLockTitle");
    const composerLockMessage = document.getElementById("composerLockMessage");
    const composerReportBtn = document.getElementById("composerReportBtn");
    const composerBlockToggleBtn = document.getElementById("composerBlockToggleBtn");
    const muteNotificationsToggle = document.getElementById("muteNotificationsToggle");
    const recordingModeToggle = document.getElementById("recordingModeToggle");
    const sharedFilesList = document.getElementById("sharedFilesList");
    const detailsName = document.getElementById("detailsName");
    const detailsAvatar = document.getElementById("detailsAvatar");
    const detailsPersonName = document.getElementById("detailsPersonName");
    const detailsPersonLink = document.getElementById("detailsPersonLink");
    const detailsMatchedOn = document.getElementById("detailsMatchedOn");
    const detailsUserType = document.getElementById("detailsUserType");
    const detailsIndustry = document.getElementById("detailsIndustry");
    const detailsStage = document.getElementById("detailsStage");
    const detailsMutual = document.getElementById("detailsMutual");
    const viewFullProfileBtn = document.getElementById("viewFullProfileBtn");
    const modalBackdrop = document.getElementById("modalBackdrop");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");
    const modalFoot = document.getElementById("modalFoot");

    let activeTab = "direct";
    let chatSocket = null;
    let reconnectTimer = null;
    let socketConversationId = "";
    let socketReconnectAttempts = 0;
    let shouldRecoverStateOnReconnect = false;
    let stateSyncInFlight = false;
    let mediaRecorder = null;
    let mediaRecorderStream = null;
    let mediaChunks = [];
    let renderedConversationId = "";
    let historyLoaderNode = null;
    const messageRowMap = new Map();

    const emojiSets = {
        faces: ["😀", "😂", "😊", "😍", "🤔", "😭", "😎", "🥳", "😴", "😅", "🤯", "🥹", "😇", "🤝"],
        hands: ["👍", "👎", "👏", "🙌", "🙏", "👌", "🤌", "✌️", "🤞", "💪", "👋", "🤙", "🫶", "✍️"],
        ideas: ["🔥", "🚀", "💡", "✅", "📌", "🎯", "💼", "📈", "🌍", "⚡", "🎉", "💬", "🧠", "🤖"],
    };
    const reactionChoices = [
        { key: "thumbs_up", label: "👍" },
        { key: "fire", label: "🔥" },
    ];

    function parseIsoDate(value) {
        const time = Date.parse(value || "");
        return Number.isNaN(time) ? 0 : time;
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let index = 0; index < cookies.length; index += 1) {
                const cookie = cookies[index].trim();
                if (cookie.substring(0, name.length + 1) === `${name}=`) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken = getCookie("csrftoken");

    function escapeHtml(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll("\"", "&quot;")
            .replaceAll("'", "&#39;");
    }

    function normalizeMessagingUrl(value) {
        const raw = String(value || "").trim();
        if (!raw) {
            return "";
        }
        if (/^(?:https?:|data:|blob:)/i.test(raw)) {
            return raw;
        }
        if (raw.startsWith("//users/") || raw.startsWith("//messages/")) {
            return raw.slice(1);
        }
        if (raw.startsWith("users/") || raw.startsWith("messages/")) {
            return `/${raw}`;
        }
        return raw;
    }

    function avatarIdentity(avatarUrl) {
        const value = normalizeMessagingUrl(avatarUrl);
        if (!value) {
            return "";
        }
        try {
            const parsed = new URL(value, window.location.origin);
            return `${parsed.origin}${parsed.pathname}`;
        } catch (_error) {
            return value.split("#")[0].split("?")[0];
        }
    }

    function preserveAvatarUrl(previousUrl, nextUrl) {
        const previousIdentity = avatarIdentity(previousUrl);
        const nextIdentity = avatarIdentity(nextUrl);
        if (previousIdentity && nextIdentity && previousIdentity === nextIdentity) {
            return normalizeMessagingUrl(previousUrl);
        }
        return normalizeMessagingUrl(nextUrl || previousUrl || "");
    }

    function avatarInnerMarkup(initials, avatarUrl, name) {
        const normalizedAvatarUrl = normalizeMessagingUrl(avatarUrl);
        if (normalizedAvatarUrl) {
            return `<img class="avatar-image" src="${escapeHtml(normalizedAvatarUrl)}" alt="${escapeHtml(name || "CoVise member")} avatar" loading="lazy" decoding="async">`;
        }
        return escapeHtml(initials || "CV");
    }

    function setAvatarElement(element, initials, avatarUrl, name) {
        if (!element) {
            return;
        }
        const normalizedAvatarUrl = normalizeMessagingUrl(avatarUrl);
        if (normalizedAvatarUrl) {
            const nextIdentity = avatarIdentity(normalizedAvatarUrl);
            const existingImage = element.querySelector(".avatar-image");
            if (existingImage && element.dataset.avatarIdentity === nextIdentity) {
                if (existingImage.alt !== `${name || "CoVise member"} avatar`) {
                    existingImage.alt = `${name || "CoVise member"} avatar`;
                }
                return;
            }
            element.dataset.avatarIdentity = nextIdentity;
            element.innerHTML = avatarInnerMarkup(initials, normalizedAvatarUrl, name);
            return;
        }
        delete element.dataset.avatarIdentity;
        element.textContent = initials || "CV";
    }

    function receiptHTML(receipt) {
        if (receipt === "sent") {
            return '<span class="receipt">✓</span>';
        }
        if (receipt === "delivered") {
            return '<span class="receipt">✓✓</span>';
        }
        if (receipt === "seen") {
            return '<span class="receipt seen">✓✓</span>';
        }
        return "";
    }

    function formatMessageTime(value) {
        if (!value) {
            return "";
        }
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) {
            return value;
        }
        return parsed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }

    function formatFileSize(value) {
        const size = Number(value || 0);
        if (!size) {
            return "";
        }
        if (size < 1024) {
            return `${size} B`;
        }
        if (size < 1024 * 1024) {
            return `${(size / 1024).toFixed(1)} KB`;
        }
        return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    }

    function scrollMessagesToBottom() {
        if (!messagesStream) {
            return;
        }
        messagesStream.scrollTop = messagesStream.scrollHeight;
    }

    function updateMobileKeyboardInset() {
        if (!app) {
            return;
        }
        if (!window.visualViewport || !window.matchMedia("(max-width: 760px)").matches) {
            app.style.setProperty("--keyboard-offset", "0px");
            app.classList.remove("keyboard-open");
            return;
        }

        const activeElement = document.activeElement;
        const composerFocused = !!(chatInputBar && activeElement && chatInputBar.contains(activeElement));
        if (!composerFocused) {
            app.style.setProperty("--keyboard-offset", "0px");
            app.classList.remove("keyboard-open");
            return;
        }

        const viewport = window.visualViewport;
        const keyboardOffset = Math.max(
            0,
            Math.round(window.innerHeight - viewport.height - viewport.offsetTop)
        );
        const appliedOffset = keyboardOffset > 120 ? Math.min(keyboardOffset, 320) : 0;
        app.style.setProperty("--keyboard-offset", `${appliedOffset}px`);
        app.classList.toggle("keyboard-open", appliedOffset > 0);
    }

    function conversationLockState(conversation) {
        if (!conversation || conversation.conversation_type === "group") {
            return {
                locked: false,
                title: "",
                message: "",
                blockActionLabel: "Block User",
            };
        }
        const blockedByCurrentUser = !!conversation.blocked_by_current_user;
        const blockedByPartner = !!conversation.blocked_by_partner;
        const locked = !!(conversation.messaging_blocked || blockedByCurrentUser || blockedByPartner);
        let title = "Conversation locked";
        let message = conversation.messaging_lock_reason || "Messaging is unavailable in this conversation.";
        if (blockedByCurrentUser && blockedByPartner) {
            title = "Conversation locked";
            message = "Messaging is locked because one of you has blocked the other.";
        } else if (blockedByCurrentUser) {
            title = "You blocked this user";
            message = "Unblock them to send messages again.";
        } else if (blockedByPartner) {
            title = "This user blocked you";
            message = "You can no longer send messages in this conversation.";
        }
        return {
            locked,
            title,
            message,
            blockActionLabel: blockedByCurrentUser ? "Unblock User" : "Block User",
        };
    }

    function applyConversationBlockState(conversation, overrides) {
        if (!conversation) {
            return;
        }
        Object.assign(conversation, overrides || {});
        const lockState = conversationLockState(conversation);
        conversation.messaging_blocked = lockState.locked;
        conversation.messaging_lock_reason = lockState.locked ? lockState.message : "";
        syncSummaryFromActiveConversation();
    }

    function closeEmojiPicker() {
        if (emojiPickerPanel) {
            emojiPickerPanel.hidden = true;
        }
    }

    function insertEmojiAtCursor(emoji) {
        if (!chatInput) {
            return;
        }
        const start = chatInput.selectionStart ?? chatInput.value.length;
        const end = chatInput.selectionEnd ?? chatInput.value.length;
        const currentValue = chatInput.value || "";
        chatInput.value = `${currentValue.slice(0, start)}${emoji}${currentValue.slice(end)}`;
        const nextCaret = start + emoji.length;
        chatInput.focus();
        chatInput.setSelectionRange(nextCaret, nextCaret);
        updateComposerState();
    }

    function renderEmojiPicker() {
        const gridByKey = {
            faces: emojiFacesGrid,
            hands: emojiHandsGrid,
            ideas: emojiIdeasGrid,
        };
        Object.entries(gridByKey).forEach(([key, grid]) => {
            if (!grid) {
                return;
            }
            grid.innerHTML = "";
            emojiSets[key].forEach((emoji) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "emoji-chip";
                button.textContent = emoji;
                button.setAttribute("aria-label", `Insert ${emoji}`);
                button.addEventListener("click", () => {
                    insertEmojiAtCursor(emoji);
                    closeEmojiPicker();
                });
                grid.appendChild(button);
            });
        });
    }

    function sortByRecent(left, right) {
        const rightTime = parseIsoDate(right.last_message_at);
        const leftTime = parseIsoDate(left.last_message_at);
        if (rightTime !== leftTime) {
            return rightTime - leftTime;
        }
        return String(left.name || "").localeCompare(String(right.name || ""));
    }

    function directConversations() {
        return conversationSummaries
            .filter((conversation) => conversation.conversation_type !== "group")
            .slice()
            .sort(sortByRecent);
    }

    function groupConversations() {
        return conversationSummaries
            .filter((conversation) => conversation.conversation_type === "group")
            .slice()
            .sort(sortByRecent);
    }

    function findConversationSummary(conversationId) {
        return conversationSummaries.find((conversation) => conversation.id === conversationId) || null;
    }

    function activeConversationSummary() {
        return findConversationSummary(activeConversationId);
    }

    function activeConversation() {
        if (activeConversationData && activeConversationData.id === activeConversationId) {
            return activeConversationData;
        }
        return null;
    }

    function conversationProfileUrl(conversation) {
        if (!conversation) {
            return "#";
        }
        if (conversation.partner_id) {
            return `/profile/user/${conversation.partner_id}/`;
        }
        return "#";
    }

    function buildChatStatusLine(conversation) {
        if (!conversation) {
            return "Select a direct conversation to start messaging.";
        }
        if (conversation.conversation_type === "group") {
            return conversation.status || `${(conversation.group_members || []).length} members`;
        }
        const parts = [conversation.status, conversation.country].filter(Boolean);
        return parts.join(" - ") || "Private conversation";
    }

    function replaceStateCollections(nextConversationSummaries, nextFriendOptions) {
        const previousConversationsById = new Map(conversationSummaries.map((conversation) => [conversation.id, conversation]));
        const previousFriendsById = new Map(friendOptions.map((friend) => [friend.id, friend]));

        conversationSummaries = (Array.isArray(nextConversationSummaries) ? nextConversationSummaries : []).map((conversation) => {
            const normalizedConversation = {
                ...conversation,
                avatar_url: normalizeMessagingUrl(conversation.avatar_url),
            };
            const previous = previousConversationsById.get(conversation.id);
            return previous
                ? { ...normalizedConversation, avatar_url: preserveAvatarUrl(previous.avatar_url, normalizedConversation.avatar_url) }
                : normalizedConversation;
        });
        friendOptions = (Array.isArray(nextFriendOptions) ? nextFriendOptions : []).map((friend) => {
            const normalizedFriend = {
                ...friend,
                avatar_url: normalizeMessagingUrl(friend.avatar_url),
            };
            const previous = previousFriendsById.get(friend.id);
            return previous
                ? { ...normalizedFriend, avatar_url: preserveAvatarUrl(previous.avatar_url, normalizedFriend.avatar_url) }
                : normalizedFriend;
        });
    }

    function upsertConversationSummary(summary) {
        if (!summary || !summary.id) {
            return;
        }
        const index = conversationSummaries.findIndex((conversation) => conversation.id === summary.id);
        if (index >= 0) {
            const previous = conversationSummaries[index];
            conversationSummaries[index] = {
                ...previous,
                ...summary,
                avatar_url: preserveAvatarUrl(previous.avatar_url, summary.avatar_url),
            };
            return;
        }
        conversationSummaries.push(summary);
    }

    function syncSummaryFromActiveConversation() {
        const conversation = activeConversation();
        if (!conversation) {
            return;
        }
        const summary = { ...conversation };
        delete summary.messages;
        delete summary.shared_files;
        delete summary.has_older_messages;
        delete summary.oldest_loaded_message_id;
        upsertConversationSummary(summary);
    }

    function setActiveConversationData(nextConversation) {
        if (!nextConversation) {
            activeConversationData = null;
            return;
        }
        const previousConversation = activeConversationData && activeConversationData.id === nextConversation.id
            ? activeConversationData
            : null;
        const nextMessages = Array.isArray(nextConversation.messages)
            ? nextConversation.messages.map((message) => ({
                ...message,
                attachment_url: normalizeMessagingUrl(message.attachment_url),
            }))
            : [];
        const nextSharedFiles = Array.isArray(nextConversation.shared_files)
            ? nextConversation.shared_files.map((item) => ({
                ...item,
                url: normalizeMessagingUrl(item.url),
            }))
            : [];
        activeConversationData = {
            ...(previousConversation || {}),
            ...nextConversation,
            avatar_url: preserveAvatarUrl(previousConversation ? previousConversation.avatar_url : "", nextConversation.avatar_url),
            messages: nextMessages,
            shared_files: nextSharedFiles,
        };
        syncSummaryFromActiveConversation();
    }

    function setActiveConversationId(nextConversationId, nextTab) {
        activeConversationId = nextConversationId || "";
        if (nextTab) {
            activeTab = nextTab;
        } else {
            const summary = activeConversationSummary();
            if (summary) {
                activeTab = summary.conversation_type === "group" ? "groups" : "direct";
            }
        }
        const url = new URL(window.location.href);
        if (activeConversationId) {
            url.searchParams.set("conversation", activeConversationId);
        } else {
            url.searchParams.delete("conversation");
        }
        window.history.replaceState({}, "", url.toString());
    }

    function applyMessagesState(statePayload, options) {
        replaceStateCollections(statePayload.conversation_summaries, statePayload.friend_options);
        setActiveConversationId(statePayload.active_conversation_id || "", options && options.tab);
        setActiveConversationData(statePayload.active_conversation || null);
        renderAll(options);
        connectSocket();
        if (activeConversation() && activeConversationSummary() && activeConversationSummary().unread) {
            markActiveConversationSeen();
        }
    }

    function syncMessagesState(options) {
        if (stateSyncInFlight) {
            return Promise.resolve();
        }
        stateSyncInFlight = true;
        const syncUrl = new URL("/messages/state/", window.location.origin);
        if (activeConversationId) {
            syncUrl.searchParams.set("conversation", activeConversationId);
        }
        return fetch(syncUrl.toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (result.ok && result.data && result.data.ok) {
                    applyMessagesState(result.data, options || {});
                }
            })
            .catch(() => {})
            .finally(() => {
                stateSyncInFlight = false;
            });
    }

    function loadConversation(conversationId, nextTab, options) {
        if (!conversationId) {
            setActiveConversationId("", nextTab || "direct");
            setActiveConversationData(null);
            renderAll(options);
            return Promise.resolve();
        }
        const stateUrl = new URL("/messages/state/", window.location.origin);
        stateUrl.searchParams.set("conversation", conversationId);
        return fetch(stateUrl.toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data || !result.data.ok) {
                    showMessagingError((result.data && result.data.error) || "We could not open that conversation right now.");
                    return;
                }
                applyMessagesState(result.data, { ...(options || {}), tab: nextTab });
                app.classList.add("mobile-chat-open");
            })
            .catch(() => {
                showMessagingError("We could not open that conversation right now.");
            });
    }

    function createConversationListItem() {
        const element = document.createElement("button");
        element.type = "button";
        element.className = "conv-item";
        element.innerHTML = `
            <div class="conv-avatar-wrap">
                <div class="avatar"></div>
            </div>
            <div class="conv-main">
                <div class="conv-head"><h3></h3><span></span></div>
                <p></p>
                <div class="conv-foot"></div>
            </div>
        `;
        element.addEventListener("click", () => {
            loadConversation(element.dataset.conversationId || "", element.dataset.tabName || "direct", { stickToBottom: true });
        });
        return element;
    }

    function syncConversationListItem(element, conversation, tabName) {
        if (!element || !conversation) {
            return;
        }
        element.dataset.conversationId = conversation.id;
        element.dataset.tabName = tabName;
        element.className = `conv-item${conversation.id === activeConversationId ? " is-active" : ""}`;

        const avatarElement = element.querySelector(".avatar");
        const nameElement = element.querySelector(".conv-head h3");
        const timeElement = element.querySelector(".conv-head span");
        const previewElement = element.querySelector(".conv-main > p");
        const footElement = element.querySelector(".conv-foot");

        setAvatarElement(avatarElement, conversation.avatar, conversation.avatar_url, conversation.name);
        if (nameElement) {
            nameElement.textContent = conversation.name || "";
        }
        if (timeElement) {
            timeElement.textContent = conversation.time || "New";
        }
        if (previewElement) {
            previewElement.textContent = conversation.preview || "Start the conversation";
        }
        if (footElement) {
            footElement.innerHTML = `
                ${conversation.conversation_type === "group" ? `<span class="match-pill subtle">${escapeHtml(conversation.status || "Group conversation")}</span>` : ""}
                ${conversation.unread ? `<span class="unread-badge">${conversation.unread}</span>` : ""}
            `;
        }
    }

    function ensureActiveConversationSelection() {
        const summary = activeConversationSummary();
        if (summary && activeConversationId) {
            activeTab = summary.conversation_type === "group" ? "groups" : "direct";
            return;
        }
        const firstDirect = directConversations()[0];
        if (firstDirect) {
            setActiveConversationId(firstDirect.id, "direct");
            return;
        }
        const firstGroup = groupConversations()[0];
        if (!activeConversationId && firstGroup) {
            activeTab = "direct";
        }
        setActiveConversationId("", "direct");
    }

    function closeMessageMenus() {
        document.querySelectorAll(".msg-menu.is-open").forEach((menu) => menu.classList.remove("is-open"));
    }

    function renderLists() {
        const query = (searchInput && searchInput.value ? searchInput.value : "").trim().toLowerCase();
        const renderCollection = (container, items, tabName, emptyTitle, emptyText) => {
            if (!container) {
                return;
            }
            const filtered = items.filter((conversation) => {
                const haystack = [
                    conversation.name,
                    conversation.preview,
                    conversation.status,
                    conversation.country,
                    conversation.skills,
                ].join(" ").toLowerCase();
                return haystack.includes(query);
            });

            if (!filtered.length) {
                container.innerHTML = `
                    <div class="request-item request-empty">
                        <div>
                            <h3>${escapeHtml(emptyTitle)}</h3>
                            <p>${escapeHtml(emptyText)}</p>
                        </div>
                    </div>
                `;
                return;
            }

            const existingItems = new Map(
                Array.from(container.querySelectorAll(".conv-item[data-conversation-id]"))
                    .map((element) => [element.dataset.conversationId, element])
            );
            const fragment = document.createDocumentFragment();
            filtered.forEach((conversation) => {
                const conversationId = String(conversation.id || "");
                const element = existingItems.get(conversationId) || createConversationListItem();
                syncConversationListItem(element, conversation, tabName);
                existingItems.delete(conversationId);
                fragment.appendChild(element);
            });
            container.replaceChildren(fragment);
        };

        renderCollection(
            directList,
            directConversations(),
            "direct",
            query ? "No direct messages found" : "No direct messages yet",
            query ? "Try another search term." : "Accepted private chats will appear here."
        );
        renderCollection(
            groupsList,
            groupConversations(),
            "groups",
            query ? "No groups found" : "No groups yet",
            query ? "Try another search term." : "Create a group to start a shared conversation."
        );

        if (directList) {
            directList.classList.toggle("is-hidden", activeTab !== "direct");
        }
        if (groupsList) {
            groupsList.classList.toggle("is-hidden", activeTab !== "groups");
        }
        if (directTabBtn) {
            directTabBtn.classList.toggle("is-active", activeTab === "direct");
        }
        if (groupsTabBtn) {
            groupsTabBtn.classList.toggle("is-active", activeTab === "groups");
        }
    }

    function renderSharedFiles(conversation) {
        if (!sharedFilesList) {
            return;
        }
        sharedFilesList.innerHTML = "";
        const items = (conversation && conversation.shared_files) || [];
        if (!items.length) {
            sharedFilesList.innerHTML = '<p class="muted-note">No shared files yet.</p>';
            return;
        }
        items.forEach((item) => {
            const row = document.createElement("article");
            row.className = "file-item";
            row.innerHTML = `
                <a class="file-item-link" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noopener">
                    <i class="fa-solid ${item.message_type === "image" ? "fa-image" : item.message_type === "voice" ? "fa-wave-square" : "fa-file"}"></i>
                    <div class="file-item-meta">
                        <strong>${escapeHtml(item.name || "Attachment")}</strong>
                        <span>${escapeHtml(item.sender_name || "CoVise member")} - ${escapeHtml(formatFileSize(item.attachment_size) || "Shared file")}</span>
                    </div>
                </a>
                <a class="file-item-open" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noopener">Open</a>
            `;
            sharedFilesList.appendChild(row);
        });
    }

    function clearMessagesRenderState() {
        renderedConversationId = "";
        messageRowMap.clear();
        historyLoaderNode = null;
        if (messagesStream) {
            messagesStream.innerHTML = "";
        }
    }

    function clearEmptyMessageState() {
        if (!messagesStream) {
            return;
        }
        messagesStream.querySelectorAll("[data-empty-state='true']").forEach((node) => node.remove());
    }

    function renderMessageListEmptyState(title, text) {
        if (!messagesStream) {
            return;
        }
        messageRowMap.forEach((row) => row.remove());
        if (historyLoaderNode) {
            historyLoaderNode.remove();
            historyLoaderNode = null;
        }
        clearEmptyMessageState();
        const wrapper = document.createElement("div");
        wrapper.className = "request-item request-empty";
        wrapper.dataset.emptyState = "true";
        wrapper.innerHTML = `
            <div>
                <h3>${escapeHtml(title)}</h3>
                <p>${escapeHtml(text)}</p>
            </div>
        `;
        messagesStream.appendChild(wrapper);
    }

    function renderEmptyConversationState() {
        clearMessagesRenderState();
        renderMessageListEmptyState(
            "No direct conversation selected",
            "Open a direct thread from the left panel to start messaging instantly."
        );
    }

    function syncPinnedBanner(conversation) {
        if (!pinnedText || !pinnedText.parentElement) {
            return;
        }
        const banner = pinnedText.parentElement;
        if (!conversation) {
            pinnedText.textContent = "";
            banner.classList.add("is-hidden");
            banner.classList.remove("is-ephemeral");
            return;
        }
        const isEphemeral = conversation.recording_mode === "ephemeral";
        const bannerText = conversation.pinned || (isEphemeral ? "Messages in this conversation are currently ephemeral and will not be saved." : "");
        pinnedText.textContent = bannerText;
        banner.classList.toggle("is-ephemeral", isEphemeral);
        banner.classList.toggle("is-hidden", !bannerText);
    }

    function renderChatHeaderAndDetails(conversation) {
        if (!conversation) {
            if (chatName) {
                chatName.textContent = "Messages";
            }
            if (chatStatus) {
                chatStatus.textContent = "Select a direct conversation to start messaging.";
            }
            if (chatNameLink) {
                chatNameLink.setAttribute("href", "#");
            }
            setAvatarElement(chatAvatar, "CV", "", "Messages");
            if (detailsName) {
                detailsName.textContent = "No direct conversation selected";
            }
            if (detailsPersonName) {
                detailsPersonName.textContent = "No direct conversation selected";
            }
            if (detailsPersonLink) {
                detailsPersonLink.setAttribute("href", "#");
            }
            if (viewFullProfileBtn) {
                viewFullProfileBtn.setAttribute("href", "#");
            }
            setAvatarElement(detailsAvatar, "CV", "", "Messages");
            if (detailsMatchedOn) {
                detailsMatchedOn.textContent = "No conversation selected";
            }
            if (detailsUserType) {
                detailsUserType.textContent = "No conversation selected";
            }
            if (detailsIndustry) {
                detailsIndustry.textContent = "No conversation selected";
            }
            if (detailsStage) {
                detailsStage.textContent = "No conversation selected";
            }
            if (detailsMutual) {
                detailsMutual.textContent = "0";
            }
            if (muteNotificationsToggle) {
                muteNotificationsToggle.checked = false;
                muteNotificationsToggle.disabled = true;
            }
            if (recordingModeToggle) {
                recordingModeToggle.checked = true;
                recordingModeToggle.disabled = true;
            }
            const blockButton = document.getElementById("blockUserBtn");
            if (blockButton) {
                blockButton.style.display = "block";
                blockButton.disabled = true;
                blockButton.textContent = "Block User";
            }
            const reportButton = document.getElementById("reportUserBtn");
            if (reportButton) {
                reportButton.style.display = "block";
                reportButton.disabled = true;
            }
            const deleteButton = document.getElementById("deleteConversationBtn");
            if (deleteButton) {
                deleteButton.style.display = "block";
                deleteButton.disabled = true;
            }
            renderSharedFiles(null);
            syncPinnedBanner(null);
            return;
        }

        if (chatName) {
            chatName.textContent = conversation.name || "Messages";
        }
        if (chatStatus) {
            chatStatus.textContent = buildChatStatusLine(conversation);
        }
        if (chatNameLink) {
            chatNameLink.setAttribute("href", conversationProfileUrl(conversation));
        }
        setAvatarElement(chatAvatar, conversation.avatar, conversation.avatar_url, conversation.name);

        if (detailsName) {
            detailsName.textContent = conversation.name || "Conversation";
        }
        if (detailsPersonName) {
            detailsPersonName.textContent = conversation.name || "Conversation";
        }
        if (detailsPersonLink) {
            detailsPersonLink.setAttribute("href", conversationProfileUrl(conversation));
        }
        if (viewFullProfileBtn) {
            viewFullProfileBtn.setAttribute("href", conversationProfileUrl(conversation));
            viewFullProfileBtn.style.visibility = conversation.conversation_type === "group" ? "hidden" : "visible";
        }
        setAvatarElement(detailsAvatar, conversation.avatar, conversation.avatar_url, conversation.name);
        if (detailsMatchedOn) {
            detailsMatchedOn.textContent = conversation.matchedOn || "Not available";
        }
        if (detailsUserType) {
            detailsUserType.textContent = conversation.conversation_type === "group" ? "Group conversation" : (conversation.userType || "CoVise member");
        }
        if (detailsIndustry) {
            detailsIndustry.textContent = conversation.conversation_type === "group"
                ? `${(conversation.group_members || []).length} members`
                : (conversation.industry || "Not added yet");
        }
        if (detailsStage) {
            detailsStage.textContent = conversation.conversation_type === "group"
                ? ((conversation.group_members || []).map((member) => member.display_name).join(", ") || "Group participants")
                : (conversation.stage || "Not added yet");
        }
        if (detailsMutual) {
            detailsMutual.textContent = String(conversation.mutual || 0);
        }
        if (muteNotificationsToggle) {
            muteNotificationsToggle.disabled = false;
            muteNotificationsToggle.checked = !!conversation.mute_notifications;
        }
        if (recordingModeToggle) {
            recordingModeToggle.disabled = false;
            recordingModeToggle.checked = conversation.recording_mode !== "ephemeral";
        }
        const blockButton = document.getElementById("blockUserBtn");
        if (blockButton) {
            const isPrivateConversation = conversation.conversation_type !== "group";
            blockButton.style.display = isPrivateConversation ? "block" : "none";
            blockButton.disabled = !isPrivateConversation;
            blockButton.textContent = conversationLockState(conversation).blockActionLabel;
        }
        const reportButton = document.getElementById("reportUserBtn");
        if (reportButton) {
            const isPrivateConversation = conversation.conversation_type !== "group";
            reportButton.style.display = isPrivateConversation ? "block" : "none";
            reportButton.disabled = !isPrivateConversation;
        }
        const deleteButton = document.getElementById("deleteConversationBtn");
        if (deleteButton) {
            const isPrivateConversation = conversation.conversation_type !== "group";
            deleteButton.style.display = isPrivateConversation ? "block" : "none";
            deleteButton.disabled = !isPrivateConversation;
        }
        renderSharedFiles(conversation);
        syncPinnedBanner(conversation);
    }

    function createMessageMenu(message, isMine) {
        if (message.is_ephemeral) {
            return null;
        }
        const wrap = document.createElement("div");
        wrap.className = `msg-menu-wrap${isMine ? " is-own" : " is-other"}`;
        wrap.innerHTML = `
            <button class="msg-menu-trigger" type="button" aria-label="Message actions" data-message-menu-toggle="${escapeHtml(message.id)}">
                <i class="fa-solid fa-ellipsis-vertical"></i>
            </button>
            <div class="msg-menu" data-message-menu="${escapeHtml(message.id)}">
                <button type="button" data-message-action="react" data-message-id="${escapeHtml(message.id)}">
                    <i class="fa-regular fa-face-smile"></i>
                    <span>React</span>
                </button>
                <button type="button" data-message-action="report" data-message-id="${escapeHtml(message.id)}">
                    <i class="fa-regular fa-flag"></i>
                    <span>Report</span>
                </button>
                ${isMine ? `
                <button type="button" data-message-action="delete" data-message-id="${escapeHtml(message.id)}">
                    <i class="fa-regular fa-trash-can"></i>
                    <span>Delete message</span>
                </button>` : ""}
            </div>
        `;
        return wrap;
    }

    function syncMediaBubbleBody(container, message) {
        const messageType = message.message_type || "text";
        const attachmentUrl = normalizeMessagingUrl(message.attachment_url);
        const text = message.text || "";
        const attachmentName = message.attachment_name || "Attachment";

        if (messageType === "image" && attachmentUrl) {
            container.className = `msg-body bubble media-bubble${text ? " has-caption" : ""}`;
            let link = container.querySelector("a[data-role='image-link']");
            let image = container.querySelector("img.bubble-image");
            if (!link) {
                container.innerHTML = "";
                link = document.createElement("a");
                link.dataset.role = "image-link";
                link.target = "_blank";
                link.rel = "noopener";
                image = document.createElement("img");
                image.className = "bubble-image";
                image.loading = "lazy";
                image.decoding = "async";
                link.appendChild(image);
                container.appendChild(link);
            }
            link.href = attachmentUrl;
            if (image.dataset.attachmentIdentity !== attachmentUrl) {
                image.src = attachmentUrl;
                image.dataset.attachmentIdentity = attachmentUrl;
            }
            image.alt = attachmentName;
            let caption = container.querySelector(".bubble-caption");
            if (text) {
                if (!caption) {
                    caption = document.createElement("div");
                    caption.className = "bubble-caption";
                    container.appendChild(caption);
                }
                caption.textContent = text;
            } else if (caption) {
                caption.remove();
            }
            return;
        }

        if (messageType === "voice" && attachmentUrl) {
            container.className = `msg-body bubble media-bubble${text ? " has-caption" : ""}`;
            let audio = container.querySelector("audio.bubble-audio");
            if (!audio) {
                container.innerHTML = "";
                audio = document.createElement("audio");
                audio.className = "bubble-audio";
                audio.controls = true;
                audio.preload = "metadata";
                container.appendChild(audio);
            }
            if (audio.dataset.attachmentIdentity !== attachmentUrl) {
                audio.src = attachmentUrl;
                audio.dataset.attachmentIdentity = attachmentUrl;
            }
            let caption = container.querySelector(".bubble-caption");
            if (text) {
                if (!caption) {
                    caption = document.createElement("div");
                    caption.className = "bubble-caption";
                    container.appendChild(caption);
                }
                caption.textContent = text;
            } else if (caption) {
                caption.remove();
            }
            return;
        }

        if (messageType === "file" && attachmentUrl) {
            container.className = `msg-body bubble media-bubble${text ? " has-caption" : ""}`;
            let link = container.querySelector("a.bubble-file");
            if (!link) {
                container.innerHTML = "";
                link = document.createElement("a");
                link.className = "bubble-file";
                link.target = "_blank";
                link.rel = "noopener";
                link.innerHTML = `
                    <i class="fa-solid fa-file-arrow-down"></i>
                    <div class="bubble-file-meta">
                        <strong></strong>
                        <span></span>
                    </div>
                `;
                container.appendChild(link);
            }
            link.href = attachmentUrl;
            const title = link.querySelector("strong");
            const meta = link.querySelector("span");
            if (title) {
                title.textContent = attachmentName;
            }
            if (meta) {
                meta.textContent = formatFileSize(message.attachment_size) || "Open file";
            }
            let caption = container.querySelector(".bubble-caption");
            if (text) {
                if (!caption) {
                    caption = document.createElement("div");
                    caption.className = "bubble-caption";
                    container.appendChild(caption);
                }
                caption.textContent = text;
            } else if (caption) {
                caption.remove();
            }
            return;
        }

        container.className = "msg-body bubble";
        container.textContent = text;
    }

    function syncReactionChips(row, message) {
        let reactions = row.querySelector(".msg-reactions");
        if (!reactions) {
            reactions = document.createElement("div");
            reactions.className = "msg-reactions";
            row.appendChild(reactions);
        }
        reactions.innerHTML = "";
        const counts = message.reaction_counts || {};
        const viewerReactions = Array.isArray(message.viewer_reactions) ? message.viewer_reactions : [];
        reactionChoices.forEach((choice) => {
            const count = Number(counts[choice.key] || 0);
            if (!count && !viewerReactions.includes(choice.key)) {
                return;
            }
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = `msg-reaction-chip${viewerReactions.includes(choice.key) ? " is-active" : ""}`;
            chip.dataset.reactionToggle = choice.key;
            chip.dataset.messageId = message.id;
            chip.innerHTML = `<span>${choice.label}</span><span>${count}</span>`;
            reactions.appendChild(chip);
        });
        reactions.hidden = !reactions.childElementCount;
    }

    function createMessageRow(message, conversation) {
        const row = document.createElement("article");
        row.dataset.messageId = message.id;
        row.setAttribute("role", "article");
        row.innerHTML = `
            <div class="msg-sender"></div>
            <div class="msg-shell">
                <div class="msg-content">
                    <div class="msg-body bubble"></div>
                </div>
            </div>
            <div class="msg-meta"><span class="msg-time"></span><span class="msg-receipt"></span></div>
        `;
        syncMessageRow(row, message, conversation);
        return row;
    }

    function syncMessageRow(row, message, conversation) {
        const isMine = message.sender_id === currentUserId;
        row.className = `msg ${isMine ? "outgoing" : "incoming"}`;
        row.dataset.messageId = message.id;
        row.setAttribute(
            "aria-label",
            `${isMine ? "You" : (message.sender_name || "CoVise member")}, ${formatMessageTime(message.created_at) || "just now"}`
        );

        const sender = row.querySelector(".msg-sender");
        const showSender = conversation && conversation.conversation_type === "group" && !isMine;
        if (sender) {
            sender.textContent = showSender ? (message.sender_name || "CoVise member") : "";
            sender.hidden = !showSender;
        }

        const shell = row.querySelector(".msg-shell");
        if (shell) {
            shell.className = `msg-shell ${isMine ? "is-own" : "is-other"}`;
            let menuWrap = shell.querySelector(".msg-menu-wrap");
            if (message.is_ephemeral) {
                if (menuWrap) {
                    menuWrap.remove();
                }
            } else if (!menuWrap) {
                menuWrap = createMessageMenu(message, isMine);
                if (isMine) {
                    shell.insertBefore(menuWrap, shell.firstChild);
                } else {
                    shell.appendChild(menuWrap);
                }
            } else {
                menuWrap.className = `msg-menu-wrap${isMine ? " is-own" : " is-other"}`;
                const deleteButton = menuWrap.querySelector("[data-message-action='delete']");
                if (deleteButton) {
                    deleteButton.style.display = isMine ? "flex" : "none";
                }
            }
        }

        let contentWrap = row.querySelector(".msg-content");
        if (!contentWrap) {
            contentWrap = document.createElement("div");
            contentWrap.className = "msg-content";
            row.querySelector(".msg-shell").appendChild(contentWrap);
        }
        let contentBody = contentWrap.querySelector(".msg-body");
        if (!contentBody) {
            contentBody = document.createElement("div");
            contentBody.className = "msg-body bubble";
            contentWrap.replaceChildren(contentBody);
        }
        syncMediaBubbleBody(contentBody, message);
        syncReactionChips(row, message);

        const timeElement = row.querySelector(".msg-time");
        if (timeElement) {
            timeElement.textContent = formatMessageTime(message.created_at);
        }
        const receiptElement = row.querySelector(".msg-receipt");
        if (receiptElement) {
            receiptElement.innerHTML = isMine ? receiptHTML(message.receipt || "sent") : "";
        }
    }

    function renderHistoryLoader(conversation, nodes) {
        if (!conversation || !conversation.has_older_messages || !conversation.oldest_loaded_message_id) {
            return;
        }
        if (!historyLoaderNode) {
            historyLoaderNode = document.createElement("div");
            historyLoaderNode.className = "date-separator";
            historyLoaderNode.innerHTML = `<button class="panel-btn ghost" type="button" data-load-older="1">Load older messages</button>`;
        }
        nodes.push(historyLoaderNode);
    }

    function pruneDetachedMessageRows(allMessages) {
        const validIds = new Set((Array.isArray(allMessages) ? allMessages : []).map((message) => String(message.id)));
        Array.from(messageRowMap.keys()).forEach((messageId) => {
            if (!validIds.has(messageId)) {
                const row = messageRowMap.get(messageId);
                if (row) {
                    row.remove();
                }
                messageRowMap.delete(messageId);
            }
        });
    }

    function syncRenderedMessageNodes(desiredNodes) {
        if (!messagesStream) {
            return;
        }
        clearEmptyMessageState();
        desiredNodes.forEach((node, index) => {
            const currentNode = messagesStream.children[index];
            if (currentNode !== node) {
                messagesStream.insertBefore(node, currentNode || null);
            }
        });
        while (messagesStream.children.length > desiredNodes.length) {
            messagesStream.lastElementChild.remove();
        }
    }

    function renderChatMessages(conversation, options) {
        if (!messagesStream) {
            return;
        }
        const query = (searchInput && searchInput.value ? searchInput.value : "").trim().toLowerCase();
        const stickToBottom = options && Object.prototype.hasOwnProperty.call(options, "stickToBottom")
            ? !!options.stickToBottom
            : ((messagesStream.scrollHeight - messagesStream.scrollTop - messagesStream.clientHeight) < 96);
        if (!conversation) {
            renderEmptyConversationState();
            return;
        }

        const allMessages = Array.isArray(conversation.messages) ? conversation.messages : [];
        const messages = query
            ? allMessages.filter((message) => (
                `${message.sender_name || ""} ${message.text || ""} ${message.attachment_name || ""}`.toLowerCase().includes(query)
            ))
            : allMessages;
        if (renderedConversationId !== conversation.id) {
            clearMessagesRenderState();
            renderedConversationId = conversation.id;
        }

        pruneDetachedMessageRows(allMessages);
        const desiredNodes = [];
        if (!query) {
            renderHistoryLoader(conversation, desiredNodes);
        } else if (historyLoaderNode) {
            historyLoaderNode.remove();
        }

        messages.forEach((message) => {
            const messageId = String(message.id);
            let row = messageRowMap.get(messageId);
            if (!row) {
                row = createMessageRow(message, conversation);
                messageRowMap.set(messageId, row);
            } else {
                syncMessageRow(row, message, conversation);
            }
            desiredNodes.push(row);
        });

        if (query && !messages.length) {
            renderMessageListEmptyState(
                "No messages found",
                "Try another search term for this conversation or your contacts."
            );
        } else if (!messages.length) {
            syncRenderedMessageNodes(desiredNodes);
            renderMessageListEmptyState(
                "No messages yet",
                "Send the first message to get this conversation started."
            );
        } else {
            syncRenderedMessageNodes(desiredNodes);
            if (stickToBottom) {
                scrollMessagesToBottom();
            }
        }
    }

    function renderChat() {
        const conversation = activeConversation();
        renderChatHeaderAndDetails(conversation);
        renderChatMessages(conversation, { stickToBottom: true });
        updateComposerState();
    }

    function renderAll(options) {
        ensureActiveConversationSelection();
        renderLists();
        renderChatHeaderAndDetails(activeConversation());
        renderChatMessages(activeConversation(), options || { stickToBottom: true });
        updateComposerState();
    }

    function openModal(title, body, footer) {
        if (!modalBackdrop || !modalTitle || !modalBody || !modalFoot) {
            return;
        }
        modalTitle.textContent = title;
        modalBody.innerHTML = body;
        modalFoot.innerHTML = footer || '<button class="panel-btn" id="modalOkBtn" type="button">Close</button>';
        modalBackdrop.classList.add("is-open");
        const ok = document.getElementById("modalOkBtn");
        if (ok) {
            ok.addEventListener("click", closeModal);
        }
    }

    function closeModal() {
        if (modalBackdrop) {
            modalBackdrop.classList.remove("is-open");
        }
    }

    function showMessagingError(message, title) {
        openModal(title || "Messaging", `<p>${escapeHtml(message || "Something went wrong.")}</p>`);
    }

    function updateComposerState() {
        const conversation = activeConversation();
        const lockState = conversationLockState(conversation);
        const isDisabled = !conversation || lockState.locked;
        if (chatInput) {
            chatInput.disabled = isDisabled;
            chatInput.placeholder = lockState.locked ? lockState.message : "Type a message...";
        }
        if (sendBtn) {
            sendBtn.disabled = isDisabled || !(chatInput && chatInput.value.trim());
        }
        if (inputAttachBtn) {
            inputAttachBtn.disabled = isDisabled;
        }
        if (voiceRecordBtn) {
            voiceRecordBtn.disabled = isDisabled;
        }
        if (emojiPickerBtn) {
            emojiPickerBtn.disabled = isDisabled;
        }
        if (chatInputBar) {
            chatInputBar.classList.toggle("is-locked", !!(conversation && lockState.locked));
        }
        if (composerLockOverlay) {
            const showLockOverlay = !!(conversation && lockState.locked);
            composerLockOverlay.hidden = !showLockOverlay;
            if (composerLockTitle) {
                composerLockTitle.textContent = lockState.title;
            }
            if (composerLockMessage) {
                composerLockMessage.textContent = lockState.message;
            }
        }
        if (composerBlockToggleBtn) {
            composerBlockToggleBtn.textContent = lockState.blockActionLabel;
            composerBlockToggleBtn.hidden = !(conversation && conversation.conversation_type !== "group");
        }
        if (composerReportBtn) {
            composerReportBtn.hidden = !(conversation && conversation.conversation_type !== "group");
        }
    }

    function updateSummaryForNewMessage(conversation, message) {
        conversation.preview = message.text
            || (message.message_type === "image"
                ? "Sent an image"
                : message.message_type === "voice"
                    ? "Sent a voice message"
                    : message.message_type === "file"
                        ? `Shared ${message.attachment_name || "a file"}`
                        : "Start the conversation");
        conversation.time = "Now";
        conversation.last_message_at = message.created_at || new Date().toISOString();
    }

    function appendSharedFileFromMessage(conversation, message) {
        if (!conversation || !message.attachment_url) {
            return;
        }
        const files = Array.isArray(conversation.shared_files) ? conversation.shared_files : [];
        if (files.some((item) => item.id === message.id)) {
            return;
        }
        files.unshift({
            id: message.id,
            message_type: message.message_type || "file",
            name: message.attachment_name || "Attachment",
            url: normalizeMessagingUrl(message.attachment_url),
            created_at: message.created_at,
            sender_name: message.sender_name || "CoVise member",
            attachment_size: message.attachment_size || null,
        });
        conversation.shared_files = files;
    }

    function applyIncomingMessage(data) {
        const conversationId = data.conversation_id;
        let summary = findConversationSummary(conversationId);
        if (!summary) {
            syncMessagesState({ stickToBottom: true });
            return;
        }

        const incomingMessage = {
            id: data.message_id,
            sender_id: data.sender_id,
            sender_name: data.sender_name,
            text: data.message,
            created_at: data.created_at,
            receipt: data.receipt || "sent",
            message_type: data.message_type || "text",
            attachment_url: normalizeMessagingUrl(data.attachment_url),
            attachment_name: data.attachment_name || "",
            attachment_content_type: data.attachment_content_type || "",
            attachment_size: data.attachment_size || null,
            is_ephemeral: !!data.is_ephemeral,
            reaction_counts: data.reaction_counts || { thumbs_up: 0, fire: 0 },
            viewer_reactions: Array.isArray(data.viewer_reactions) ? data.viewer_reactions : [],
        };

        if (activeConversationData && activeConversationData.id === conversationId) {
            const existingIndex = activeConversationData.messages.findIndex((message) => message.id === incomingMessage.id);
            if (existingIndex >= 0) {
                activeConversationData.messages[existingIndex] = {
                    ...activeConversationData.messages[existingIndex],
                    ...incomingMessage,
                };
            } else {
                activeConversationData.messages.push(incomingMessage);
            }
            activeConversationData.messages.sort((left, right) => parseIsoDate(left.created_at) - parseIsoDate(right.created_at));
            updateSummaryForNewMessage(activeConversationData, incomingMessage);
            appendSharedFileFromMessage(activeConversationData, incomingMessage);
            if (incomingMessage.sender_id === currentUserId) {
                activeConversationData.unread = 0;
            }
            syncSummaryFromActiveConversation();
            renderLists();
            renderChatMessages(activeConversationData, { stickToBottom: true });
            renderSharedFiles(activeConversationData);
        } else {
            updateSummaryForNewMessage(summary, incomingMessage);
            summary.unread = Number(summary.unread || 0) + (incomingMessage.sender_id === currentUserId ? 0 : 1);
            upsertConversationSummary(summary);
            renderLists();
        }

        if (conversationId === activeConversationId && incomingMessage.sender_id !== currentUserId && !incomingMessage.is_ephemeral) {
            markActiveConversationSeen();
        }
    }

    function updateMessageReceipts(conversationId, updates) {
        if (!activeConversationData || activeConversationData.id !== conversationId || !Array.isArray(updates) || !updates.length) {
            return;
        }
        updates.forEach((update) => {
            const message = activeConversationData.messages.find((item) => item.id === update.message_id);
            if (message) {
                message.receipt = update.receipt || message.receipt || "sent";
                const row = messageRowMap.get(String(message.id));
                if (row) {
                    syncMessageRow(row, message, activeConversationData);
                }
            }
        });
    }

    function markActiveConversationSeen() {
        const conversation = activeConversation();
        if (!conversation || !activeConversationId) {
            return;
        }
        fetch(`/messages/${activeConversationId}/seen/`, {
            method: "POST",
            headers: { "X-CSRFToken": csrftoken },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    return;
                }
                conversation.unread = 0;
                syncSummaryFromActiveConversation();
                renderLists();
                updateMessageReceipts(activeConversationId, result.data.updates || []);
            })
            .catch(() => {});
    }

    function disconnectSocket() {
        if (reconnectTimer) {
            window.clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        if (chatSocket && chatSocket.readyState !== WebSocket.CLOSED) {
            chatSocket._manualClose = true;
            chatSocket.close();
        }
        chatSocket = null;
        socketConversationId = "";
    }

    function scheduleSocketReconnect(conversationId) {
        if (!conversationId) {
            return;
        }
        if (reconnectTimer) {
            window.clearTimeout(reconnectTimer);
        }
        const attempt = Math.min(socketReconnectAttempts + 1, 6);
        socketReconnectAttempts = attempt;
        const delay = Math.min(1000 * (2 ** (attempt - 1)), 15000);
        reconnectTimer = window.setTimeout(() => {
            reconnectTimer = null;
            if (activeConversationId === conversationId) {
                connectSocket();
            }
        }, delay);
    }

    function connectSocket() {
        if (!activeConversationId) {
            shouldRecoverStateOnReconnect = false;
            socketReconnectAttempts = 0;
            disconnectSocket();
            return;
        }
        if (
            chatSocket
            && socketConversationId === activeConversationId
            && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)
        ) {
            return;
        }

        const preserveRecovery = shouldRecoverStateOnReconnect && socketConversationId === activeConversationId;
        if (!preserveRecovery) {
            shouldRecoverStateOnReconnect = false;
            socketReconnectAttempts = 0;
        }
        disconnectSocket();

        const socketProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
        const socket = new WebSocket(`${socketProtocol}${window.location.host}/ws/messages/${activeConversationId}/`);
        chatSocket = socket;
        socketConversationId = activeConversationId;

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "chat_error") {
                showMessagingError(data.error, "Messaging error");
                return;
            }
            if (data.type === "conversation_deleted") {
                handleConversationDeleted(data);
                return;
            }
            if (data.type === "message_receipts_seen") {
                updateMessageReceipts(data.conversation_id, data.updates || []);
                return;
            }
            applyIncomingMessage(data);
        };
        socket.onopen = () => {
            if (chatSocket === socket && socketConversationId === activeConversationId) {
                const shouldRecover = shouldRecoverStateOnReconnect;
                shouldRecoverStateOnReconnect = false;
                socketReconnectAttempts = 0;
                if (shouldRecover) {
                    syncMessagesState({ keepScroll: true });
                }
                markActiveConversationSeen();
            }
        };
        socket.onclose = () => {
            if (socket._manualClose || chatSocket !== socket || !activeConversationId) {
                return;
            }
            chatSocket = null;
            shouldRecoverStateOnReconnect = true;
            scheduleSocketReconnect(socketConversationId || activeConversationId);
        };
        socket.onerror = () => {
            if (socket.readyState !== WebSocket.CLOSED) {
                socket.close();
            }
        };
    }

    function handleConversationDeleted(data) {
        const deletedId = data.conversation_id;
        conversationSummaries = conversationSummaries.filter((conversation) => conversation.id !== deletedId);
        if (activeConversationId === deletedId) {
            activeConversationData = null;
            const nextDirect = directConversations()[0];
            if (nextDirect) {
                setActiveConversationId(nextDirect.id, "direct");
                loadConversation(nextDirect.id, "direct", { stickToBottom: true });
            } else {
                setActiveConversationId("", "direct");
                disconnectSocket();
                renderAll({ stickToBottom: true });
            }
        } else {
            renderAll({ stickToBottom: true });
        }
        openModal("Conversation deleted", "<p>This conversation was removed.</p>");
    }

    function applySentMessage(result) {
        if (!result || !result.data || !result.data.message) {
            return;
        }
        applyIncomingMessage({
            conversation_id: result.data.conversation_id,
            message_id: result.data.message.id,
            message: result.data.message.text,
            sender_id: result.data.message.sender_id,
            sender_name: result.data.message.sender_name,
            created_at: result.data.message.created_at,
            receipt: result.data.message.receipt || "sent",
            message_type: result.data.message.message_type,
            attachment_url: result.data.message.attachment_url,
            attachment_name: result.data.message.attachment_name,
            attachment_content_type: result.data.message.attachment_content_type,
            attachment_size: result.data.message.attachment_size,
            is_ephemeral: result.data.message.is_ephemeral,
            reaction_counts: result.data.message.reaction_counts,
            viewer_reactions: result.data.message.viewer_reactions,
        });
    }

    function inferMessageTypeFromFile(file) {
        if (!file || !file.type) {
            return "";
        }
        if (file.type.startsWith("image/")) {
            return "image";
        }
        if (file.type.startsWith("audio/")) {
            return "voice";
        }
        return "file";
    }

    function sendMediaMessage(file, messageType) {
        const conversation = activeConversation();
        if (!conversation) {
            showMessagingError("Select a conversation first.");
            return;
        }
        if (conversationLockState(conversation).locked) {
            updateComposerState();
            showMessagingError(conversationLockState(conversation).message, "Conversation locked");
            return;
        }
        if (!file) {
            return;
        }
        const formData = new FormData();
        formData.append("attachment", file);
        formData.append("message_type", messageType || "");
        formData.append("caption", chatInput ? chatInput.value.trim() : "");

        fetch(`/messages/${conversation.id}/media/`, {
            method: "POST",
            headers: { "X-CSRFToken": csrftoken },
            body: formData,
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    if (result.data && result.data.code === "messaging_blocked") {
                        syncMessagesState({ keepScroll: true });
                    }
                    showMessagingError((result.data && result.data.error) || "We could not send that attachment right now.");
                    return;
                }
                applySentMessage(result);
                if (chatInput) {
                    chatInput.value = "";
                }
                if (chatFileInput) {
                    chatFileInput.value = "";
                }
                updateComposerState();
            })
            .catch(() => {
                showMessagingError("We could not send that attachment right now.");
            });
    }

    function handleSend() {
        const text = chatInput ? chatInput.value.trim() : "";
        const conversation = activeConversation();
        if (!conversation) {
            showMessagingError("Select a conversation first.");
            return;
        }
        if (conversationLockState(conversation).locked) {
            updateComposerState();
            showMessagingError(conversationLockState(conversation).message, "Conversation locked");
            return;
        }
        if (!text) {
            return;
        }
        closeEmojiPicker();
        if (sendBtn) {
            sendBtn.disabled = true;
        }
        fetch(`/messages/${conversation.id}/send/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrftoken,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ message: text }),
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    if (result.data && result.data.code === "messaging_blocked") {
                        syncMessagesState({ keepScroll: true });
                    }
                    updateComposerState();
                    showMessagingError((result.data && result.data.error) || "We could not send your message right now.");
                    return;
                }
                applySentMessage(result);
                if (chatInput) {
                    chatInput.value = "";
                }
                updateComposerState();
            })
            .catch(() => {
                updateComposerState();
                showMessagingError("We could not send your message right now.");
            });
    }

    function stopVoiceRecordingUi() {
        if (voiceRecordBtn) {
            voiceRecordBtn.classList.remove("is-recording");
            voiceRecordBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
        }
        if (recordingIndicator) {
            recordingIndicator.hidden = true;
        }
    }

    function stopVoiceRecorderTracks() {
        if (mediaRecorderStream) {
            mediaRecorderStream.getTracks().forEach((track) => track.stop());
            mediaRecorderStream = null;
        }
    }

    function toggleVoiceRecording() {
        const conversation = activeConversation();
        if (!conversation) {
            showMessagingError("Select a conversation first.", "Voice message");
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
            showMessagingError("Voice recording is not supported in this browser.", "Voice message");
            return;
        }
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
            return;
        }
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then((stream) => {
                mediaRecorderStream = stream;
                mediaChunks = [];
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) {
                        mediaChunks.push(event.data);
                    }
                };
                mediaRecorder.onstop = () => {
                    const mimeType = mediaRecorder.mimeType || "audio/webm";
                    const extension = mimeType.includes("ogg") ? "ogg" : mimeType.includes("mp4") ? "m4a" : mimeType.includes("mpeg") ? "mp3" : "webm";
                    const file = new File(mediaChunks, `voice-note-${Date.now()}.${extension}`, { type: mimeType });
                    stopVoiceRecorderTracks();
                    stopVoiceRecordingUi();
                    mediaRecorder = null;
                    mediaChunks = [];
                    sendMediaMessage(file, "voice");
                };
                mediaRecorder.onerror = () => {
                    stopVoiceRecorderTracks();
                    stopVoiceRecordingUi();
                    mediaRecorder = null;
                    mediaChunks = [];
                    showMessagingError("We could not record that voice message right now.", "Voice message");
                };
                mediaRecorder.start();
                if (voiceRecordBtn) {
                    voiceRecordBtn.classList.add("is-recording");
                    voiceRecordBtn.innerHTML = '<i class="fa-solid fa-stop"></i>';
                }
                if (recordingIndicator) {
                    recordingIndicator.hidden = false;
                }
            })
            .catch(() => {
                stopVoiceRecorderTracks();
                stopVoiceRecordingUi();
                showMessagingError("Microphone access is required to send a voice message.", "Voice message");
            });
    }

    function loadOlderMessages() {
        const conversation = activeConversation();
        if (!conversation || !conversation.has_older_messages || !conversation.oldest_loaded_message_id) {
            return;
        }
        const url = new URL(`/messages/${conversation.id}/history/`, window.location.origin);
        url.searchParams.set("before", conversation.oldest_loaded_message_id);
        fetch(url.toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    showMessagingError((result.data && result.data.error) || "We could not load older messages right now.");
                    return;
                }
                const incomingMessages = Array.isArray(result.data.messages) ? result.data.messages : [];
                const seenMessageIds = new Set((conversation.messages || []).map((message) => message.id));
                conversation.messages = [
                    ...incomingMessages.filter((message) => !seenMessageIds.has(message.id)),
                    ...(conversation.messages || []),
                ];
                conversation.has_older_messages = !!result.data.has_older_messages;
                conversation.oldest_loaded_message_id = result.data.oldest_loaded_message_id || "";
                renderChatMessages(conversation, { stickToBottom: false });
            })
            .catch(() => {
                showMessagingError("We could not load older messages right now.");
            });
    }

    function openReactionPicker(messageId) {
        openModal(
            "React to message",
            `
                <div class="message-react-picker">
                    ${reactionChoices.map((choice) => `
                        <button class="message-react-option" type="button" data-react-choice="${choice.key}" data-message-id="${escapeHtml(messageId)}">
                            ${choice.label}
                        </button>
                    `).join("")}
                </div>
            `
        );
        document.querySelectorAll("[data-react-choice]").forEach((button) => {
            button.addEventListener("click", () => {
                toggleMessageReaction(messageId, button.dataset.reactChoice || "");
                closeModal();
            });
        });
    }

    function toggleMessageReaction(messageId, reactionKey) {
        if (!messageId || !reactionKey || !activeConversationData) {
            return;
        }
        fetch(`/messages/reactions/${messageId}/${reactionKey}/`, {
            method: "POST",
            headers: { "X-CSRFToken": csrftoken },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    showMessagingError((result.data && result.data.error) || "We could not update the reaction right now.");
                    return;
                }
                const message = activeConversationData.messages.find((item) => item.id === messageId);
                if (!message) {
                    return;
                }
                message.reaction_counts = result.data.reaction_counts || message.reaction_counts || {};
                message.viewer_reactions = result.data.viewer_reactions || [];
                const row = messageRowMap.get(String(message.id));
                if (row) {
                    syncMessageRow(row, message, activeConversationData);
                }
            })
            .catch(() => {
                showMessagingError("We could not update the reaction right now.");
            });
    }

    function promptReportMessage(messageId) {
        openModal(
            "Report message",
            `
                <label class="modal-label" for="reportMessageReason">Reason</label>
                <select class="modal-select" id="reportMessageReason">
                    <option value="">Select a reason</option>
                    <option value="Spam or scam">Spam or scam</option>
                    <option value="Harassment or abuse">Harassment or abuse</option>
                    <option value="Inappropriate content">Inappropriate content</option>
                    <option value="Other">Other</option>
                </select>
                <div id="reportMessageOtherWrap" hidden>
                    <label class="modal-label" for="reportMessageOther">Tell us more</label>
                    <textarea class="modal-select modal-textarea" id="reportMessageOther" rows="4"></textarea>
                </div>
            `,
            `
                <button class="panel-btn ghost" id="cancelReportMessageBtn" type="button">Cancel</button>
                <button class="panel-btn" id="submitReportMessageBtn" type="button">Send Report</button>
            `
        );
        const reasonSelect = document.getElementById("reportMessageReason");
        const otherWrap = document.getElementById("reportMessageOtherWrap");
        const cancelButton = document.getElementById("cancelReportMessageBtn");
        const submitButton = document.getElementById("submitReportMessageBtn");
        if (cancelButton) {
            cancelButton.addEventListener("click", closeModal);
        }
        if (reasonSelect && otherWrap) {
            reasonSelect.addEventListener("change", () => {
                otherWrap.hidden = reasonSelect.value !== "Other";
            });
        }
        if (submitButton) {
            submitButton.addEventListener("click", () => {
                const body = new URLSearchParams();
                body.append("report_reason", reasonSelect ? reasonSelect.value : "");
                const other = document.getElementById("reportMessageOther");
                body.append("report_reason_other", other ? other.value.trim() : "");
                fetch(`/messages/${messageId}/report-message/`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrftoken,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    body: body.toString(),
                })
                    .then(async (response) => {
                        const data = await response.json();
                        return { ok: response.ok, data };
                    })
                    .then((result) => {
                        if (!result.ok || !result.data.ok) {
                            showMessagingError((result.data && result.data.error) || "We could not send your report right now.", "Report message");
                            return;
                        }
                        openModal("Report sent", `<p>${escapeHtml(result.data.message)}</p>`);
                    })
                    .catch(() => {
                        showMessagingError("We could not send your report right now.", "Report message");
                    });
            });
        }
    }

    function deleteMessage(messageId) {
        if (!activeConversationData) {
            return;
        }
        fetch(`/messages/${messageId}/delete-message/`, {
            method: "POST",
            headers: { "X-CSRFToken": csrftoken },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    showMessagingError((result.data && result.data.error) || "We could not delete this message right now.", "Delete message");
                    return;
                }
                activeConversationData.messages = activeConversationData.messages.filter((message) => message.id !== messageId);
                if (result.data.had_attachment) {
                    activeConversationData.shared_files = (activeConversationData.shared_files || []).filter((item) => item.id !== messageId);
                    renderSharedFiles(activeConversationData);
                }
                activeConversationData.preview = result.data.last_message_preview || "Start the conversation";
                activeConversationData.time = result.data.last_message_time || "New";
                const latestMessage = activeConversationData.messages[activeConversationData.messages.length - 1];
                activeConversationData.last_message_at = latestMessage ? latestMessage.created_at : "";
                activeConversationData.has_older_messages = !!activeConversationData.oldest_loaded_message_id;
                syncSummaryFromActiveConversation();
                renderLists();
                renderChatMessages(activeConversationData, { stickToBottom: false });
            })
            .catch(() => {
                showMessagingError("We could not delete this message right now.", "Delete message");
            });
    }

    function openCreateGroupModal() {
        if (!friendOptions.length) {
            openModal("Create Group", "<p>You can only create a group with friends who already accepted a chat request.</p>");
            return;
        }
        openModal(
            "Create Group",
            `
                <label class="modal-label" for="groupNameInput">Group name</label>
                <input class="modal-input" id="groupNameInput" type="text" placeholder="Founders sprint">
                <label class="modal-label" for="groupFriendPicker">Choose friends</label>
                <div class="friend-picker-grid" id="groupFriendPicker">
                    ${friendOptions.map((friend) => `
                        <label class="friend-option">
                            <input type="checkbox" value="${escapeHtml(friend.id)}">
                            <div class="avatar">${avatarInnerMarkup(friend.avatar_initials, friend.avatar_url, friend.display_name)}</div>
                            <div class="friend-option-copy">
                                <strong>${escapeHtml(friend.display_name)}</strong>
                                <span>Friend</span>
                            </div>
                        </label>
                    `).join("")}
                </div>
            `,
            `
                <button class="panel-btn ghost" id="cancelCreateGroupBtn" type="button">Cancel</button>
                <button class="panel-btn" id="confirmCreateGroupBtn" type="button">Create Group</button>
            `
        );
        const cancelButton = document.getElementById("cancelCreateGroupBtn");
        const confirmButton = document.getElementById("confirmCreateGroupBtn");
        if (cancelButton) {
            cancelButton.addEventListener("click", closeModal);
        }
        if (confirmButton) {
            confirmButton.addEventListener("click", () => {
                const groupNameInput = document.getElementById("groupNameInput");
                const selectedParticipantIds = Array.from(document.querySelectorAll("#groupFriendPicker input[type='checkbox']:checked"))
                    .map((input) => input.value);
                fetch("/messages/groups/create/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrftoken,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        group_name: groupNameInput ? groupNameInput.value.trim() : "",
                        participant_ids: selectedParticipantIds,
                    }),
                })
                    .then(async (response) => {
                        const data = await response.json();
                        return { ok: response.ok, data };
                    })
                    .then((result) => {
                        if (!result.ok || !result.data.ok) {
                            showMessagingError((result.data && result.data.error) || "We could not create that group right now.", "Create Group");
                            return;
                        }
                        closeModal();
                        loadConversation(result.data.conversation_id, "groups", { stickToBottom: true });
                    })
                    .catch(() => {
                        showMessagingError("We could not create that group right now.", "Create Group");
                    });
            });
        }
    }

    function promptReportConversation() {
        const conversation = activeConversation();
        if (!conversation) {
            showMessagingError("Select a conversation first.", "Report User");
            return;
        }
        openModal(
            "Report User",
            `
                <label class="modal-label" for="reportReasonSelect">Reason</label>
                <select class="modal-select" id="reportReasonSelect">
                    <option value="">Select a reason</option>
                    <option value="Spam or scam">Spam or scam</option>
                    <option value="Harassment or abuse">Harassment or abuse</option>
                    <option value="Fake or misleading profile">Fake or misleading profile</option>
                    <option value="Inappropriate content">Inappropriate content</option>
                    <option value="Other">Other</option>
                </select>
                <div id="reportReasonOtherWrap" hidden>
                    <label class="modal-label" for="reportReasonOther">Tell us more</label>
                    <textarea class="modal-select modal-textarea" id="reportReasonOther" rows="4"></textarea>
                </div>
                <label class="toggle-row">
                    <span>Also block this user</span>
                    <input id="reportBlockToggle" type="checkbox">
                    <span class="toggle-slider"></span>
                </label>
            `,
            `
                <button class="panel-btn ghost" id="modalCancelBtn" type="button">Cancel</button>
                <button class="panel-btn" id="submitConversationReportBtn" type="button">Send Report</button>
            `
        );
        const cancelButton = document.getElementById("modalCancelBtn");
        const reasonSelect = document.getElementById("reportReasonSelect");
        const otherWrap = document.getElementById("reportReasonOtherWrap");
        const submitButton = document.getElementById("submitConversationReportBtn");
        if (cancelButton) {
            cancelButton.addEventListener("click", closeModal);
        }
        if (reasonSelect && otherWrap) {
            reasonSelect.addEventListener("change", () => {
                otherWrap.hidden = reasonSelect.value !== "Other";
            });
        }
        if (submitButton) {
            submitButton.addEventListener("click", () => {
                const body = new URLSearchParams();
                body.append("report_reason", reasonSelect ? reasonSelect.value : "");
                const otherReason = document.getElementById("reportReasonOther");
                body.append("report_reason_other", otherReason ? otherReason.value.trim() : "");
                const blockToggle = document.getElementById("reportBlockToggle");
                if (blockToggle && blockToggle.checked) {
                    body.append("block_user", "1");
                }
                fetch(`/messages/${conversation.id}/report/`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrftoken,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    body: body.toString(),
                })
                    .then(async (response) => {
                        const data = await response.json();
                        return { ok: response.ok, data };
                    })
                    .then((result) => {
                        if (!result.ok || !result.data.ok) {
                            showMessagingError((result.data && result.data.error) || "We could not send your report right now.", "Report User");
                            return;
                        }
                        if (blockToggle && blockToggle.checked) {
                            applyConversationBlockState(conversation, { blocked_by_current_user: true });
                            updateComposerState();
                        }
                        renderChatHeaderAndDetails(conversation);
                        openModal("Report sent", `<p>${escapeHtml(result.data.message)}</p>`);
                    })
                    .catch(() => {
                        showMessagingError("We could not send your report right now.", "Report User");
                    });
            });
        }
    }

    function toggleBlockedUser() {
        const conversation = activeConversation();
        if (!conversation || !conversation.partner_id) {
            showMessagingError("Select a private conversation first.", "Block User");
            return;
        }
        fetch(`/users/${conversation.partner_id}/block/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrftoken,
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    showMessagingError((result.data && result.data.error) || "Unable to update block status right now.", "Block User");
                    return;
                }
                applyConversationBlockState(conversation, { blocked_by_current_user: !!result.data.blocked });
                renderChatHeaderAndDetails(conversation);
                renderLists();
                updateComposerState();
                openModal(result.data.blocked ? "User blocked" : "User unblocked", `<p>${escapeHtml(result.data.message)}</p>`);
            })
            .catch(() => {
                showMessagingError("Unable to update block status right now.", "Block User");
            });
    }

    function deleteConversation() {
        const conversation = activeConversation();
        if (!conversation) {
            showMessagingError("Select a conversation first.", "Delete Conversation");
            return;
        }
        openModal(
            "Delete Conversation",
            "<p>This will remove the conversation and its saved messages for both participants. This cannot be undone.</p>",
            `
                <button class="panel-btn ghost" id="cancelDeleteConversationBtn" type="button">Cancel</button>
                <button class="panel-btn danger" id="confirmDeleteConversationBtn" type="button">Delete Conversation</button>
            `
        );
        const cancelButton = document.getElementById("cancelDeleteConversationBtn");
        const confirmButton = document.getElementById("confirmDeleteConversationBtn");
        if (cancelButton) {
            cancelButton.addEventListener("click", closeModal);
        }
        if (confirmButton) {
            confirmButton.addEventListener("click", () => {
                fetch(`/messages/${conversation.id}/delete/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrftoken },
                })
                    .then(async (response) => {
                        const data = await response.json();
                        return { ok: response.ok, data };
                    })
                    .then((result) => {
                        if (!result.ok || !result.data.ok) {
                            showMessagingError((result.data && result.data.error) || "We could not delete this conversation right now.", "Delete Conversation");
                            return;
                        }
                        closeModal();
                        handleConversationDeleted({ conversation_id: conversation.id });
                    })
                    .catch(() => {
                        showMessagingError("We could not delete this conversation right now.", "Delete Conversation");
                    });
            });
        }
    }

    function bindStaticControls() {
        if (directTabBtn) {
            directTabBtn.addEventListener("click", () => {
                activeTab = "direct";
                renderLists();
            });
        }
        if (groupsTabBtn) {
            groupsTabBtn.addEventListener("click", () => {
                activeTab = "groups";
                renderLists();
            });
        }
        if (searchInput) {
            searchInput.addEventListener("input", () => renderAll({ stickToBottom: false }));
        }
        const toggleDetailsBtn = document.getElementById("toggleDetailsBtn");
        if (toggleDetailsBtn) {
            toggleDetailsBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                app.classList.toggle("details-open");
            });
        }
        const closeDetailsBtn = document.getElementById("closeDetailsBtn");
        if (closeDetailsBtn) {
            closeDetailsBtn.addEventListener("click", () => app.classList.remove("details-open"));
        }
        const mobileBackBtn = document.getElementById("mobileBackBtn");
        if (mobileBackBtn) {
            mobileBackBtn.addEventListener("click", () => app.classList.remove("mobile-chat-open"));
        }
        const mobileCloseChat = document.getElementById("mobileCloseChat");
        if (mobileCloseChat) {
            mobileCloseChat.addEventListener("click", () => app.classList.remove("mobile-chat-open"));
        }
        document.querySelectorAll(".details-tab").forEach((button) => {
            button.addEventListener("click", () => {
                const tab = button.dataset.detailsTab;
                document.querySelectorAll(".details-tab").forEach((item) => item.classList.remove("is-active"));
                document.querySelectorAll(".details-pane").forEach((pane) => pane.classList.remove("is-active"));
                button.classList.add("is-active");
                const pane = document.querySelector(`.details-pane[data-pane="${tab}"]`);
                if (pane) {
                    pane.classList.add("is-active");
                }
            });
        });
        if (panelMoreMenuBtn && panelMoreMenu) {
            panelMoreMenuBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                panelMoreMenu.classList.toggle("is-open");
            });
            panelMoreMenu.addEventListener("click", (event) => {
                event.stopPropagation();
                const button = event.target.closest("button");
                if (!button) {
                    return;
                }
                panelMoreMenu.classList.remove("is-open");
                if (button.dataset.action === "create-group") {
                    openCreateGroupModal();
                }
            });
        }
        document.addEventListener("click", (event) => {
            if (panelMoreMenu && panelMoreMenuBtn && !panelMoreMenu.contains(event.target) && !panelMoreMenuBtn.contains(event.target)) {
                panelMoreMenu.classList.remove("is-open");
            }
            if (emojiPickerPanel && emojiPickerBtn && !emojiPickerPanel.contains(event.target) && !emojiPickerBtn.contains(event.target)) {
                closeEmojiPicker();
            }
            if (!event.target.closest(".msg-menu-wrap")) {
                closeMessageMenus();
            }
        });
        if (chatInput) {
            chatInput.addEventListener("input", updateComposerState);
            chatInput.addEventListener("keydown", (event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    handleSend();
                }
            });
            chatInput.addEventListener("focus", () => {
                updateMobileKeyboardInset();
                window.setTimeout(updateMobileKeyboardInset, 80);
            });
            chatInput.addEventListener("blur", () => {
                window.setTimeout(updateMobileKeyboardInset, 0);
            });
        }
        if (sendBtn) {
            sendBtn.addEventListener("click", handleSend);
        }
        if (inputAttachBtn && chatFileInput) {
            inputAttachBtn.addEventListener("click", () => chatFileInput.click());
            chatFileInput.addEventListener("change", () => {
                const file = chatFileInput.files && chatFileInput.files[0];
                if (file) {
                    sendMediaMessage(file, inferMessageTypeFromFile(file));
                }
            });
        }
        if (voiceRecordBtn) {
            voiceRecordBtn.addEventListener("click", toggleVoiceRecording);
        }
        if (emojiPickerBtn && emojiPickerPanel) {
            emojiPickerBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                emojiPickerPanel.hidden = !emojiPickerPanel.hidden;
            });
        }
        const searchInChatBtn = document.getElementById("searchInChatBtn");
        if (searchInChatBtn && searchInput) {
            searchInChatBtn.addEventListener("click", () => searchInput.focus());
        }
        if (window.visualViewport) {
            window.visualViewport.addEventListener("resize", updateMobileKeyboardInset);
            window.visualViewport.addEventListener("scroll", updateMobileKeyboardInset);
        }
        window.addEventListener("orientationchange", () => {
            window.setTimeout(updateMobileKeyboardInset, 120);
        });
        if (createGroupBtn) {
            createGroupBtn.addEventListener("click", openCreateGroupModal);
        }
        if (muteNotificationsToggle) {
            muteNotificationsToggle.addEventListener("change", () => {
                const conversation = activeConversation();
                if (!conversation) {
                    muteNotificationsToggle.checked = false;
                    return;
                }
                fetch(`/messages/${conversation.id}/mute/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrftoken },
                })
                    .then(async (response) => {
                        const data = await response.json();
                        return { ok: response.ok, data };
                    })
                    .then((result) => {
                        if (!result.ok || !result.data.ok) {
                            muteNotificationsToggle.checked = !muteNotificationsToggle.checked;
                            showMessagingError((result.data && result.data.error) || "We could not update notification settings right now.", "Mute notifications");
                            return;
                        }
                        conversation.mute_notifications = !!result.data.mute_notifications;
                        syncSummaryFromActiveConversation();
                    })
                    .catch(() => {
                        muteNotificationsToggle.checked = !muteNotificationsToggle.checked;
                        showMessagingError("We could not update notification settings right now.", "Mute notifications");
                    });
            });
        }
        if (recordingModeToggle) {
            recordingModeToggle.addEventListener("change", () => {
                const conversation = activeConversation();
                if (!conversation) {
                    recordingModeToggle.checked = true;
                    return;
                }
                fetch(`/messages/${conversation.id}/recording/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrftoken },
                })
                    .then(async (response) => {
                        const data = await response.json();
                        return { ok: response.ok, data };
                    })
                    .then((result) => {
                        if (!result.ok || !result.data.ok) {
                            recordingModeToggle.checked = !recordingModeToggle.checked;
                            showMessagingError((result.data && result.data.error) || "We could not update recording settings right now.", "Record chat history");
                            return;
                        }
                        conversation.recording_mode = result.data.recording_mode;
                        conversation.pinned = result.data.banner || "";
                        syncSummaryFromActiveConversation();
                        renderChatHeaderAndDetails(conversation);
                    })
                    .catch(() => {
                        recordingModeToggle.checked = !recordingModeToggle.checked;
                        showMessagingError("We could not update recording settings right now.", "Record chat history");
                    });
            });
        }
        const blockUserBtn = document.getElementById("blockUserBtn");
        if (blockUserBtn) {
            blockUserBtn.addEventListener("click", toggleBlockedUser);
        }
        const reportUserBtn = document.getElementById("reportUserBtn");
        if (reportUserBtn) {
            reportUserBtn.addEventListener("click", promptReportConversation);
        }
        if (composerReportBtn) {
            composerReportBtn.addEventListener("click", promptReportConversation);
        }
        if (composerBlockToggleBtn) {
            composerBlockToggleBtn.addEventListener("click", toggleBlockedUser);
        }
        const deleteConversationBtn = document.getElementById("deleteConversationBtn");
        if (deleteConversationBtn) {
            deleteConversationBtn.addEventListener("click", deleteConversation);
        }
        const createAgreementBtn = document.getElementById("createAgreementBtn");
        if (createAgreementBtn) {
            createAgreementBtn.addEventListener("click", () => {
                openModal("Contract Maker", "<p>Contract Maker is still coming soon for private chats.</p>");
            });
        }
        if (modalBackdrop) {
            modalBackdrop.addEventListener("click", (event) => {
                if (event.target === modalBackdrop) {
                    closeModal();
                }
            });
        }
        const closeModalBtn = document.getElementById("closeModalBtn");
        if (closeModalBtn) {
            closeModalBtn.addEventListener("click", closeModal);
        }
        if (messagesStream) {
            messagesStream.addEventListener("click", (event) => {
                const historyButton = event.target.closest("[data-load-older]");
                if (historyButton) {
                    loadOlderMessages();
                    return;
                }
                const menuToggle = event.target.closest("[data-message-menu-toggle]");
                if (menuToggle) {
                    const menu = document.querySelector(`[data-message-menu="${menuToggle.dataset.messageMenuToggle}"]`);
                    if (menu) {
                        const isOpen = menu.classList.contains("is-open");
                        closeMessageMenus();
                        menu.classList.toggle("is-open", !isOpen);
                    }
                    return;
                }
                const actionButton = event.target.closest("[data-message-action]");
                if (actionButton) {
                    closeMessageMenus();
                    const messageId = actionButton.dataset.messageId || "";
                    if (actionButton.dataset.messageAction === "react") {
                        openReactionPicker(messageId);
                    } else if (actionButton.dataset.messageAction === "report") {
                        promptReportMessage(messageId);
                    } else if (actionButton.dataset.messageAction === "delete") {
                        deleteMessage(messageId);
                    }
                    return;
                }
                const reactionChip = event.target.closest("[data-reaction-toggle]");
                if (reactionChip) {
                    toggleMessageReaction(reactionChip.dataset.messageId || "", reactionChip.dataset.reactionToggle || "");
                }
            });
        }
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) {
                syncMessagesState({ keepScroll: true });
                connectSocket();
            }
        });
    }

    renderEmojiPicker();
    bindStaticControls();
    ensureActiveConversationSelection();
    if (activeConversationData && activeConversationData.id !== activeConversationId) {
        activeConversationData = null;
    }
    renderAll({ stickToBottom: true });
    connectSocket();
    if (activeConversation() && activeConversationSummary() && activeConversationSummary().unread) {
        markActiveConversationSeen();
    }
    if (initialMessageError) {
        openModal("Messaging blocked", `<p>${escapeHtml(initialMessageError)}</p>`);
    }
})();
