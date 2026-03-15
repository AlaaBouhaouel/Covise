(function () {
    const directConversations = [
        {
            id: "leena",
            name: "Leena Al-Sabah",
            avatar: "L",
            avatarColor: "var(--avatar-blue)",
            preview: "I can handle product and early technical hiring if we align on scope.",
            time: "2h ago",
            unread: 3,
            online: true,
            match: "Tech Co-founder Match",
            status: "Active now",
            matchedOn: "March 8, 2026",
            userType: "Specialist / Operator",
            industry: "Fintech / B2B SaaS",
            stage: "MVP built",
            conviction: 84,
            mutual: 7,
            pinned: "Pinned: Review the GCC launch checklist before our call.",
            messages: [
                { type: "separator", label: "March 10" },
                { from: "them", text: "Great connecting on CoVise. I reviewed your one-liner for the SME treasury platform.", time: "10:11 AM" },
                { from: "me", text: "Thanks Leena. We are focused on automating invoice financing workflows for GCC distributors.", time: "10:13 AM", receipt: "sent" },
                { from: "them", text: "That fits my background. I led product at a payments startup in Kuwait for 3 years.", time: "10:16 AM" },
                { type: "separator", label: "Yesterday" },
                { from: "me", text: "Would you be open to leading product while I stay on GTM and partnerships?", time: "4:08 PM", receipt: "delivered" },
                { from: "them", text: "Yes, if we agree on decision boundaries and weekly execution cadence.", time: "4:12 PM" },
                { from: "me", text: "Fair. I propose weekly sprint planning on Mondays and investor update every two weeks.", time: "4:15 PM", receipt: "delivered" },
                { from: "them", text: "Works for me. Also we should validate with 5 pilot CFOs in Riyadh and Dubai.", time: "4:17 PM" },
                { type: "separator", label: "Today" },
                { from: "me", text: "I already have intros to 3 CFOs in logistics and wholesale. We can run discovery this week.", time: "9:42 AM", receipt: "seen" },
                { from: "them", text: "Perfect. If the pain is strong, I can draft the MVP PRD by Sunday.", time: "9:44 AM" },
                { from: "me", text: "Let us do a call tonight at 8 PM KSA and lock milestones for the next 30 days.", time: "9:46 AM", receipt: "seen" },
                { from: "them", text: "Confirmed. I will send a proposed product timeline before the call.", time: "9:49 AM" }
            ]
        },
        { id: "fahad", name: "Fahad Al-Qahtani", avatar: "F", avatarColor: "var(--avatar-green)", preview: "I have a shortlist of enterprise leads in Dammam ready for pilot.", time: "Yesterday", unread: 1, online: false, match: "Sales Operator Match", status: "Last seen 2h ago", matchedOn: "March 5, 2026", userType: "Specialist / Operator", industry: "Logistics / Supply Chain", stage: "Early revenue", conviction: 79, mutual: 4, pinned: "Pinned: Share pilot pricing model.", messages: [] },
        { id: "nora", name: "Nora Al-Mansoori", avatar: "N", avatarColor: "var(--avatar-purple)", preview: "Can we review the UAE licensing timeline before next week?", time: "Yesterday", unread: 0, online: true, match: "GCC Expansion Match", status: "Active now", matchedOn: "March 2, 2026", userType: "Founder", industry: "Legal / Regtech", stage: "MVP built", conviction: 82, mutual: 5, pinned: "Pinned: UAE entity setup checklist.", messages: [] },
        { id: "abdullah", name: "Abdullah Al-Otaibi", avatar: "A", avatarColor: "var(--avatar-amber)", preview: "I can support the backend architecture and security review.", time: "2d ago", unread: 2, online: false, match: "Technical Architect Match", status: "Last seen 1d ago", matchedOn: "March 1, 2026", userType: "Specialist / Operator", industry: "Cybersecurity", stage: "Idea", conviction: 76, mutual: 3, pinned: "Pinned: API security architecture notes.", messages: [] },
        { id: "mariam", name: "Mariam Al-Hajri", avatar: "M", avatarColor: "var(--avatar-pink)", preview: "Investor intro deck looks good, only financial assumptions need revision.", time: "3d ago", unread: 0, online: true, match: "Investor Readiness Match", status: "Active now", matchedOn: "February 28, 2026", userType: "Investor", industry: "Fintech", stage: "Early revenue", conviction: 88, mutual: 11, pinned: "Pinned: Final investor deck v3.", messages: [] },
        { id: "salem", name: "Salem Al-Rumaithi", avatar: "S", avatarColor: "var(--avatar-cyan)", preview: "Let us align on founder vesting terms before signing.", time: "4d ago", unread: 0, online: false, match: "Legal Structuring Match", status: "Last seen 3d ago", matchedOn: "February 26, 2026", userType: "Founder", industry: "Marketplace", stage: "MVP built", conviction: 81, mutual: 6, pinned: "Pinned: Founder vesting clause draft.", messages: [] }
    ];

    const groupConversations = [
        { name: "Riyadh AI Builders", members: 8, preview: "New benchmark results posted for the matching model.", time: "1h ago", avatar: "R" },
        { name: "GCC Fintech Founders", members: 14, preview: "Who can share a compliance advisor in Bahrain?", time: "Yesterday", avatar: "G" }
    ];

    const app = document.getElementById("messagesApp");
    const directList = document.getElementById("directList");
    const groupsList = document.getElementById("groupsList");
    const searchInput = document.getElementById("conversationSearch");
    const directTabBtn = document.getElementById("directTabBtn");
    const groupsTabBtn = document.getElementById("groupsTabBtn");
    const messagesStream = document.getElementById("messagesStream");
    const chatInput = document.getElementById("chatInput");
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

    let activeTab = "direct";
    let activeConversationId = directConversations[0].id;

    function receiptHTML(receipt) {
        if (receipt === "sent") return '<span class="receipt">✓</span>';
        if (receipt === "delivered") return '<span class="receipt">✓✓</span>';
        if (receipt === "seen") return '<span class="receipt seen">✓✓</span>';
        return "";
    }

    function activeConversation() {
        return directConversations.find((c) => c.id === activeConversationId) || directConversations[0];
    }

    function renderLists() {
        const q = searchInput.value.trim().toLowerCase();
        directList.innerHTML = "";
        groupsList.innerHTML = "";

        directConversations
            .filter((c) => (c.name + " " + c.preview + " " + c.match).toLowerCase().includes(q))
            .forEach((c) => {
                const el = document.createElement("button");
                el.type = "button";
                el.className = "conv-item" + (activeTab === "direct" && c.id === activeConversationId ? " is-active" : "");
                el.innerHTML = `
                    <div class="conv-avatar-wrap">
                        <div class="avatar" style="background:${c.avatarColor};">${c.avatar}</div>
                        ${c.online ? '<span class="online-dot"></span>' : ""}
                    </div>
                    <div class="conv-main">
                        <div class="conv-head"><h3>${c.name}</h3><span>${c.time}</span></div>
                        <p>${c.preview}</p>
                        <div class="conv-foot">
                            <span class="match-pill subtle">${c.match}</span>
                            ${c.unread ? `<span class="unread-badge">${c.unread}</span>` : ""}
                        </div>
                    </div>`;
                el.addEventListener("click", () => {
                    activeConversationId = c.id;
                    activeTab = "direct";
                    renderAll();
                    app.classList.add("mobile-chat-open");
                });
                directList.appendChild(el);
            });

        groupConversations
            .filter((g) => (g.name + " " + g.preview).toLowerCase().includes(q))
            .forEach((g) => {
                const el = document.createElement("button");
                el.type = "button";
                el.className = "conv-item group-item";
                el.innerHTML = `
                    <div class="avatar">${g.avatar}</div>
                    <div class="conv-main">
                        <div class="conv-head"><h3>${g.name}</h3><span>${g.time}</span></div>
                        <p>${g.preview}</p>
                        <div class="conv-foot"><span class="match-pill subtle">${g.members} members</span></div>
                    </div>`;
                groupsList.appendChild(el);
            });

        directList.classList.toggle("is-hidden", activeTab !== "direct");
        groupsList.classList.toggle("is-hidden", activeTab !== "groups");
        directTabBtn.classList.toggle("is-active", activeTab === "direct");
        groupsTabBtn.classList.toggle("is-active", activeTab === "groups");
    }

    function renderChat() {
        const c = activeConversation();
        chatName.textContent = c.name;
        chatStatus.textContent = c.status;
        if (chatStatusDot) {
            chatStatus.prepend(chatStatusDot);
            chatStatusDot.classList.toggle("offline", !c.online);
        }
        chatAvatar.textContent = c.avatar;
        chatAvatar.style.background = c.avatarColor;
        chatMatchPill.textContent = c.match;
        pinnedText.textContent = c.pinned;

        detailsName.textContent = c.name;
        detailsPersonName.textContent = c.name;
        detailsAvatar.textContent = c.avatar;
        detailsAvatar.style.background = c.avatarColor;
        detailsMatchPill.textContent = c.match;
        detailsMatchedOn.textContent = c.matchedOn;
        detailsUserType.textContent = c.userType;
        detailsIndustry.textContent = c.industry;
        detailsStage.textContent = c.stage;
        detailsMutual.textContent = c.mutual;
        convictionFill.style.width = c.conviction + "%";
        convictionValue.textContent = c.conviction + "/100";

        messagesStream.innerHTML = "";
        c.messages.forEach((m) => {
            if (m.type === "separator") {
                const sep = document.createElement("div");
                sep.className = "date-separator";
                sep.textContent = m.label;
                messagesStream.appendChild(sep);
                return;
            }
            const row = document.createElement("article");
            row.className = "msg " + (m.from === "me" ? "outgoing" : "incoming");
            row.innerHTML = `<div class="bubble">${m.text}</div><div class="msg-meta"><span>${m.time}</span>${m.from === "me" ? receiptHTML(m.receipt) : ""}</div>`;
            messagesStream.appendChild(row);
        });
        messagesStream.scrollTop = messagesStream.scrollHeight;
    }

    function renderAll() {
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

    function closeModal() { modalBackdrop.classList.remove("is-open"); }

    function handleSend() {
        const text = chatInput.value.trim();
        if (!text) return;
        const c = activeConversation();
        const now = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
        c.messages.push({ from: "me", text, time: now, receipt: "sent" });
        c.preview = text;
        c.time = "Now";
        c.unread = 0;
        chatInput.value = "";
        sendBtn.disabled = true;
        renderAll();
    }

    directTabBtn.addEventListener("click", () => { activeTab = "direct"; renderAll(); });
    groupsTabBtn.addEventListener("click", () => { activeTab = "groups"; renderAll(); });
    searchInput.addEventListener("input", renderAll);
    requestsToggle.addEventListener("click", () => {
        requestsList.classList.toggle("is-open");
        requestsToggle.classList.toggle("is-open");
    });

    document.getElementById("toggleDetailsBtn").addEventListener("click", () => app.classList.toggle("details-open"));
    document.getElementById("closeDetailsBtn").addEventListener("click", () => app.classList.remove("details-open"));
    document.getElementById("mobileBackBtn").addEventListener("click", () => app.classList.remove("mobile-chat-open"));
    document.getElementById("mobileCloseChat").addEventListener("click", () => app.classList.remove("mobile-chat-open"));

    document.querySelectorAll(".details-tab").forEach((btn) => {
        btn.addEventListener("click", () => {
            const tab = btn.dataset.detailsTab;
            document.querySelectorAll(".details-tab").forEach((b) => b.classList.remove("is-active"));
            document.querySelectorAll(".details-pane").forEach((p) => p.classList.remove("is-active"));
            btn.classList.add("is-active");
            document.querySelector('.details-pane[data-pane="' + tab + '"]').classList.add("is-active");
        });
    });

    moreMenuBtn.addEventListener("click", () => moreMenu.classList.toggle("is-open"));
    document.addEventListener("click", (e) => { if (!e.target.closest(".menu-wrap")) moreMenu.classList.remove("is-open"); });
    moreMenu.addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        moreMenu.classList.remove("is-open");
        if (btn.dataset.action === "contract") {
            openModal("Contract Maker", "<p>Contract Maker — Coming Soon. This feature will allow you to generate co-founder agreements directly from your conversation.</p>");
        } else {
            openModal("AI Summary", "<p>AI Summary — Coming Soon. CoVise Advisor will summarize key decisions and agreements from this conversation.</p>");
        }
    });

    document.getElementById("videoCallBtn").addEventListener("click", () => openModal("Video Call", "<p>Video calling is coming soon on CoVise messaging.</p>"));
    document.getElementById("createAgreementBtn").addEventListener("click", () => openModal("Contract Maker", "<p>Contract Maker — Coming Soon. This feature will allow you to generate co-founder agreements directly from your conversation.</p>"));
    const railContactsBtn = document.getElementById("railContactsBtn");
    const railGroupsBtn = document.getElementById("railGroupsBtn");
    if (railContactsBtn) {
        railContactsBtn.addEventListener("click", () => openModal("Contacts", "<p>Contacts directory will be available in the next release.</p>"));
    }
    if (railGroupsBtn) {
        railGroupsBtn.addEventListener("click", () => { activeTab = "groups"; renderAll(); });
    }

    document.getElementById("blockUserBtn").addEventListener("click", () => {
        openModal("Block User", "<p>Are you sure you want to block this user? They will no longer be able to message you or see your profile.</p>",
            '<button class="panel-btn ghost" id="modalOkBtn" type="button">Cancel</button><button class="panel-btn danger" id="confirmBlockBtn" type="button">Block User</button>');
        const confirm = document.getElementById("confirmBlockBtn");
        if (confirm) confirm.addEventListener("click", () => { closeModal(); openModal("User Blocked", "<p>This user has been blocked.</p>"); });
    });

    document.getElementById("reportUserBtn").addEventListener("click", () => {
        openModal("Report User",
            '<label class="modal-label" for="reportReason">Reason</label><select id="reportReason" class="modal-select"><option>Spam</option><option>Inappropriate behavior</option><option>Fake profile</option><option>Other</option></select>',
            '<button class="panel-btn ghost" id="modalOkBtn" type="button">Cancel</button><button class="panel-btn" id="submitReportBtn" type="button">Submit</button>');
        const submit = document.getElementById("submitReportBtn");
        if (submit) submit.addEventListener("click", () => { closeModal(); openModal("Report Submitted", "<p>Thanks. Our trust and safety team will review your report.</p>"); });
    });

    document.getElementById("clearChatBtn").addEventListener("click", () => {
        openModal("Clear Chat History", "<p>Are you sure you want to clear this conversation history?</p>",
            '<button class="panel-btn ghost" id="modalOkBtn" type="button">Cancel</button><button class="panel-btn danger" id="confirmClearBtn" type="button">Clear</button>');
        const clear = document.getElementById("confirmClearBtn");
        if (clear) clear.addEventListener("click", () => { activeConversation().messages = []; closeModal(); renderChat(); });
    });

    document.getElementById("closeModalBtn").addEventListener("click", closeModal);
    modalBackdrop.addEventListener("click", (e) => { if (e.target === modalBackdrop) closeModal(); });

    chatInput.addEventListener("input", () => { sendBtn.disabled = chatInput.value.trim().length === 0; });
    sendBtn.addEventListener("click", handleSend);
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    renderAll();
})();
