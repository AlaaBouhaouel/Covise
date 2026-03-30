(function () {
    const conversations = JSON.parse(
        document.getElementById("conversation-data").textContent
    );
    const conversationRequests = JSON.parse(
        document.getElementById("conversation-request-data").textContent
    );
    const activeConversationValue = JSON.parse(
        document.getElementById("active-conversation-id").textContent
    );
    const currentUserId = JSON.parse(
        document.getElementById("current-user-id").textContent
    );

    const groupConversations = [];
    const app = document.getElementById("messagesApp");
    const directList = document.getElementById("directList");
    const groupsList = document.getElementById("groupsList");
    const searchInput = document.getElementById("conversationSearch");
    const directTabBtn = document.getElementById("directTabBtn");
    const groupsTabBtn = document.getElementById("groupsTabBtn");
    const messagesStream = document.getElementById("messagesStream");
    const sendBtn = document.getElementById("sendBtn");
    const chatName = document.getElementById("chatName");
    const chatStatus = document.getElementById("chatStatus");
    const chatStatusDot = document.getElementById("chatStatusDot");
    const chatAvatar = document.getElementById("chatAvatar");
    const chatMatchPill = document.getElementById("chatMatchPill");
    const pinnedText = document.getElementById("pinnedText");
    const detailsName = document.getElementById("detailsName");
    const detailsPersonName = document.getElementById("detailsPersonName");
    const detailsAvatar = document.getElementById("detailsAvatar");
    const detailsMatchPill = document.getElementById("detailsMatchPill");
    const detailsMatchedOn = document.getElementById("detailsMatchedOn");
    const detailsUserType = document.getElementById("detailsUserType");
    const detailsIndustry = document.getElementById("detailsIndustry");
    const detailsStage = document.getElementById("detailsStage");
    const detailsMutual = document.getElementById("detailsMutual");
    const convictionFill = document.getElementById("convictionFill");
    const convictionValue = document.getElementById("convictionValue");
    const requestsToggle = document.getElementById("requestsToggle");
    const requestsList = document.getElementById("requestsList");
    const moreMenuBtn = document.getElementById("moreMenuBtn");
    const moreMenu = document.getElementById("moreMenu");
    const modalBackdrop = document.getElementById("modalBackdrop");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");
    const modalFoot = document.getElementById("modalFoot");
    const chatInput = document.getElementById("chatInput");
    const searchInChatBtn = document.getElementById("searchInChatBtn");
    const attachFileBtn = document.getElementById("attachFileBtn");
    const inputAttachBtn = document.getElementById("inputAttachBtn");
    const emojiPickerBtn = document.getElementById("emojiPickerBtn");

    let activeTab = "direct";
    let activeConversationId = activeConversationValue || (conversations[0] ? conversations[0].id : "");
    let chatSocket = null;

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

    function activeConversation() {
        return conversations.find((conversation) => conversation.id === activeConversationId) || null;
    }

    function ensureActiveConversation() {
        if (!activeConversationId && conversations[0]) {
            activeConversationId = conversations[0].id;
        }
        if (activeConversationId && activeConversation()) {
            return;
        }
        activeConversationId = conversations[0] ? conversations[0].id : "";
    }

    function connectSocket() {
        if (!activeConversationId) {
            return;
        }

        if (chatSocket) {
            chatSocket.close();
        }

        chatSocket = new WebSocket(
            "ws://" + window.location.host + "/ws/messages/" + activeConversationId + "/"
        );

        chatSocket.onmessage = function (event) {
            const data = JSON.parse(event.data);
            const conversation = conversations.find((item) => item.id === data.conversation_id);

            if (!conversation) {
                return;
            }

            conversation.messages.push({
                id: data.message_id,
                sender_id: data.sender_id,
                sender_name: data.sender_name,
                text: data.message,
                created_at: data.created_at,
            });

            conversation.preview = data.message;
            conversation.time = "Now";
            if (conversation.id === activeConversationId) {
                conversation.unread = 0;
            } else {
                conversation.unread += 1;
            }

            renderAll();
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

    function renderRequests() {
        const requestCount = conversationRequests.length;
        const label = requestCount === 1 ? "1 Message Request" : `${requestCount} Message Requests`;
        requestsToggle.querySelector("span").textContent = label;
        requestsList.innerHTML = "";

        if (!requestCount) {
            requestsList.innerHTML = '<article class="request-item"><div><h3>No pending requests</h3><p>Send a request from someone&apos;s public profile to start a private chat after they accept.</p></div></article>';
            return;
        }

        conversationRequests.forEach((requestItem) => {
            const element = document.createElement("article");
            element.className = "request-item";
            let actionsHtml = '<div class="request-actions">';
            if (requestItem.is_incoming) {
                actionsHtml += `<button class="accept" type="button" data-request-id="${requestItem.id}" data-action="accept">Accept</button>`;
                actionsHtml += `<button class="decline" type="button" data-request-id="${requestItem.id}" data-action="decline">Decline</button>`;
            } else {
                actionsHtml += '<button class="accept" type="button" disabled>Pending</button>';
            }
            actionsHtml += "</div>";
            element.innerHTML = `
                <div><h3>${requestItem.name}</h3><p>${requestItem.description}</p></div>
                ${actionsHtml}
            `;

            element.querySelectorAll("[data-request-id]").forEach((button) => {
                button.addEventListener("click", () => {
                    fetch(`/messages/requests/${requestItem.id}/${button.dataset.action}/`, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": csrftoken,
                        },
                    })
                        .then((response) => response.json())
                        .then((data) => {
                            if (!data.ok) {
                                return;
                            }
                            if (data.conversation_id) {
                                window.location.href = `/messages/?conversation=${data.conversation_id}`;
                                return;
                            }
                            window.location.reload();
                        });
                });
            });

            requestsList.appendChild(element);
        });
    }

    function renderLists() {
        const query = searchInput.value.trim().toLowerCase();
        directList.innerHTML = "";
        groupsList.innerHTML = "";

        conversations
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
                        <div class="avatar">${conversation.avatar}</div>
                    </div>
                    <div class="conv-main">
                        <div class="conv-head"><h3>${conversation.name}</h3><span>${conversation.time}</span></div>
                        <p>${conversation.preview}</p>
                        <div class="conv-foot">
                            <span class="match-pill subtle">${conversation.match}</span>
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

        if (!conversations.length) {
            directList.innerHTML = '<div class="request-item"><div><h3>No conversations yet</h3><p>Open a public profile and press "Request Private Chat" to start one.</p></div></div>';
        }

        groupConversations.forEach((group) => {
            const element = document.createElement("button");
            element.type = "button";
            element.className = "conv-item group-item";
            element.innerHTML = `
                <div class="avatar">${group.avatar}</div>
                <div class="conv-main">
                    <div class="conv-head"><h3>${group.name}</h3><span>${group.time}</span></div>
                    <p>${group.preview}</p>
                    <div class="conv-foot"><span class="match-pill subtle">${group.members} members</span></div>
                </div>`;
            groupsList.appendChild(element);
        });

        if (!groupConversations.length) {
            groupsList.innerHTML = '<div class="request-item"><div><h3>No groups yet</h3><p>Group conversations are not enabled yet.</p></div></div>';
        }

        directList.classList.toggle("is-hidden", activeTab !== "direct");
        groupsList.classList.toggle("is-hidden", activeTab !== "groups");
        directTabBtn.classList.toggle("is-active", activeTab === "direct");
        groupsTabBtn.classList.toggle("is-active", activeTab === "groups");
    }

    function renderChat() {
        const conversation = activeConversation();
        messagesStream.innerHTML = "";

        if (!conversation) {
            chatName.textContent = "Messages";
            chatStatus.textContent = "Choose a conversation to start chatting";
            chatAvatar.textContent = "C";
            chatMatchPill.textContent = "Private conversation";
            pinnedText.textContent = "Start a private chat from a public profile.";
            detailsName.textContent = "No conversation selected";
            detailsPersonName.textContent = "No conversation selected";
            detailsAvatar.textContent = "C";
            detailsMatchPill.textContent = "Private conversation";
            detailsMatchedOn.textContent = "";
            detailsUserType.textContent = "";
            detailsIndustry.textContent = "";
            detailsStage.textContent = "";
            detailsMutual.textContent = "0";
            convictionFill.style.width = "0%";
            convictionValue.textContent = "0/100";
            return;
        }

        chatName.textContent = conversation.name;
        chatStatus.textContent = conversation.status;
        if (chatStatusDot) {
            chatStatus.prepend(chatStatusDot);
            chatStatusDot.classList.add("offline");
        }
        chatAvatar.textContent = conversation.avatar;
        chatMatchPill.textContent = conversation.match;
        pinnedText.textContent = conversation.pinned || "Private chat with this member.";

        detailsName.textContent = conversation.name;
        detailsPersonName.textContent = conversation.name;
        detailsAvatar.textContent = conversation.avatar;
        detailsMatchPill.textContent = conversation.match;
        detailsMatchedOn.textContent = conversation.matchedOn;
        detailsUserType.textContent = conversation.userType;
        detailsIndustry.textContent = conversation.industry;
        detailsStage.textContent = conversation.stage;
        detailsMutual.textContent = conversation.mutual;
        convictionFill.style.width = "0%";
        convictionValue.textContent = "N/A";

        conversation.messages.forEach((message) => {
            const row = document.createElement("article");
            const isMine = message.sender_id === currentUserId;
            row.className = "msg " + (isMine ? "outgoing" : "incoming");
            row.innerHTML = `<div class="bubble">${message.text}</div><div class="msg-meta"><span>${formatMessageTime(message.created_at)}</span>${isMine ? receiptHTML(message.receipt || "sent") : ""}</div>`;
            messagesStream.appendChild(row);
        });
        messagesStream.scrollTop = messagesStream.scrollHeight;
    }

    function renderAll() {
        ensureActiveConversation();
        renderRequests();
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

    function handleSend() {
        const text = chatInput.value.trim();

        if (!text || !chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
            return;
        }

        chatSocket.send(JSON.stringify({
            message: text,
        }));

        chatInput.value = "";
        sendBtn.disabled = true;
    }

    function openComingSoonModal(title, body) {
        openModal(title, `<p>${body}</p>`);
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
    requestsToggle.addEventListener("click", () => {
        requestsList.classList.toggle("is-open");
        requestsToggle.classList.toggle("is-open");
    });

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

    moreMenuBtn.addEventListener("click", () => moreMenu.classList.toggle("is-open"));
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".menu-wrap")) {
            moreMenu.classList.remove("is-open");
        }
    });
    moreMenu.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button) return;
        moreMenu.classList.remove("is-open");
        if (button.dataset.action === "contract") {
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
    if (attachFileBtn) {
        attachFileBtn.addEventListener("click", () => {
            openComingSoonModal("Attach File", "File sharing is not wired yet, but this is where upload support will connect.");
        });
    }
    if (inputAttachBtn) {
        inputAttachBtn.addEventListener("click", () => {
            openComingSoonModal("Attach File", "File sharing from the input bar is not wired yet, but the control is active now.");
        });
    }
    if (emojiPickerBtn) {
        emojiPickerBtn.addEventListener("click", () => {
            openComingSoonModal("Emoji Picker", "Emoji reactions and the picker are not wired yet, but this button is now active.");
        });
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

    document.getElementById("removeContactBtn").addEventListener("click", () => {
        openModal("Remove Contact", "<p>Removing a contact is not connected yet, but this action is now enabled and ready for the contact-management flow.</p>");
    });
    document.getElementById("blockUserBtn").addEventListener("click", () => {
        openModal("Block User", "<p>Blocking is not connected yet for live chat conversations.</p>");
    });

    document.getElementById("reportUserBtn").addEventListener("click", () => {
        openModal("Report User", "<p>Reporting is not connected yet for live chat conversations.</p>");
    });

    document.getElementById("clearChatBtn").addEventListener("click", () => {
        openModal("Clear Chat History", "<p>Chat history deletion is not connected yet.</p>");
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

    connectSocket();
    renderAll();
})();
