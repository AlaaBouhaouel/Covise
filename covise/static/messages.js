(function () {
    const conversations = JSON.parse(
        document.getElementById("conversation-data").textContent
    );
    const friendOptions = JSON.parse(
        document.getElementById("friend-options").textContent
    );
    const activeConversationValue = JSON.parse(
        document.getElementById("active-conversation-id").textContent
    );
    const initialMessageError = JSON.parse(
        document.getElementById("message-error").textContent
    );
    const currentUserId = JSON.parse(
        document.getElementById("current-user-id").textContent
    );

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
    const sendBtn = document.getElementById("sendBtn");
    const chatName = document.getElementById("chatName");
    const chatNameLink = document.getElementById("chatNameLink");
    const chatStatus = document.getElementById("chatStatus");
    const chatAvatar = document.getElementById("chatAvatar");
    const chatMatchPill = document.getElementById("chatMatchPill");
    const pinnedText = document.getElementById("pinnedText");
    const detailsName = document.getElementById("detailsName");
    const detailsPersonName = document.getElementById("detailsPersonName");
    const detailsPersonLink = document.getElementById("detailsPersonLink");
    const detailsAvatar = document.getElementById("detailsAvatar");
    const detailsMatchPill = document.getElementById("detailsMatchPill");
    const detailsMatchedOn = document.getElementById("detailsMatchedOn");
    const detailsUserType = document.getElementById("detailsUserType");
    const detailsIndustry = document.getElementById("detailsIndustry");
    const detailsStage = document.getElementById("detailsStage");
    const detailsMutual = document.getElementById("detailsMutual");
    const convictionFill = document.getElementById("convictionFill");
    const convictionValue = document.getElementById("convictionValue");
    const viewFullProfileBtn = document.getElementById("viewFullProfileBtn");
    const moreMenu = document.getElementById("moreMenu");
    const modalBackdrop = document.getElementById("modalBackdrop");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");
    const modalFoot = document.getElementById("modalFoot");
    const chatInput = document.getElementById("chatInput");
    const searchInChatBtn = document.getElementById("searchInChatBtn");
    const inputAttachBtn = document.getElementById("inputAttachBtn");
    const chatFileInput = document.getElementById("chatFileInput");
    const voiceRecordBtn = document.getElementById("voiceRecordBtn");
    const recordingIndicator = document.getElementById("recordingIndicator");
    const emojiPickerBtn = document.getElementById("emojiPickerBtn");
    const emojiPickerPanel = document.getElementById("emojiPickerPanel");
    const emojiFacesGrid = document.getElementById("emojiFacesGrid");
    const emojiHandsGrid = document.getElementById("emojiHandsGrid");
    const emojiIdeasGrid = document.getElementById("emojiIdeasGrid");
    const muteNotificationsToggle = document.getElementById("muteNotificationsToggle");
    const recordingModeToggle = document.getElementById("recordingModeToggle");
    const sharedFilesList = document.getElementById("sharedFilesList");
    const notifBell = document.getElementById("notifBell");
    const notifPanel = document.getElementById("notifPanel");

    let activeTab = "direct";
    let activeConversationId = activeConversationValue || (conversations[0] ? conversations[0].id : "");
    let chatSocket = null;
    let reconnectTimer = null;
    let socketConversationId = "";
    let mediaRecorder = null;
    let mediaRecorderStream = null;
    let mediaChunks = [];
    const emojiSets = {
        faces: ["😀", "😂", "😊", "😍", "🤔", "😭", "😎", "🥳", "😴", "😅", "🤯", "🥹", "😇", "🤝"],
        hands: ["👍", "👎", "👏", "🙌", "🙏", "👌", "🤌", "✌️", "🤞", "💪", "👋", "🤙", "🫶", "✍️"],
        ideas: ["🔥", "🚀", "💡", "✅", "📌", "🎯", "💼", "📈", "🌍", "⚡", "🎉", "💬", "🧠", "🤖"],
    };

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let index = 0; index < cookies.length; index += 1) {
                const cookie = cookies[index].trim();
                if (cookie.substring(0, name.length + 1) === name + "=") {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken = getCookie("csrftoken");

    function receiptHTML(receipt) {
        if (receipt === "sent") return '<span class="receipt">✓</span>';
        if (receipt === "delivered") return '<span class="receipt">✓✓</span>';
        if (receipt === "seen") return '<span class="receipt seen">✓✓</span>';
        return "";
    }

    function escapeHtml(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function avatarInnerMarkup(initials, avatarUrl, name) {
        if (avatarUrl) {
            return `<img class="avatar-image" src="${escapeHtml(avatarUrl)}" alt="${escapeHtml((name || "CoVise member"))} avatar">`;
        }
        return escapeHtml(initials || "CV");
    }

    function setAvatarElement(element, initials, avatarUrl, name) {
        if (!element) {
            return;
        }
        if (avatarUrl) {
            element.innerHTML = avatarInnerMarkup(initials, avatarUrl, name);
        } else {
            element.textContent = initials || "CV";
        }
    }

    function formatFileSize(value) {
        const size = Number(value || 0);
        if (!size) return "";
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / (1024 * 1024)).toFixed(1)} MB`;
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
        sendBtn.disabled = chatInput.value.trim().length === 0;
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

    function activeConversation() {
        return conversations.find((conversation) => conversation.id === activeConversationId) || null;
    }

    function conversationSortTimestamp(conversation) {
        const lastMessage = Array.isArray(conversation.messages) && conversation.messages.length
            ? conversation.messages[conversation.messages.length - 1]
            : null;
        const lastMessageTime = lastMessage && lastMessage.created_at ? Date.parse(lastMessage.created_at) : NaN;
        if (!Number.isNaN(lastMessageTime)) {
            return lastMessageTime;
        }
        return -1;
    }

    function sortConversationsByRecent(items) {
        return [...items].sort((left, right) => {
            const rightTime = conversationSortTimestamp(right);
            const leftTime = conversationSortTimestamp(left);
            if (rightTime !== leftTime) {
                return rightTime - leftTime;
            }
            return String(left.name || "").localeCompare(String(right.name || ""));
        });
    }

    function directConversations() {
        return sortConversationsByRecent(
            conversations.filter((conversation) => conversation.conversation_type !== "group")
        );
    }

    function groupConversations() {
        return sortConversationsByRecent(
            conversations.filter((conversation) => conversation.conversation_type === "group")
        );
    }

    function showMessagingError(message, title) {
        openModal(title || "Message not sent", `<p>${message}</p>`);
    }

    function applyIncomingMessage(data) {
        const conversation = conversations.find((item) => item.id === data.conversation_id);
        if (!conversation) {
            return;
        }

        const alreadyExists = conversation.messages.some((item) => item.id === data.message_id);
        if (!alreadyExists) {
            conversation.messages.push({
                id: data.message_id,
                sender_id: data.sender_id,
                sender_name: data.sender_name,
                text: data.message,
                created_at: data.created_at,
                receipt: data.receipt || "sent",
                message_type: data.message_type || "text",
                attachment_url: data.attachment_url || "",
                attachment_name: data.attachment_name || "",
                attachment_content_type: data.attachment_content_type || "",
                attachment_size: data.attachment_size || null,
                is_ephemeral: !!data.is_ephemeral,
                reaction_counts: data.reaction_counts || { thumbs_up: 0, fire: 0 },
                viewer_reactions: data.viewer_reactions || [],
            });
        }

        if (data.message_type === "image") {
            conversation.preview = data.message || "Sent an image";
        } else if (data.message_type === "voice") {
            conversation.preview = data.message || "Sent a voice message";
        } else if (data.message_type === "file") {
            conversation.preview = data.message || `Shared ${data.attachment_name || "a file"}`;
        } else {
            conversation.preview = data.message;
        }
        conversation.time = "Now";
        if (data.attachment_url) {
            conversation.shared_files = conversation.shared_files || [];
            const alreadyListed = conversation.shared_files.some((item) => item.id === data.message_id);
            if (!alreadyListed) {
                conversation.shared_files.unshift({
                    id: data.message_id,
                    message_type: data.message_type || "file",
                    name: data.attachment_name || "Attachment",
                    url: data.attachment_url || "",
                    created_at: data.created_at,
                    sender_name: data.sender_name,
                    attachment_size: data.attachment_size || null,
                });
            }
        }
        if (conversation.id === activeConversationId || data.sender_id === currentUserId) {
            conversation.unread = 0;
        } else {
            conversation.unread += 1;
        }

        renderAll();

        if (conversation.id === activeConversationId && data.sender_id !== currentUserId && !data.is_ephemeral) {
            markActiveConversationSeen();
        }
    }

    function updateMessageReceipts(conversationId, updates) {
        const conversation = conversations.find((item) => item.id === conversationId);
        if (!conversation || !Array.isArray(updates) || !updates.length) {
            return;
        }

        updates.forEach((update) => {
            const message = conversation.messages.find((item) => item.id === update.message_id);
            if (message) {
                message.receipt = update.receipt || message.receipt || "sent";
            }
        });

        renderAll();
    }

    function markActiveConversationSeen() {
        const conversation = activeConversation();
        if (!conversation || !activeConversationId) {
            return;
        }

        fetch(`/messages/${activeConversationId}/seen/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrftoken,
            },
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok || !result.data.updates) {
                    return;
                }
                conversation.unread = 0;
                updateMessageReceipts(activeConversationId, result.data.updates);
            })
            .catch(() => {});
    }

    function ensureActiveConversation() {
        const listForTab = activeTab === "groups" ? groupConversations() : directConversations();
        const current = activeConversation();

        if (current) {
            const currentTab = current.conversation_type === "group" ? "groups" : "direct";
            if (currentTab === activeTab) {
                return;
            }
        }

        if (listForTab.length) {
            activeConversationId = listForTab[0].id;
            return;
        }

        if (!activeConversationId && conversations[0]) {
            activeConversationId = conversations[0].id;
            return;
        }

        if (!activeConversation()) {
            activeConversationId = conversations[0] ? conversations[0].id : "";
        }
    }

    function connectSocket() {
        if (!activeConversationId) {
            return;
        }

        if (
            chatSocket &&
            socketConversationId === activeConversationId &&
            (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)
        ) {
            return;
        }

        if (chatSocket && chatSocket.readyState !== WebSocket.CLOSED) {
            chatSocket._manualClose = true;
            chatSocket.close();
        }

        const socketProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
        const socket = new WebSocket(
            socketProtocol + window.location.host + "/ws/messages/" + activeConversationId + "/"
        );
        chatSocket = socket;
        socketConversationId = activeConversationId;

        socket.onmessage = function (event) {
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
        socket.onopen = function () {
            if (chatSocket === socket && socketConversationId === activeConversationId) {
                markActiveConversationSeen();
            }
        };
        socket.onclose = function () {
            if (socket._manualClose || chatSocket !== socket || !activeConversationId) {
                return;
            }
            if (reconnectTimer) {
                window.clearTimeout(reconnectTimer);
            }
            reconnectTimer = window.setTimeout(function () {
                reconnectTimer = null;
                if (activeConversationId) {
                    connectSocket();
                }
            }, 1500);
        };
        socket.onerror = function () {
            if (socket.readyState !== WebSocket.CLOSED) {
                socket.close();
            }
        };
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

    function buildChatStatusLine(conversation) {
        if (!conversation) {
            return "";
        }
        if (conversation.conversation_type === "group") {
            return conversation.status || "";
        }
        return conversation.country || "";
    }

    function conversationProfileUrl(conversation) {
        if (!conversation || !conversation.partner_id || conversation.conversation_type === "group") {
            return "#";
        }
        return `/profile/user/${conversation.partner_id}/`;
    }

    function renderLists() {
        const query = searchInput.value.trim().toLowerCase();
        directList.innerHTML = "";
        groupsList.innerHTML = "";

        directConversations()
            .filter((conversation) => (
                conversation.name + " " + conversation.preview + " " + conversation.match
            ).toLowerCase().includes(query))
            .forEach((conversation) => {
                const element = document.createElement("button");
                element.type = "button";
                element.className = "conv-item" + (
                    activeTab === "direct" && conversation.id === activeConversationId ? " is-active" : ""
                );
                element.innerHTML = `
                    <div class="conv-avatar-wrap">
                        <div class="avatar">${avatarInnerMarkup(conversation.avatar, conversation.avatar_url, conversation.name)}</div>
                    </div>
                    <div class="conv-main">
                        <div class="conv-head"><h3>${conversation.name}</h3><span>${conversation.time}</span></div>
                        <p>${conversation.preview}</p>
                    <div class="conv-foot">
                        ${conversation.unread ? `<span class="unread-badge">${conversation.unread}</span>` : ""}
                    </div>
                </div>`;
                element.addEventListener("click", () => {
                    activeConversationId = conversation.id;
                    conversation.unread = 0;
                    activeTab = "direct";
                    connectSocket();
                    renderAll();
                    app.classList.add("mobile-chat-open");
                });
                directList.appendChild(element);
            });

        if (!directConversations().length) {
            directList.innerHTML = '<div class="request-item"><div><h3>No conversations yet</h3><p>Open a public profile and press "Request Private Chat" to start one.</p></div></div>';
        }

        groupConversations()
            .filter((conversation) => (
                conversation.name + " " + conversation.preview + " " + conversation.match
            ).toLowerCase().includes(query))
            .forEach((group) => {
            const element = document.createElement("button");
            element.type = "button";
            element.className = "conv-item group-item" + (
                activeTab === "groups" && group.id === activeConversationId ? " is-active" : ""
            );
            element.innerHTML = `
                <div class="avatar">${avatarInnerMarkup(group.avatar, group.avatar_url, group.name)}</div>
                <div class="conv-main">
                    <div class="conv-head"><h3>${group.name}</h3><span>${group.time}</span></div>
                    <p>${group.preview}</p>
                    <div class="conv-foot"><span class="match-pill subtle">${group.status}</span>${group.unread ? `<span class="unread-badge">${group.unread}</span>` : ""}</div>
                </div>`;
            element.addEventListener("click", () => {
                activeConversationId = group.id;
                group.unread = 0;
                activeTab = "groups";
                connectSocket();
                renderAll();
                app.classList.add("mobile-chat-open");
            });
            groupsList.appendChild(element);
        });

        if (!groupConversations().length) {
            groupsList.innerHTML = '<div class="request-item request-empty"><div><h3>No groups yet</h3></div></div>';
        }

        directList.classList.toggle("is-hidden", activeTab !== "direct");
        groupsList.classList.toggle("is-hidden", activeTab !== "groups");
        directTabBtn.classList.toggle("is-active", activeTab === "direct");
        groupsTabBtn.classList.toggle("is-active", activeTab === "groups");
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
                        <span>${escapeHtml(item.sender_name || "CoVise member")} · ${escapeHtml(formatFileSize(item.attachment_size) || "Shared file")}</span>
                    </div>
                </a>
                <a class="file-item-open" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noopener">Open</a>
            `;
            sharedFilesList.appendChild(row);
        });
    }

    function renderMessageBody(message) {
        const messageType = message.message_type || "text";
        const text = escapeHtml(message.text || "");
        const attachmentUrl = escapeHtml(message.attachment_url || "");
        const attachmentName = escapeHtml(message.attachment_name || "Attachment");
        const attachmentSize = escapeHtml(formatFileSize(message.attachment_size) || "");

        if (messageType === "image" && attachmentUrl) {
            return `
                <div class="bubble media-bubble${text ? " has-caption" : ""}">
                    <a href="${attachmentUrl}" target="_blank" rel="noopener">
                        <img class="bubble-image" src="${attachmentUrl}" alt="${attachmentName}">
                    </a>
                    ${text ? `<div class="bubble-caption">${text}</div>` : ""}
                </div>
            `;
        }

        if (messageType === "voice" && attachmentUrl) {
            return `
                <div class="bubble media-bubble${text ? " has-caption" : ""}">
                    <audio class="bubble-audio" controls preload="metadata" src="${attachmentUrl}"></audio>
                    ${text ? `<div class="bubble-caption">${text}</div>` : ""}
                </div>
            `;
        }

        if (messageType === "file" && attachmentUrl) {
            return `
                <div class="bubble media-bubble${text ? " has-caption" : ""}">
                    <a class="bubble-file" href="${attachmentUrl}" target="_blank" rel="noopener">
                        <i class="fa-solid fa-file-arrow-down"></i>
                        <div class="bubble-file-meta">
                            <strong>${attachmentName}</strong>
                            <span>${attachmentSize || "Open file"}</span>
                        </div>
                    </a>
                    ${text ? `<div class="bubble-caption">${text}</div>` : ""}
                </div>
            `;
        }

        return `<div class="bubble">${text}</div>`;
    }

    function closeMessageMenus() {
        document.querySelectorAll(".msg-menu.is-open").forEach((menu) => menu.classList.remove("is-open"));
    }

    function renderMessageMenu(message, isMine) {
        if (!message || message.is_ephemeral) {
            return "";
        }
        const messageId = escapeHtml(message.id);
        return `
            <div class="msg-menu-wrap${isMine ? " is-own" : " is-other"}">
                <button class="msg-menu-trigger" type="button" aria-label="Message actions" data-message-menu-toggle="${messageId}">
                    <i class="fa-solid fa-ellipsis-vertical"></i>
                </button>
                <div class="msg-menu" data-message-menu="${messageId}">
                    <button type="button" data-message-action="react" data-message-id="${messageId}">
                        <i class="fa-regular fa-face-smile"></i>
                        <span>React</span>
                    </button>
                    <button type="button" data-message-action="report" data-message-id="${messageId}">
                        <i class="fa-regular fa-flag"></i>
                        <span>Report</span>
                    </button>
                    ${isMine ? `
                    <button type="button" data-message-action="delete" data-message-id="${messageId}">
                        <i class="fa-regular fa-trash-can"></i>
                        <span>Delete message</span>
                    </button>` : ""}
                </div>
            </div>
        `;
    }

    function renderMessageShell(message, isMine) {
        if (isMine) {
            return `<div class="msg-shell is-own">${renderMessageMenu(message, isMine)}${renderMessageBody(message)}</div>`;
        }
        return `<div class="msg-shell is-other">${renderMessageBody(message)}${renderMessageMenu(message, isMine)}</div>`;
    }

    function renderMessageReactions(message) {
        if (!message || message.is_ephemeral) {
            return "";
        }
        const counts = message.reaction_counts || {};
        const viewerReactions = Array.isArray(message.viewer_reactions) ? message.viewer_reactions : [];
        return `
            <div class="msg-reactions">
                <button class="msg-reaction-chip${viewerReactions.includes("thumbs_up") ? " is-active" : ""}" type="button" data-message-reaction="thumbs_up" data-message-id="${escapeHtml(message.id)}">
                    <span>👍</span>
                    <span>${escapeHtml(counts.thumbs_up || 0)}</span>
                </button>
                <button class="msg-reaction-chip${viewerReactions.includes("fire") ? " is-active" : ""}" type="button" data-message-reaction="fire" data-message-id="${escapeHtml(message.id)}">
                    <span>🔥</span>
                    <span>${escapeHtml(counts.fire || 0)}</span>
                </button>
            </div>
        `;
    }

    function renderGroupSenderLabel(message, conversation, isMine) {
        if (!conversation || conversation.conversation_type !== "group" || isMine) {
            return "";
        }
        return `<div class="msg-sender">${escapeHtml(message.sender_name || "CoVise member")}</div>`;
    }

    function renderChat() {
        const conversation = activeConversation();
        const query = searchInput.value.trim().toLowerCase();
        messagesStream.innerHTML = "";

        if (!conversation) {
            chatName.textContent = "Messages";
            chatStatus.textContent = "";
            setAvatarElement(chatAvatar, "C", "", "CoVise");
            if (chatNameLink) chatNameLink.setAttribute("href", "#");
            if (chatMatchPill) chatMatchPill.textContent = "Private conversation";
            pinnedText.textContent = "Start a private chat from a public profile.";
            if (pinnedText.parentElement) {
                pinnedText.parentElement.classList.remove("is-ephemeral");
                pinnedText.parentElement.classList.remove("is-hidden");
            }
            detailsName.textContent = "No conversation selected";
            detailsPersonName.textContent = "No conversation selected";
            if (detailsPersonLink) detailsPersonLink.setAttribute("href", "#");
            if (viewFullProfileBtn) viewFullProfileBtn.setAttribute("href", "#");
            setAvatarElement(detailsAvatar, "C", "", "CoVise");
            if (detailsMatchPill) detailsMatchPill.textContent = "Private conversation";
            detailsMatchedOn.textContent = "";
            detailsUserType.textContent = "";
            detailsIndustry.textContent = "";
            detailsStage.textContent = "";
            detailsMutual.textContent = "0";
            convictionFill.style.width = "0%";
            convictionValue.textContent = "0/100";
            if (muteNotificationsToggle) muteNotificationsToggle.checked = false;
            if (recordingModeToggle) recordingModeToggle.checked = true;
            renderSharedFiles(null);
            return;
        }

        chatName.textContent = conversation.name;
        if (chatNameLink) chatNameLink.setAttribute("href", conversationProfileUrl(conversation));
        chatStatus.textContent = buildChatStatusLine(conversation);
        setAvatarElement(chatAvatar, conversation.avatar, conversation.avatar_url, conversation.name);
        if (chatMatchPill) chatMatchPill.textContent = conversation.match;
        pinnedText.textContent = conversation.pinned || "Private chat with this member.";
        if (pinnedText.parentElement) {
            const isEphemeralConversation = conversation.recording_mode === "ephemeral";
            pinnedText.parentElement.classList.toggle("is-ephemeral", isEphemeralConversation);
            pinnedText.parentElement.classList.toggle("is-hidden", !conversation.pinned && !isEphemeralConversation);
        }

        detailsName.textContent = conversation.name;
        detailsPersonName.textContent = conversation.name;
        if (detailsPersonLink) detailsPersonLink.setAttribute("href", conversationProfileUrl(conversation));
        if (viewFullProfileBtn) viewFullProfileBtn.setAttribute("href", conversationProfileUrl(conversation));
        setAvatarElement(detailsAvatar, conversation.avatar, conversation.avatar_url, conversation.name);
        if (detailsMatchPill) detailsMatchPill.textContent = conversation.match;
        detailsMatchedOn.textContent = conversation.matchedOn;
        detailsUserType.textContent = conversation.conversation_type === "group" ? "Group conversation" : conversation.userType;
        detailsIndustry.textContent = conversation.conversation_type === "group" ? `${(conversation.group_members || []).length} members` : conversation.industry;
        detailsStage.textContent = conversation.conversation_type === "group"
            ? (conversation.group_members || []).map((member) => member.display_name).join(", ")
            : conversation.stage;
        detailsMutual.textContent = conversation.mutual;
        convictionFill.style.width = "0%";
        convictionValue.textContent = "N/A";
        const blockButton = document.getElementById("blockUserBtn");
        if (blockButton) {
            blockButton.textContent = conversation.blocked_by_current_user ? "Unblock User" : "Block User";
            blockButton.style.display = conversation.conversation_type === "group" ? "none" : "block";
        }
        const reportButton = document.getElementById("reportUserBtn");
        if (reportButton) reportButton.style.display = conversation.conversation_type === "group" ? "none" : "block";
        const deleteButton = document.getElementById("deleteConversationBtn");
        if (deleteButton) deleteButton.style.display = conversation.conversation_type === "group" ? "none" : "block";
        if (muteNotificationsToggle) {
            muteNotificationsToggle.checked = !!conversation.mute_notifications;
        }
        if (recordingModeToggle) {
            recordingModeToggle.checked = conversation.recording_mode !== "ephemeral";
        }
        renderSharedFiles(conversation);

        const visibleMessages = query
            ? conversation.messages.filter((message) => (
                `${message.sender_name || ""} ${message.text || ""} ${message.attachment_name || ""}`.toLowerCase().includes(query)
            ))
            : conversation.messages;

        if (query && !visibleMessages.length) {
            messagesStream.innerHTML = '<div class="request-item"><div><h3>No messages found</h3><p>Try another search term for this conversation or your contacts.</p></div></div>';
            return;
        }

        visibleMessages.forEach((message) => {
            const row = document.createElement("article");
            const isMine = message.sender_id === currentUserId;
            row.className = "msg " + (isMine ? "outgoing" : "incoming");
            row.innerHTML = `${renderGroupSenderLabel(message, conversation, isMine)}${renderMessageShell(message, isMine)}<div class="msg-meta"><span>${formatMessageTime(message.created_at)}</span>${isMine ? receiptHTML(message.receipt || "sent") : ""}</div>`;
            messagesStream.appendChild(row);
        });
        messagesStream.scrollTop = messagesStream.scrollHeight;
    }

    function renderAll() {
        ensureActiveConversation();
        renderLists();
        renderChat();
    }

    function openModal(title, body, footer) {
        modalTitle.textContent = title;
        modalBody.innerHTML = body;
        modalFoot.innerHTML = footer || '<button class="panel-btn" id="modalOkBtn" type="button">Close</button>';
        modalBackdrop.classList.add("is-open");
        const ok = document.getElementById("modalOkBtn");
        if (ok) ok.addEventListener("click", closeModal);
    }

    function closeModal() {
        modalBackdrop.classList.remove("is-open");
    }

    function handleConversationDeleted(data) {
        const deletedId = data.conversation_id;
        const deletedIndex = conversations.findIndex((item) => item.id === deletedId);
        if (deletedIndex === -1) {
            return;
        }
        const wasActive = activeConversationId === deletedId;
        conversations.splice(deletedIndex, 1);
        if (wasActive) {
            activeConversationId = conversations[0] ? conversations[0].id : "";
            if (chatSocket && chatSocket.readyState !== WebSocket.CLOSED) {
                chatSocket._manualClose = true;
                chatSocket.close();
            }
            if (activeConversationId) {
                connectSocket();
            }
        }
        renderAll();
        openModal("Conversation deleted", "<p>This conversation was removed.</p>");
    }

    function applySentMessage(result) {
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
        });
    }

    function sendMediaMessage(file, messageType) {
        const conversation = activeConversation();
        if (!conversation) {
            showMessagingError("Select a conversation first.");
            return;
        }
        if (!file) {
            return;
        }

        const formData = new FormData();
        formData.append("attachment", file);
        formData.append("message_type", messageType || "");
        formData.append("caption", chatInput.value.trim());

        fetch(`/messages/${conversation.id}/media/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrftoken,
            },
            body: formData,
        })
            .then(async (response) => {
                const data = await response.json();
                return { ok: response.ok, data };
            })
            .then((result) => {
                if (!result.ok || !result.data.ok) {
                    showMessagingError((result.data && result.data.error) || "We could not send that attachment right now.");
                    return;
                }
                applySentMessage(result);
                chatInput.value = "";
                sendBtn.disabled = true;
                if (chatFileInput) {
                    chatFileInput.value = "";
                }
            })
            .catch(() => {
                showMessagingError("We could not send that attachment right now.");
            });
    }

    function handleSend() {
        const text = chatInput.value.trim();
        const conversation = activeConversation();

        if (!conversation) {
            showMessagingError("Select a conversation first.");
            return;
        }
        if (!text) {
            return;
        }
        closeEmojiPicker();

        function sendViaHttpFallback() {
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
                        showMessagingError((result.data && result.data.error) || "We could not send your message right now.");
                        return;
                    }
                    applySentMessage(result);
                    chatInput.value = "";
                    sendBtn.disabled = true;
                })
                .catch(() => {
                    showMessagingError("We could not send your message right now.");
                });
        }

        if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
            sendViaHttpFallback();
            return;
        }

        try {
            chatSocket.send(JSON.stringify({
                message: text,
            }));
            chatInput.value = "";
            sendBtn.disabled = true;
        } catch (error) {
            sendViaHttpFallback();
        }
    }

    function openComingSoonModal(title, body) {
        openModal(title, `<p>${body}</p>`);
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

    directTabBtn.addEventListener("click", () => {
        activeTab = "direct";
        renderAll();
    });
    groupsTabBtn.addEventListener("click", () => {
        activeTab = "groups";
        renderAll();
    });
    searchInput.addEventListener("input", renderAll);

    document.getElementById("toggleDetailsBtn").addEventListener("click", () => app.classList.toggle("details-open"));
    document.getElementById("closeDetailsBtn").addEventListener("click", () => app.classList.remove("details-open"));
    document.getElementById("mobileBackBtn").addEventListener("click", () => app.classList.remove("mobile-chat-open"));
    document.getElementById("mobileCloseChat").addEventListener("click", () => app.classList.remove("mobile-chat-open"));

    document.querySelectorAll(".details-tab").forEach((button) => {
        button.addEventListener("click", () => {
            const tab = button.dataset.detailsTab;
            document.querySelectorAll(".details-tab").forEach((item) => item.classList.remove("is-active"));
            document.querySelectorAll(".details-pane").forEach((pane) => pane.classList.remove("is-active"));
            button.classList.add("is-active");
            document.querySelector('.details-pane[data-pane="' + tab + '"]').classList.add("is-active");
        });
    });

    document.getElementById("toggleDetailsBtn").addEventListener("click", (event) => {
        event.stopPropagation();
        moreMenu.classList.toggle("is-open");
    });
    if (panelMoreMenuBtn && panelMoreMenu) {
        panelMoreMenuBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            panelMoreMenu.classList.toggle("is-open");
        });
    }
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".menu-wrap")) {
            moreMenu.classList.remove("is-open");
            if (panelMoreMenu) panelMoreMenu.classList.remove("is-open");
        }
        if (!event.target.closest(".msg-menu-wrap")) {
            closeMessageMenus();
        }
        if (
            emojiPickerPanel &&
            !emojiPickerPanel.hidden &&
            !emojiPickerPanel.contains(event.target) &&
            !emojiPickerBtn.contains(event.target)
        ) {
            closeEmojiPicker();
        }
    });
    moreMenu.addEventListener("click", (event) => {
        event.stopPropagation();
        const button = event.target.closest("button");
        if (!button) return;
        moreMenu.classList.remove("is-open");
        if (button.dataset.action === "details") {
            app.classList.toggle("details-open");
        } else if (button.dataset.action === "contract") {
            openModal("Contract Maker", "<p>Contract Maker is still coming soon for private chats.</p>");
        } else {
            openModal("AI Summary", "<p>AI summaries will be enabled after message history is connected more deeply.</p>");
        }
    });

    if (searchInChatBtn) {
        searchInChatBtn.addEventListener("click", () => {
            openComingSoonModal("Search In Chat", "In-chat search is not wired yet, but the button is now active and ready for the real search flow.");
        });
    }
    if (inputAttachBtn) {
        inputAttachBtn.addEventListener("click", () => {
            if (chatFileInput) {
                chatFileInput.click();
            }
        });
    }
    if (emojiPickerBtn) {
        emojiPickerBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            if (!emojiPickerPanel) {
                return;
            }
            emojiPickerPanel.hidden = !emojiPickerPanel.hidden;
            if (!emojiPickerPanel.hidden) {
                chatInput.focus();
            }
        });
    }
    if (chatFileInput) {
        chatFileInput.addEventListener("change", () => {
            const [file] = chatFileInput.files || [];
            if (!file) {
                return;
            }
            const messageType = (file.type || "").startsWith("image/") ? "image" : "file";
            sendMediaMessage(file, messageType);
        });
    }
    if (messagesStream) {
        messagesStream.addEventListener("click", (event) => {
            const toggleButton = event.target.closest("[data-message-menu-toggle]");
            if (toggleButton) {
                const menuId = toggleButton.dataset.messageMenuToggle;
                const menu = messagesStream.querySelector(`[data-message-menu="${menuId}"]`);
                const shouldOpen = menu && !menu.classList.contains("is-open");
                closeMessageMenus();
                if (menu && shouldOpen) {
                    menu.classList.add("is-open");
                }
                return;
            }

            const actionButton = event.target.closest("[data-message-action]");
            if (!actionButton) {
                return;
            }

            const messageId = actionButton.dataset.messageId;
            const action = actionButton.dataset.messageAction;
            const conversation = activeConversation();
            if (!messageId || !action || !conversation) {
                return;
            }

            const message = conversation.messages.find((item) => item.id === messageId);
            if (!message) {
                return;
            }

            closeMessageMenus();

            if (action === "react") {
                openModal(
                    "React to message",
                    `
                        <div class="message-react-picker">
                            <button class="message-react-option" type="button" data-picker-reaction="thumbs_up" data-message-id="${escapeHtml(messageId)}">👍</button>
                            <button class="message-react-option" type="button" data-picker-reaction="fire" data-message-id="${escapeHtml(messageId)}">🔥</button>
                        </div>
                    `
                );
                modalBody.querySelectorAll("[data-picker-reaction]").forEach((button) => {
                    button.addEventListener("click", () => {
                        const reaction = button.dataset.pickerReaction;
                        fetch(`/messages/reactions/${messageId}/${reaction}/`, {
                            method: "POST",
                            headers: {
                                "X-CSRFToken": csrftoken,
                            },
                        })
                            .then(async (response) => {
                                const data = await response.json();
                                return { ok: response.ok, data };
                            })
                            .then((result) => {
                                if (!result.ok || !result.data.ok) {
                                    showMessagingError((result.data && result.data.error) || "We could not react to this message right now.", "Reaction error");
                                    return;
                                }
                                message.reaction_counts = result.data.reaction_counts || { thumbs_up: 0, fire: 0 };
                                message.viewer_reactions = result.data.viewer_reactions || [];
                                closeModal();
                            })
                            .catch(() => {
                                showMessagingError("We could not react to this message right now.", "Reaction error");
                            });
                    });
                });
                return;
            }

            if (action === "delete") {
                openModal(
                    "Delete message",
                    "<p>This will remove this message from the conversation.</p>",
                    `
                        <button class="panel-btn ghost" id="cancelDeleteMessageBtn" type="button">Cancel</button>
                        <button class="panel-btn danger" id="confirmDeleteMessageBtn" type="button">Delete Message</button>
                    `
                );
                const cancelDeleteMessage = document.getElementById("cancelDeleteMessageBtn");
                const confirmDeleteMessage = document.getElementById("confirmDeleteMessageBtn");
                if (cancelDeleteMessage) cancelDeleteMessage.addEventListener("click", closeModal);
                if (confirmDeleteMessage) {
                    confirmDeleteMessage.addEventListener("click", () => {
                        fetch(`/messages/${messageId}/delete-message/`, {
                            method: "POST",
                            headers: {
                                "X-CSRFToken": csrftoken,
                            },
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
                                conversation.messages = conversation.messages.filter((item) => item.id !== result.data.message_id);
                                conversation.shared_files = (conversation.shared_files || []).filter((item) => item.id !== result.data.message_id);
                                conversation.preview = result.data.last_message_preview || "Start the conversation";
                                conversation.time = result.data.last_message_time || "New";
                                closeModal();
                                renderAll();
                            })
                            .catch(() => {
                                showMessagingError("We could not delete this message right now.", "Delete message");
                            });
                    });
                }
                return;
            }

            if (action === "report") {
                openModal(
                    "Report message",
                    `
                        <label class="modal-label" for="reportMessageReasonSelect">Reason</label>
                        <select class="modal-select" id="reportMessageReasonSelect">
                            <option value="">Select a reason</option>
                            <option value="Spam or scam">Spam or scam</option>
                            <option value="Harassment or abuse">Harassment or abuse</option>
                            <option value="Fake or misleading content">Fake or misleading content</option>
                            <option value="Inappropriate content">Inappropriate content</option>
                            <option value="Other">Other</option>
                        </select>
                        <div id="reportMessageOtherWrap" hidden>
                            <label class="modal-label" for="reportMessageOther">Tell us more</label>
                            <textarea class="modal-select modal-textarea" id="reportMessageOther" rows="4" placeholder="What went wrong?"></textarea>
                        </div>
                    `,
                    `
                        <button class="panel-btn ghost" id="cancelReportMessageBtn" type="button">Cancel</button>
                        <button class="panel-btn" id="submitReportMessageBtn" type="button">Send Report</button>
                    `
                );
                const cancelReportMessage = document.getElementById("cancelReportMessageBtn");
                const reasonSelect = document.getElementById("reportMessageReasonSelect");
                const otherWrap = document.getElementById("reportMessageOtherWrap");
                const submitReportMessage = document.getElementById("submitReportMessageBtn");
                if (cancelReportMessage) cancelReportMessage.addEventListener("click", closeModal);
                if (reasonSelect && otherWrap) {
                    reasonSelect.addEventListener("change", () => {
                        otherWrap.hidden = reasonSelect.value !== "Other";
                    });
                }
                if (submitReportMessage) {
                    submitReportMessage.addEventListener("click", () => {
                        const reason = reasonSelect ? reasonSelect.value : "";
                        const otherReason = document.getElementById("reportMessageOther");
                        const body = new URLSearchParams();
                        body.append("report_reason", reason);
                        body.append("report_reason_other", otherReason ? otherReason.value.trim() : "");
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
                                openModal("Report sent", `<p>${result.data.message}</p>`);
                            })
                            .catch(() => {
                                showMessagingError("We could not send your report right now.", "Report message");
                            });
                    });
                }
            }
        });
    }
    if (voiceRecordBtn) {
        voiceRecordBtn.addEventListener("click", toggleVoiceRecording);
    }
    document.getElementById("videoCallBtn").addEventListener("click", () => openModal("Video Call", "<p>Video calling is not wired yet, but the control is now active for the future call flow.</p>"));
    document.getElementById("createAgreementBtn").addEventListener("click", () => openModal("Contract Maker", "<p>Contract Maker is still coming soon for private chats.</p>"));
    const railContactsBtn = document.getElementById("railContactsBtn");
    const railGroupsBtn = document.getElementById("railGroupsBtn");
    if (railContactsBtn) {
        railContactsBtn.addEventListener("click", () => openModal("Contacts", "<p>Contacts directory will be available in the next release.</p>"));
    }
    if (railGroupsBtn) {
        railGroupsBtn.addEventListener("click", () => {
            activeTab = "groups";
            renderAll();
        });
    }
    if (createGroupBtn) {
        createGroupBtn.addEventListener("click", () => {
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
                                <input type="checkbox" value="${friend.id}">
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
            if (cancelButton) cancelButton.addEventListener("click", closeModal);
            if (confirmButton) {
                confirmButton.addEventListener("click", () => {
                    const groupNameInput = document.getElementById("groupNameInput");
                    const selectedParticipantIds = Array.from(
                        document.querySelectorAll("#groupFriendPicker input[type='checkbox']:checked")
                    ).map((input) => input.value);
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
                            window.location.href = `/messages/?conversation=${result.data.conversation_id}`;
                        })
                        .catch(() => {
                            showMessagingError("We could not create that group right now.", "Create Group");
                        });
                });
            }
        });
    }

    document.getElementById("blockUserBtn").addEventListener("click", () => {
        const conversation = activeConversation();
        if (!conversation || !conversation.partner_id) {
            openModal("Block User", "<p>Select a conversation first.</p>");
            return;
        }
        const shouldBlock = !conversation.blocked_by_current_user;
        fetch(`/users/${conversation.partner_id}/block/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrftoken,
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then((response) => response.json())
            .then((data) => {
                if (!data.ok) {
                    openModal("Block User", `<p>${data.error || "Unable to update block status right now."}</p>`);
                    return;
                }
                conversation.blocked_by_current_user = data.blocked;
                renderChat();
                openModal(
                    data.blocked ? "User blocked" : "User unblocked",
                    `<p>${data.message}</p>`
                );
                if (shouldBlock) {
                    chatInput.value = "";
                    sendBtn.disabled = true;
                }
            })
            .catch(() => {
                openModal("Block User", "<p>Unable to update block status right now.</p>");
            });
    });

    document.getElementById("reportUserBtn").addEventListener("click", () => {
        const conversation = activeConversation();
        if (!conversation) {
            openModal("Report User", "<p>Select a conversation first.</p>");
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
                    <textarea class="modal-select modal-textarea" id="reportReasonOther" rows="4" placeholder="What went wrong?"></textarea>
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
        if (cancelButton) cancelButton.addEventListener("click", closeModal);
        if (reasonSelect && otherWrap) {
            reasonSelect.addEventListener("change", () => {
                otherWrap.hidden = reasonSelect.value !== "Other";
            });
        }
        if (submitButton) {
            submitButton.addEventListener("click", () => {
                const reason = reasonSelect ? reasonSelect.value : "";
                const otherReason = document.getElementById("reportReasonOther");
                const blockToggle = document.getElementById("reportBlockToggle");
                const body = new URLSearchParams();
                body.append("report_reason", reason);
                body.append("report_reason_other", otherReason ? otherReason.value.trim() : "");
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
                            conversation.blocked_by_current_user = true;
                        }
                        renderChat();
                        openModal("Report sent", `<p>${result.data.message}</p>`);
                    })
                    .catch(() => {
                        showMessagingError("We could not send your report right now.", "Report User");
                    });
            });
        }
    });
    if (panelMoreMenu) {
        panelMoreMenu.addEventListener("click", (event) => {
            event.stopPropagation();
            const button = event.target.closest("button");
            if (!button) return;
            panelMoreMenu.classList.remove("is-open");
            if (button.dataset.action === "create-group" && createGroupBtn) {
                createGroupBtn.click();
            }
        });
    }

    document.getElementById("deleteConversationBtn").addEventListener("click", () => {
        const conversation = activeConversation();
        if (!conversation) {
            openModal("Delete Conversation", "<p>Select a conversation first.</p>");
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
        const cancelDelete = document.getElementById("cancelDeleteConversationBtn");
        const confirmDelete = document.getElementById("confirmDeleteConversationBtn");
        if (cancelDelete) cancelDelete.addEventListener("click", closeModal);
        if (confirmDelete) {
            confirmDelete.addEventListener("click", () => {
                fetch(`/messages/${conversation.id}/delete/`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrftoken,
                    },
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
                        handleConversationDeleted({ conversation_id: conversation.id });
                    })
                    .catch(() => {
                        showMessagingError("We could not delete this conversation right now.", "Delete Conversation");
                    });
            });
        }
    });

    document.getElementById("closeModalBtn").addEventListener("click", closeModal);
    modalBackdrop.addEventListener("click", (event) => {
        if (event.target === modalBackdrop) {
            closeModal();
        }
    });

    chatInput.addEventListener("input", () => {
        sendBtn.disabled = chatInput.value.trim().length === 0;
    });
    sendBtn.addEventListener("click", handleSend);
    chatInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            handleSend();
        }
    });
    if (muteNotificationsToggle) {
        muteNotificationsToggle.addEventListener("change", () => {
            const conversation = activeConversation();
            if (!conversation) {
                muteNotificationsToggle.checked = false;
                return;
            }
            fetch(`/messages/${conversation.id}/mute/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrftoken,
                },
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
                    muteNotificationsToggle.checked = !!result.data.mute_notifications;
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
                headers: {
                    "X-CSRFToken": csrftoken,
                },
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
                    conversation.pinned = result.data.recording_mode === "ephemeral" ? result.data.banner : "";
                    recordingModeToggle.checked = result.data.recording_mode !== "ephemeral";
                    renderChat();
                })
                .catch(() => {
                    recordingModeToggle.checked = !recordingModeToggle.checked;
                    showMessagingError("We could not update recording settings right now.", "Record chat history");
                });
        });
    }
    if (notifBell && notifPanel) {
        notifBell.addEventListener("click", (event) => {
            event.stopPropagation();
            notifPanel.classList.toggle("is-open");
        });
        document.addEventListener("click", (event) => {
            if (!notifPanel.contains(event.target) && !notifBell.contains(event.target)) {
                notifPanel.classList.remove("is-open");
            }
        });
    }

    connectSocket();
    renderEmojiPicker();
    renderAll();
    if (initialMessageError) {
        openModal("Messaging blocked", `<p>${initialMessageError}</p>`);
    }
})();
