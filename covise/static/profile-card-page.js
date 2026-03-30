(function () {
    var downloadBtn = document.getElementById('downloadCardBtn');
    var shareBtn = document.getElementById('shareCardBtn');
    var statusEl = document.getElementById('cardStatus');

    var elements = {
        avatar: document.getElementById('card-avatar'),
        name: document.getElementById('card-name'),
        meta: document.getElementById('card-meta'),
        score: document.getElementById('card-score'),
        scoreFill: document.getElementById('card-score-fill'),
        skills: document.getElementById('card-skills'),
        lookingFor: document.getElementById('card-looking-for'),
        about: document.getElementById('card-about')
    };

    if (!downloadBtn || !shareBtn || !statusEl || !elements.name) {
        return;
    }

    var cardDataElement = document.getElementById('profile-card-data');
    var cardData = cardDataElement ? JSON.parse(cardDataElement.textContent) : {
        avatar_initials: elements.avatar ? elements.avatar.textContent.trim() : 'CV',
        display_name: elements.name ? elements.name.textContent.trim() : 'CoVise User',
        role_location: elements.meta ? elements.meta.textContent.trim() : 'PROFILE IN PROGRESS',
        score: elements.score ? parseInt(elements.score.textContent, 10) || 0 : 0,
        skills: Array.from(elements.skills ? elements.skills.querySelectorAll('.share-chip') : []).map(function (chip) {
            return chip.textContent.trim();
        }),
        looking_for: Array.from(elements.lookingFor ? elements.lookingFor.querySelectorAll('.share-chip') : []).map(function (chip) {
            return chip.textContent.trim();
        }),
        about: elements.about ? elements.about.textContent.trim() : ''
    };

    function setStatus(message) {
        statusEl.textContent = message;
    }

    function renderChips(container, chips) {
        container.innerHTML = '';
        chips.forEach(function (chip, index) {
            var span = document.createElement('span');
            span.className = index === 0 ? 'share-chip active' : 'share-chip';
            span.textContent = chip;
            container.appendChild(span);
        });
    }

    function paintHtmlCard() {
        elements.name.textContent = cardData.display_name;
        elements.avatar.textContent = cardData.avatar_initials;
        elements.meta.textContent = cardData.role_location;
        elements.score.textContent = String(cardData.score);
        elements.scoreFill.style.width = cardData.score + '%';
        elements.about.textContent = cardData.about;
        renderChips(elements.skills, cardData.skills);
        renderChips(elements.lookingFor, cardData.looking_for);
    }

    function roundedRect(ctx, x, y, w, h, r) {
        var radius = Math.min(r, w / 2, h / 2);
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.arcTo(x + w, y, x + w, y + h, radius);
        ctx.arcTo(x + w, y + h, x, y + h, radius);
        ctx.arcTo(x, y + h, x, y, radius);
        ctx.arcTo(x, y, x + w, y, radius);
        ctx.closePath();
    }

    function drawChip(ctx, x, y, text, active) {
        ctx.font = '600 18px Syne, Segoe UI, sans-serif';
        var width = ctx.measureText(text).width + 26;

        roundedRect(ctx, x, y, width, 38, 19);
        ctx.fillStyle = active ? 'rgba(120,150,255,0.24)' : 'rgba(255,255,255,0.03)';
        ctx.fill();
        ctx.strokeStyle = active ? 'rgba(120,150,255,0.5)' : 'rgba(255,255,255,0.16)';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = active ? '#e2edff' : '#c4d0e5';
        ctx.fillText(text, x + 13, y + 25);
        return width;
    }

    function drawChipRows(ctx, items, startX, startY, maxX) {
        var x = startX;
        var y = startY;
        var gapX = 12;
        var gapY = 50;

        items.forEach(function (item, index) {
            ctx.font = '600 18px Syne, Segoe UI, sans-serif';
            var width = ctx.measureText(item).width + 26;
            if (x + width > maxX) {
                x = startX;
                y += gapY;
            }
            var used = drawChip(ctx, x, y, item, index === 0);
            x += used + gapX;
        });

        return y;
    }

    function getAboutLines(ctx) {
        ctx.font = '500 20px Syne, Segoe UI, sans-serif';
        var words = cardData.about.split(' ');
        var lines = [];
        var current = '';

        words.forEach(function (word) {
            var next = current ? current + ' ' + word : word;
            if (ctx.measureText(next).width > 780) {
                lines.push(current);
                current = word;
            } else {
                current = next;
            }
        });

        if (current) {
            lines.push(current);
        }

        return lines;
    }

    function buildCardCanvas() {
        var measure = document.createElement('canvas');
        measure.width = 920;
        measure.height = 560;
        var mctx = measure.getContext('2d');

        var skillsBottom = drawChipRows(mctx, cardData.skills, 62, 392, 858);
        var lookingBottom = drawChipRows(mctx, cardData.lookingFor, 62, skillsBottom + 84, 858);
        var aboutStart = lookingBottom + 95;
        var aboutLines = getAboutLines(mctx);
        var height = Math.max(700, aboutStart + ((aboutLines.length - 1) * 30) + 52);

        var dpr = Math.max(2, window.devicePixelRatio || 1);
        var canvas = document.createElement('canvas');
        canvas.width = Math.round(920 * dpr);
        canvas.height = Math.round(height * dpr);
        var ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        var baseGrad = ctx.createLinearGradient(0, 0, 0, height);
        baseGrad.addColorStop(0, '#0a0f1b');
        baseGrad.addColorStop(1, '#0e1829');
        roundedRect(ctx, 0, 0, 920, height, 34);
        ctx.fillStyle = baseGrad;
        ctx.fill();

        var heroGrad = ctx.createLinearGradient(0, 0, 920, 178);
        heroGrad.addColorStop(0, '#05070d');
        heroGrad.addColorStop(1, '#0f1627');
        roundedRect(ctx, 0, 0, 920, 178, 34);
        ctx.fillStyle = heroGrad;
        ctx.fill();

        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 178, 920, height - 178);
        ctx.clip();
        var bodyGrad = ctx.createLinearGradient(0, 178, 920, height);
        bodyGrad.addColorStop(0, '#101a2c');
        bodyGrad.addColorStop(1, '#162238');
        roundedRect(ctx, 0, 0, 920, height, 34);
        ctx.fillStyle = bodyGrad;
        ctx.fill();
        ctx.restore();

        // Soft top highlight for depth.
        var topGlow = ctx.createRadialGradient(460, 24, 60, 460, 24, 520);
        topGlow.addColorStop(0, 'rgba(160,190,255,0.10)');
        topGlow.addColorStop(1, 'rgba(160,190,255,0)');
        ctx.fillStyle = topGlow;
        ctx.fillRect(0, 0, 920, 240);

        // Subtle vignette.
        var vignette = ctx.createRadialGradient(460, height * 0.5, 240, 460, height * 0.5, 620);
        vignette.addColorStop(0, 'rgba(0,0,0,0)');
        vignette.addColorStop(1, 'rgba(0,0,0,0.24)');
        ctx.fillStyle = vignette;
        roundedRect(ctx, 0, 0, 920, height, 34);
        ctx.fill();

        ctx.beginPath();
        ctx.arc(95, 95, 46, 0, Math.PI * 2);
        ctx.fillStyle = '#d0ad6a';
        ctx.fill();
        ctx.fillStyle = '#171209';
        ctx.font = '700 52px Syne, Segoe UI, sans-serif';
        ctx.fillText(cardData.avatar_initials, 80, 112);

        ctx.fillStyle = '#f2f5fc';
        ctx.font = '700 52px Syne, Segoe UI, sans-serif';
        ctx.fillText(cardData.display_name, 182, 96);

        ctx.fillStyle = '#8f9eb9';
        ctx.font = '600 26px Syne, Segoe UI, sans-serif';
        ctx.fillText(cardData.role_location, 182, 133);

        roundedRect(ctx, 682, 70, 178, 56, 28);
        ctx.fillStyle = 'rgba(216,177,100,0.12)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(216,177,100,0.5)';
        ctx.stroke();
        ctx.fillStyle = '#e7c88c';
        ctx.font = '700 24px Syne, Segoe UI, sans-serif';
        ctx.fillText('VERIFIED', 718, 106);

        roundedRect(ctx, 62, 210, 796, 118, 22);
        ctx.fillStyle = 'rgba(255,255,255,0.04)';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.28)';
        ctx.shadowBlur = 24;
        ctx.shadowOffsetY = 8;
        ctx.fill();
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;
        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
        ctx.stroke();

        ctx.fillStyle = '#9aa6bd';
        ctx.font = '500 22px Syne, Segoe UI, sans-serif';
        ctx.fillText('FOUNDER CONVICTION', 98, 250);
        ctx.fillStyle = '#f0f4fd';
        ctx.font = '700 58px Syne, Segoe UI, sans-serif';
        ctx.fillText(String(cardData.score), 98, 302);
        ctx.fillStyle = '#8f9eb9';
        ctx.font = '500 42px Syne, Segoe UI, sans-serif';
        ctx.fillText('/100', 180, 302);

        roundedRect(ctx, 98, 316, 330, 10, 5);
        ctx.fillStyle = 'rgba(255,255,255,0.12)';
        ctx.fill();
        roundedRect(ctx, 98, 316, 330 * (cardData.score / 100), 10, 5);
        var progressGrad = ctx.createLinearGradient(98, 316, 428, 316);
        progressGrad.addColorStop(0, '#4a8eff');
        progressGrad.addColorStop(1, '#5ab5ff');
        ctx.fillStyle = progressGrad;
        ctx.fill();

        ctx.fillStyle = '#9aa6bd';
        ctx.font = '500 22px Syne, Segoe UI, sans-serif';
        ctx.fillText('SKILLS', 62, 376);
        skillsBottom = drawChipRows(ctx, cardData.skills, 62, 392, 858);

        ctx.fillStyle = '#9aa6bd';
        ctx.font = '500 22px Syne, Segoe UI, sans-serif';
        ctx.fillText('LOOKING FOR', 62, skillsBottom + 68);
        lookingBottom = drawChipRows(ctx, cardData.looking_for, 62, skillsBottom + 84, 858);

        ctx.strokeStyle = 'rgba(255,255,255,0.14)';
        ctx.beginPath();
        ctx.moveTo(62, lookingBottom + 62);
        ctx.lineTo(858, lookingBottom + 62);
        ctx.stroke();

        ctx.fillStyle = '#c4cfdf';
        ctx.font = '500 20px Syne, Segoe UI, sans-serif';
        var y = lookingBottom + 95;
        aboutLines.forEach(function (line) {
            ctx.fillText(line, 62, y);
            y += 30;
        });

        return canvas;
    }

    function toBlob(canvas) {
        return new Promise(function (resolve) {
            canvas.toBlob(function (blob) {
                resolve(blob);
            }, 'image/png');
        });
    }

    async function downloadCard() {
        var canvas = buildCardCanvas();
        var blob = await toBlob(canvas);
        if (!blob) {
            setStatus('Failed to create image.');
            return;
        }

        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'covise-profile-card.png';
        link.click();
        URL.revokeObjectURL(url);
        setStatus('Card image downloaded.');
    }

    async function shareCard() {
        var canvas = buildCardCanvas();
        var blob = await toBlob(canvas);
        if (!blob) {
            setStatus('Failed to prepare card for sharing.');
            return;
        }

        var file = new File([blob], 'covise-profile-card.png', { type: 'image/png' });

        if (navigator.canShare && navigator.canShare({ files: [file] }) && navigator.share) {
            try {
                await navigator.share({
                    files: [file],
                    title: 'My CoVise Profile Card',
                    text: 'Here is my CoVise profile card.'
                });
                setStatus('Card shared successfully.');
            } catch (error) {
                if (error && error.name !== 'AbortError') {
                    setStatus('Share canceled or not available.');
                }
            }
            return;
        }

        try {
            await navigator.clipboard.writeText(window.location.href);
            setStatus('Share not supported here. Page link copied to clipboard.');
        } catch (error) {
            setStatus('Share not supported on this device.');
        }
    }

    downloadBtn.addEventListener('click', downloadCard);
    shareBtn.addEventListener('click', shareCard);

    paintHtmlCard();
})();
