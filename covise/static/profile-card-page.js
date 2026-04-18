(function () {
    var downloadBtn = document.getElementById("downloadCardBtn");
    var shareBtn = document.getElementById("shareCardBtn");
    var copyBtn = document.getElementById("copyCardLinkBtn");
    var statusEl = document.getElementById("cardStatus");

    var elements = {
        avatar: document.getElementById("card-avatar"),
        name: document.getElementById("card-name"),
        role: document.getElementById("card-role"),
        location: document.getElementById("card-location"),
        meta: document.getElementById("card-meta"),
        cofounderBadge: document.getElementById("card-cofounder-badge"),
        score: document.getElementById("card-score"),
        scoreFill: document.getElementById("card-score-fill"),
        stage: document.getElementById("card-stage"),
        commitment: document.getElementById("card-commitment"),
        industry: document.getElementById("card-industry"),
        market: document.getElementById("card-market"),
        skills: document.getElementById("card-skills"),
        lookingFor: document.getElementById("card-looking-for"),
        about: document.getElementById("card-about")
    };

    if (!downloadBtn || !shareBtn || !copyBtn || !statusEl || !elements.name) {
        return;
    }

    var cardDataElement = document.getElementById("profile-card-data");
    var cardData = cardDataElement ? JSON.parse(cardDataElement.textContent) : {
        avatar_initials: elements.avatar ? elements.avatar.textContent.trim() : "CV",
        display_name: elements.name ? elements.name.textContent.trim() : "CoVise User",
        role: elements.role ? elements.role.textContent.trim() : "Founder",
        location: elements.location ? elements.location.textContent.trim() : "Location not added yet",
        role_location: elements.meta ? elements.meta.textContent.trim() : "PROFILE IN PROGRESS",
        score: elements.score ? parseInt(elements.score.textContent, 10) || 0 : 0,
        stage: elements.stage ? elements.stage.textContent.trim() : "Profile in progress",
        commitment: elements.commitment ? elements.commitment.textContent.trim() : "Flexible",
        industry: elements.industry ? elements.industry.textContent.trim() : "Not shared yet",
        market: elements.market ? elements.market.textContent.trim() : "Location not added yet",
        skills: Array.from(elements.skills ? elements.skills.querySelectorAll(".share-chip") : []).map(function (chip) {
            return chip.textContent.trim();
        }),
        looking_for: Array.from(elements.lookingFor ? elements.lookingFor.querySelectorAll(".share-chip") : []).map(function (chip) {
            return chip.textContent.trim();
        }),
        about: elements.about ? elements.about.textContent.trim() : "",
        show_cofounder_badge: elements.cofounderBadge ? !elements.cofounderBadge.hasAttribute("hidden") : false,
        share_url: window.location.href
    };
    var shareUrl = cardData.share_url ? new URL(cardData.share_url, window.location.origin).toString() : window.location.href;

    function setStatus(message) {
        statusEl.textContent = message;
    }

    function renderChips(container, chips, extraClass) {
        if (!container) {
            return;
        }
        container.innerHTML = "";
        (Array.isArray(chips) ? chips : []).forEach(function (chip, index) {
            var span = document.createElement("span");
            var classes = ["share-chip"];
            if (extraClass) {
                classes.push(extraClass);
            }
            if (index === 0) {
                classes.push("active");
            }
            span.className = classes.join(" ");
            span.textContent = chip;
            container.appendChild(span);
        });
    }

    function paintHtmlCard() {
        if (elements.avatar) {
            elements.avatar.textContent = cardData.avatar_initials;
        }
        if (elements.name) {
            elements.name.textContent = cardData.display_name;
        }
        if (elements.role) {
            elements.role.textContent = cardData.role;
        }
        if (elements.location) {
            elements.location.textContent = cardData.location;
        }
        if (elements.meta) {
            elements.meta.textContent = cardData.role_location;
        }
        if (elements.score) {
            elements.score.textContent = String(cardData.score);
        }
        if (elements.scoreFill) {
            elements.scoreFill.style.width = Math.max(0, Math.min(cardData.score, 100)) + "%";
        }
        if (elements.about) {
            elements.about.textContent = cardData.about;
        }
        if (elements.cofounderBadge) {
            elements.cofounderBadge.hidden = !cardData.show_cofounder_badge;
        }
        if (elements.stage) {
            elements.stage.textContent = cardData.stage;
        }
        if (elements.commitment) {
            elements.commitment.textContent = cardData.commitment;
        }
        if (elements.industry) {
            elements.industry.textContent = cardData.industry;
        }
        if (elements.market) {
            elements.market.textContent = cardData.market;
        }
        renderChips(elements.skills, cardData.skills);
        renderChips(elements.lookingFor, cardData.looking_for, "share-chip-accent");
    }

    function inlineStyles(sourceNode, targetNode) {
        if (!(sourceNode instanceof Element) || !(targetNode instanceof Element)) {
            return;
        }

        var computed = window.getComputedStyle(sourceNode);
        for (var index = 0; index < computed.length; index += 1) {
            var property = computed[index];
            targetNode.style.setProperty(
                property,
                computed.getPropertyValue(property),
                computed.getPropertyPriority(property)
            );
        }

        if (sourceNode instanceof SVGElement) {
            targetNode.setAttribute("xmlns", "http://www.w3.org/2000/svg");
        }

        if (sourceNode.tagName === "IMG" && sourceNode.currentSrc) {
            targetNode.setAttribute("src", sourceNode.currentSrc);
        }

        if (sourceNode.tagName === "INPUT" || sourceNode.tagName === "TEXTAREA") {
            targetNode.setAttribute("value", sourceNode.value);
        }

        var sourceChildren = sourceNode.children || [];
        var targetChildren = targetNode.children || [];
        for (var childIndex = 0; childIndex < sourceChildren.length; childIndex += 1) {
            inlineStyles(sourceChildren[childIndex], targetChildren[childIndex]);
        }
    }

    function escapeXml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function canvasToBlob(canvas) {
        return new Promise(function (resolve) {
            canvas.toBlob(function (blob) {
                resolve(blob);
            }, "image/png");
        });
    }

    async function exportCardBlob() {
        var cardNode = document.getElementById("profile-share-card");
        if (!cardNode) {
            throw new Error("Card preview not found.");
        }

        if (document.fonts && document.fonts.ready) {
            await document.fonts.ready;
        }

        var rect = cardNode.getBoundingClientRect();
        var clone = cardNode.cloneNode(true);
        inlineStyles(cardNode, clone);

        clone.style.margin = "0";
        clone.style.width = rect.width + "px";
        clone.style.height = rect.height + "px";
        clone.style.maxWidth = "none";
        clone.style.transform = "none";

        var wrapper = document.createElement("div");
        wrapper.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
        wrapper.style.width = rect.width + "px";
        wrapper.style.height = rect.height + "px";
        wrapper.style.display = "block";
        wrapper.style.margin = "0";
        wrapper.style.padding = "0";
        wrapper.style.background = "transparent";
        wrapper.appendChild(clone);

        var serialized = new XMLSerializer().serializeToString(wrapper);
        var svgMarkup = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="' + rect.width + '" height="' + rect.height + '" viewBox="0 0 ' + rect.width + " " + rect.height + '">',
            '<foreignObject width="100%" height="100%">',
            serialized,
            "</foreignObject>",
            "</svg>"
        ].join("");

        var img = new Image();
        var scale = 3;
        var canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(rect.width * scale));
        canvas.height = Math.max(1, Math.round(rect.height * scale));
        var ctx = canvas.getContext("2d");
        ctx.setTransform(scale, 0, 0, scale, 0, 0);

        await new Promise(function (resolve, reject) {
            img.onload = resolve;
            img.onerror = reject;
            img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgMarkup);
        });

        ctx.drawImage(img, 0, 0, rect.width, rect.height);
        var blob = await canvasToBlob(canvas);
        if (!blob) {
            throw new Error("Could not create image.");
        }
        return blob;
    }

    async function downloadCard() {
        var blob;
        try {
            blob = await exportCardBlob();
        } catch (error) {
            setStatus("Failed to create image.");
            return;
        }

        var url = URL.createObjectURL(blob);
        var link = document.createElement("a");
        link.href = url;
        link.download = "covise-profile-card.png";
        link.click();
        URL.revokeObjectURL(url);
        setStatus("Card image downloaded.");
    }

    async function shareCard() {
        var blob;
        try {
            blob = await exportCardBlob();
        } catch (error) {
            setStatus("Failed to prepare card for sharing.");
            return;
        }

        var file = new File([blob], "covise-profile-card.png", { type: "image/png" });

        if (navigator.canShare && navigator.canShare({ files: [file] }) && navigator.share) {
            try {
                await navigator.share({
                    files: [file],
                    title: "My CoVise Profile Card",
                    text: "Here is my CoVise profile card.",
                    url: shareUrl
                });
                setStatus("Card shared successfully.");
            } catch (error) {
                if (error && error.name !== "AbortError") {
                    setStatus("Share canceled or not available.");
                }
            }
            return;
        }

        try {
            await navigator.clipboard.writeText(shareUrl);
            setStatus("Share not supported here. Public profile link copied.");
        } catch (error) {
            setStatus("Share not supported on this device.");
        }
    }

    async function copyCardLink() {
        try {
            await navigator.clipboard.writeText(shareUrl);
            setStatus("Public profile link copied.");
        } catch (error) {
            window.prompt("Copy this profile link:", shareUrl);
            setStatus("Profile link ready to copy.");
        }
    }

    downloadBtn.addEventListener("click", downloadCard);
    shareBtn.addEventListener("click", shareCard);
    copyBtn.addEventListener("click", copyCardLink);

    paintHtmlCard();
})();
