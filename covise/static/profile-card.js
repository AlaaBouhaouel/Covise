(function () {
    var input = document.getElementById('profile-card-file');
    var feedback = document.getElementById('import-feedback');

    if (!input || !feedback) {
        return;
    }

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

    function toText(value, fallback) {
        if (typeof value === 'string' && value.trim()) {
            return value.trim();
        }
        return fallback;
    }

    function toArray(value, fallback) {
        if (Array.isArray(value)) {
            var cleaned = value
                .filter(function (item) { return typeof item === 'string' && item.trim(); })
                .map(function (item) { return item.trim(); });
            if (cleaned.length) {
                return cleaned;
            }
        }
        return fallback;
    }

    function toScore(value, fallback) {
        var parsed = Number(value);
        if (!Number.isFinite(parsed)) {
            return fallback;
        }
        if (parsed < 0) {
            return 0;
        }
        if (parsed > 100) {
            return 100;
        }
        return Math.round(parsed);
    }

    function renderChips(target, values) {
        target.innerHTML = '';
        values.forEach(function (value, index) {
            var chip = document.createElement('span');
            chip.className = index === 0 ? 'share-chip active' : 'share-chip';
            chip.textContent = value;
            target.appendChild(chip);
        });
    }

    function renderCard(data) {
        var fullName = toText(data.name, 'Ahmed Al-Rashidi');
        var title = toText(data.title, 'Operations');
        var location = toText(data.location, 'Riyadh, KSA');
        var score = toScore(data.seriousness_score, 84);
        var skills = toArray(data.skills, ['Operations', 'Supply Chain', 'Team Building', 'Finance']);
        var lookingFor = toArray(data.looking_for, ['Tech Co-Founder', 'Product']);
        var about = toText(
            data.about,
            'Building a B2B logistics platform for SMEs in Saudi. 8 years in supply chain. Need a technical co-founder who can ship fast and own the product.'
        );

        elements.name.textContent = fullName;
        elements.avatar.textContent = fullName.charAt(0).toUpperCase();
        elements.meta.textContent = title + ' - ' + location;
        elements.score.textContent = String(score);
        elements.scoreFill.style.width = score + '%';
        elements.about.textContent = about;

        renderChips(elements.skills, skills);
        renderChips(elements.lookingFor, lookingFor);
    }

    function setFeedback(message, isError) {
        feedback.textContent = message;
        feedback.classList.toggle('error', !!isError);
    }

    input.addEventListener('change', function (event) {
        var file = event.target.files && event.target.files[0];
        if (!file) {
            return;
        }

        var reader = new FileReader();
        reader.onload = function (loadEvent) {
            try {
                var raw = String(loadEvent.target.result || '');
                var parsed = JSON.parse(raw);
                renderCard(parsed);
                setFeedback('Profile card imported successfully.', false);
            } catch (error) {
                setFeedback('Could not read file. Upload a valid JSON card file.', true);
            }
        };
        reader.onerror = function () {
            setFeedback('Could not read file. Please try again.', true);
        };

        reader.readAsText(file);
    });
})();
