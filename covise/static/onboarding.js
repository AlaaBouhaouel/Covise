(function() {
    const flowNode = document.getElementById("boarding-flow");
    const initialAnswersNode = document.getElementById("onboarding-initial-answers");
    const redirectNode = document.getElementById("onboarding-complete-redirect-url");
    const startStepNode = document.getElementById("onboarding-start-step-id");

    if (!flowNode || !initialAnswersNode || !redirectNode) {
        return;
    }

    const PROFILE_STEP_ID = "S1_PROFILE_COMPLETION";
    const INTENT_STEP_ID = "S2_INTENT_SETUP";

    const flow = JSON.parse(flowNode.textContent);
    const initialAnswers = JSON.parse(initialAnswersNode.textContent);
    const completionRedirectUrl = JSON.parse(redirectNode.textContent);
    const startStepId = startStepNode ? JSON.parse(startStepNode.textContent) : PROFILE_STEP_ID;
    const config = window.CoviseOnboardingConfig || {};

    const flowName = document.getElementById("flow-name");
    const flowIntro = document.getElementById("flow-intro");
    const progressStep = document.getElementById("progress-step");
    const progressLabel = document.getElementById("progress-label");
    const progressLineFill = document.getElementById("progress-line-fill");
    const stepTitle = document.getElementById("step-title");
    const stepDescription = document.getElementById("step-description");
    const stepFields = document.getElementById("step-fields");
    const finishLaterBtn = document.getElementById("finish-later-btn");
    const nextBtn = document.getElementById("next-btn");
    const completionNote = document.getElementById("completion-note");

    const answers = { ...initialAnswers };
    const pendingFiles = {};
    let currentIndex = 0;

    function normalizeText(text) {
        return String(text || "");
    }

    function setCompletionMessage(text, state) {
        completionNote.textContent = normalizeText(text || "");
        completionNote.classList.remove("is-error", "is-success");
        if (state === "error") completionNote.classList.add("is-error");
        if (state === "success") completionNote.classList.add("is-success");
    }

    function getSingleOptions(field) {
        return (field.options || [])
            .map((option) => {
                if (option && typeof option === "object") {
                    return {
                        value: String(option.value || option.label || ""),
                        label: normalizeText(option.label || option.value || ""),
                        description: normalizeText(option.description || ""),
                    };
                }

                const label = normalizeText(option);
                return {
                    value: label,
                    label,
                    description: "",
                };
            })
            .filter((option) => option.value);
    }

    function evaluateShowIf(showIf) {
        if (!showIf) return true;

        if (showIf.any_of && Array.isArray(showIf.any_of)) {
            return showIf.any_of.some((rule) => answers[rule.field] === rule.equals);
        }

        if (showIf.field) {
            return answers[showIf.field] === showIf.equals;
        }

        return true;
    }

    function getVisibleSteps() {
        return (flow.steps || []).filter((step) => evaluateShowIf(step.show_if));
    }

    function ensureCurrentStepInBounds() {
        const visibleSteps = getVisibleSteps();
        if (currentIndex > visibleSteps.length - 1) {
            currentIndex = Math.max(0, visibleSteps.length - 1);
        }
        return visibleSteps;
    }

    function updateAnswer(fieldId, value) {
        if (Array.isArray(value)) {
            answers[fieldId] = value;
            return;
        }

        if (typeof value === "string") {
            answers[fieldId] = value.trim();
            return;
        }

        answers[fieldId] = value;
    }

    function currentSingleValue(fieldId) {
        const value = answers[fieldId];
        if (Array.isArray(value)) {
            return value[0] || "";
        }
        return value || "";
    }

    function buildTextInput(field) {
        if (field.type === "multi_line_text") {
            const textarea = document.createElement("textarea");
            textarea.id = field.id;
            textarea.name = field.id;
            textarea.className = "textarea-input";
            textarea.placeholder = normalizeText(field.placeholder || "");
            textarea.required = !!field.required;
            textarea.value = answers[field.id] || "";
            if (field.max_chars) {
                textarea.maxLength = Number(field.max_chars);
            }
            textarea.addEventListener("input", () => {
                updateAnswer(field.id, textarea.value);
                updateButtons();
            });
            return textarea;
        }

        const input = document.createElement("input");
        input.id = field.id;
        input.name = field.id;
        input.className = "text-input";
        input.placeholder = normalizeText(field.placeholder || "");
        input.required = !!field.required;
        input.value = answers[field.id] || "";

        switch (field.type) {
            case "email":
                input.type = "email";
                break;
            case "url":
                input.type = "url";
                break;
            default:
                input.type = "text";
                break;
        }

        input.addEventListener("input", () => {
            updateAnswer(field.id, input.value);
            updateButtons();
        });

        return input;
    }

    function buildImageUpload(field) {
        const wrap = document.createElement("div");
        wrap.className = "upload-field";

        const card = document.createElement("div");
        card.className = "upload-card";

        const preview = document.createElement("div");
        preview.className = "upload-preview";
        preview.textContent = "+";

        const copy = document.createElement("div");
        copy.className = "upload-copy";

        const title = document.createElement("div");
        title.className = "upload-title";
        title.textContent = "Profile photo";

        const meta = document.createElement("div");
        meta.className = "upload-meta";
        meta.textContent = normalizeText(field.helper_text || "Optional. Add a photo now or later.");

        const actions = document.createElement("div");
        actions.className = "upload-actions";

        const trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "upload-trigger";
        trigger.textContent = "Upload photo";

        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "upload-remove";
        remove.textContent = "Remove";
        remove.hidden = !answers[field.id];

        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.hidden = true;

        function resetPreview() {
            preview.className = "upload-preview";
            preview.textContent = "+";
            preview.style.backgroundImage = "";
            remove.hidden = true;
            delete pendingFiles[field.id];
            delete answers[field.id];
            input.value = "";
            updateButtons();
        }

        trigger.addEventListener("click", () => input.click());
        remove.addEventListener("click", resetPreview);

        input.addEventListener("change", () => {
            const file = input.files && input.files[0];
            if (!file) {
                resetPreview();
                return;
            }

            pendingFiles[field.id] = file;
            answers[field.id] = file.name;
            remove.hidden = false;

            const reader = new FileReader();
            reader.onload = () => {
                preview.className = "upload-preview-image";
                preview.textContent = "";
                preview.style.backgroundImage = `url("${reader.result}")`;
                preview.style.backgroundSize = "cover";
                preview.style.backgroundPosition = "center";
            };
            reader.readAsDataURL(file);
            updateButtons();
        });

        actions.appendChild(trigger);
        actions.appendChild(remove);
        copy.appendChild(title);
        copy.appendChild(meta);
        copy.appendChild(actions);
        card.appendChild(preview);
        card.appendChild(copy);
        wrap.appendChild(card);
        wrap.appendChild(input);

        return wrap;
    }

    function buildLinkList(field) {
        const wrap = document.createElement("div");
        wrap.className = "link-list-wrap";

        const list = document.createElement("div");
        list.className = "link-list";

        const addButton = document.createElement("button");
        addButton.type = "button";
        addButton.className = "link-add";
        addButton.setAttribute("aria-label", "Add another link");
        addButton.textContent = "+";

        const values = Array.isArray(answers[field.id]) ? answers[field.id].slice(0, Number(field.max_selected || 5)) : [];
        if (!values.length) {
            values.push("");
        }

        function syncAnswer() {
            const normalized = values.map((value) => String(value || "").trim()).filter(Boolean);
            answers[field.id] = normalized;
        }

        function renderRows() {
            list.innerHTML = "";

            values.forEach((value, index) => {
                const row = document.createElement("div");
                row.className = "link-row";

                const input = document.createElement("input");
                input.type = "url";
                input.className = "text-input";
                input.placeholder = normalizeText(field.placeholder || "https://example.com");
                input.value = value || "";
                input.addEventListener("input", () => {
                    values[index] = input.value;
                    syncAnswer();
                    updateButtons();
                });

                row.appendChild(input);

                if (values.length > 1) {
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.className = "link-remove";
                    remove.setAttribute("aria-label", "Remove link");
                    remove.textContent = "x";
                    remove.addEventListener("click", () => {
                        values.splice(index, 1);
                        if (!values.length) {
                            values.push("");
                        }
                        syncAnswer();
                        renderRows();
                        updateButtons();
                    });
                    row.appendChild(remove);
                }

                list.appendChild(row);
            });

            addButton.hidden = values.length >= Number(field.max_selected || 5);
        }

        addButton.addEventListener("click", () => {
            if (values.length >= Number(field.max_selected || 5)) return;
            values.push("");
            renderRows();
        });

        syncAnswer();
        renderRows();
        wrap.appendChild(list);
        wrap.appendChild(addButton);
        return wrap;
    }

    function buildCardSelect(field) {
        const wrap = document.createElement("div");
        wrap.className = "choice-grid";

        const options = getSingleOptions(field);
        const cardEntries = [];

        function syncCardState() {
            cardEntries.forEach(({ label, radio }) => {
                label.classList.toggle("is-active", radio.checked);
            });
        }

        options.forEach((option) => {
            const label = document.createElement("label");
            label.className = "choice-card";

            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = field.id;
            radio.value = option.value;
            radio.checked = currentSingleValue(field.id) === option.value;
            radio.addEventListener("change", () => {
                updateAnswer(field.id, radio.value);
                syncCardState();
                updateButtons();
            });

            const title = document.createElement("span");
            title.className = "choice-card-title";
            title.textContent = option.label;

            label.appendChild(radio);
            label.appendChild(title);

            if (option.description) {
                const description = document.createElement("span");
                description.className = "choice-card-description";
                description.textContent = option.description;
                label.appendChild(description);
            }

            wrap.appendChild(label);
            cardEntries.push({ label, radio });
        });

        syncCardState();
        return wrap;
    }

    function buildSingleSelect(field) {
        if (field.type === "single_select_card") {
            return buildCardSelect(field);
        }

        const options = getSingleOptions(field);

        if (field.type === "single_select_searchable") {
            const wrap = document.createElement("div");

            const input = document.createElement("input");
            input.type = "text";
            input.id = field.id;
            input.name = field.id;
            input.className = "search-input";
            input.placeholder = "Search and select one option";
            input.autocomplete = "off";
            input.required = !!field.required;

            const byLabel = new Map(options.map((o) => [o.label, o.value]));
            const byValue = new Map(options.map((o) => [o.value, o.label]));

            const selectedValue = currentSingleValue(field.id);
            if (selectedValue && byValue.has(selectedValue)) {
                input.value = byValue.get(selectedValue);
            }

            const dropdown = document.createElement("div");
            dropdown.className = "custom-dropdown";
            dropdown.setAttribute("hidden", "");
            document.body.appendChild(dropdown);

            function positionDropdown() {
                const r = input.getBoundingClientRect();
                dropdown.style.top = (r.bottom + 4) + "px";
                dropdown.style.left = r.left + "px";
                dropdown.style.width = r.width + "px";
            }

            function renderDropdown(filter) {
                dropdown.innerHTML = "";
                const lower = (filter || "").toLowerCase();
                const visible = lower ? options.filter((o) => o.label.toLowerCase().includes(lower)) : options;
                visible.forEach((option) => {
                    const item = document.createElement("div");
                    item.className = "custom-dropdown-option";
                    item.textContent = option.label;
                    const pick = (e) => {
                        e.preventDefault();
                        input.value = option.label;
                        answers[field.id] = option.value;
                        dropdown.setAttribute("hidden", "");
                        updateButtons();
                    };
                    item.addEventListener("mousedown", pick);
                    item.addEventListener("touchend", pick);
                    dropdown.appendChild(item);
                });
            }

            input.addEventListener("focus", () => {
                renderDropdown(input.value);
                positionDropdown();
                dropdown.removeAttribute("hidden");
            });
            input.addEventListener("input", () => {
                const entered = input.value.trim();
                answers[field.id] = byLabel.get(entered) || "";
                renderDropdown(input.value);
                positionDropdown();
                dropdown.removeAttribute("hidden");
                updateButtons();
            });
            input.addEventListener("blur", () => {
                setTimeout(() => {
                    dropdown.setAttribute("hidden", "");
                    if (!answers[field.id]) input.value = "";
                }, 200);
            });

            const reposSearchable = () => { if (!dropdown.hasAttribute("hidden")) positionDropdown(); };
            window.addEventListener("scroll", reposSearchable, { passive: true });
            window.addEventListener("resize", reposSearchable, { passive: true });

            wrap.appendChild(input);
            return wrap;
        }

        const wrap = document.createElement("div");
        wrap.className = "select-list";
        const entries = [];

        function syncSelectedState() {
            entries.forEach(({ label, radio }) => {
                label.classList.toggle("is-active", radio.checked);
            });
        }

        options.forEach((option) => {
            const label = document.createElement("label");
            label.className = "select-option";

            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = field.id;
            radio.value = option.value;
            radio.checked = currentSingleValue(field.id) === option.value;
            radio.addEventListener("change", () => {
                updateAnswer(field.id, radio.value);
                syncSelectedState();
                updateButtons();
            });

            const copy = document.createElement("span");
            copy.className = "select-option-copy";

            const title = document.createElement("span");
            title.className = "select-option-title";
            title.textContent = option.label;
            copy.appendChild(title);

            if (option.description) {
                const description = document.createElement("span");
                description.className = "select-option-description";
                description.textContent = option.description;
                copy.appendChild(description);
            }

            label.appendChild(radio);
            label.appendChild(copy);
            wrap.appendChild(label);
            entries.push({ label, radio });
        });

        syncSelectedState();
        return wrap;
    }

    function buildMultiSelect(field) {
        const wrap = document.createElement("div");
        wrap.className = "multi-select-wrap";

        const options = getSingleOptions(field);
        const byValue = new Map(options.map((o) => [o.value, o.label]));
        const allowedValues = new Set(options.map((o) => o.value));
        const selected = new Set(
            Array.isArray(answers[field.id]) ? answers[field.id].filter((v) => allowedValues.has(v)) : []
        );

        const chipInput = document.createElement("div");
        chipInput.className = "chip-input";

        const chipContainer = document.createElement("div");
        chipContainer.className = "selected-chips";
        chipInput.appendChild(chipContainer);

        const search = document.createElement("input");
        search.type = "text";
        search.className = "search-input";
        search.placeholder = "Search and select";
        search.autocomplete = "off";
        chipInput.appendChild(search);

        const dropdown = document.createElement("div");
        dropdown.className = "custom-dropdown";
        dropdown.setAttribute("hidden", "");
        document.body.appendChild(dropdown);

        function syncAnswer() {
            answers[field.id] = Array.from(selected);
        }

        function positionDropdown() {
            const r = search.getBoundingClientRect();
            dropdown.style.top = (r.bottom + 4) + "px";
            dropdown.style.left = r.left + "px";
            dropdown.style.width = r.width + "px";
        }

        function renderDropdown(filter) {
            dropdown.innerHTML = "";
            const lower = (filter || "").toLowerCase();
            const visible = options.filter((o) => !selected.has(o.value) && (!lower || o.label.toLowerCase().includes(lower)));
            visible.forEach((option) => {
                const item = document.createElement("div");
                item.className = "custom-dropdown-option";
                item.textContent = option.label;
                const pick = (e) => {
                    e.preventDefault();
                    if (field.max_selected && selected.size >= Number(field.max_selected)) return;
                    selected.add(option.value);
                    search.value = "";
                    syncAnswer();
                    renderDropdown("");
                    renderChips();
                    updateButtons();
                };
                item.addEventListener("mousedown", pick);
                item.addEventListener("touchend", pick);
                dropdown.appendChild(item);
            });
        }

        function renderChips() {
            chipContainer.innerHTML = "";
            Array.from(selected).forEach((value) => {
                const chip = document.createElement("span");
                chip.className = "chip";
                chip.textContent = byValue.get(value) || value;

                const remove = document.createElement("button");
                remove.type = "button";
                remove.setAttribute("aria-label", "Remove " + (byValue.get(value) || value));
                remove.textContent = "x";
                remove.addEventListener("click", () => {
                    selected.delete(value);
                    syncAnswer();
                    renderDropdown(search.value);
                    renderChips();
                    updateButtons();
                });

                chip.appendChild(remove);
                chipContainer.appendChild(chip);
            });
        }

        search.addEventListener("focus", () => {
            renderDropdown(search.value);
            positionDropdown();
            dropdown.removeAttribute("hidden");
        });
        search.addEventListener("input", () => {
            renderDropdown(search.value);
            positionDropdown();
            dropdown.removeAttribute("hidden");
        });
        search.addEventListener("blur", () => {
            setTimeout(() => { dropdown.setAttribute("hidden", ""); }, 200);
        });
        search.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                const first = dropdown.querySelector(".custom-dropdown-option");
                if (first) first.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
            }
        });

        const reposMulti = () => { if (!dropdown.hasAttribute("hidden")) positionDropdown(); };
        window.addEventListener("scroll", reposMulti, { passive: true });
        window.addEventListener("resize", reposMulti, { passive: true });

        syncAnswer();
        renderChips();

        wrap.appendChild(chipInput);

        if (field.max_selected) {
            const helper = document.createElement("p");
            helper.className = "helper-text";
            helper.textContent = "Max selections: " + field.max_selected;
            wrap.appendChild(helper);
        }

        return wrap;
    }

    function buildControl(field) {
        if (field.type === "single_select" || field.type === "single_select_searchable" || field.type === "single_select_card") {
            return buildSingleSelect(field);
        }

        if (field.type === "multi_select" || field.type === "multi_select_searchable") {
            return buildMultiSelect(field);
        }

        if (field.type === "file_upload_image") {
            return buildImageUpload(field);
        }

        if (field.type === "link_list") {
            return buildLinkList(field);
        }

        return buildTextInput(field);
    }

    function isFieldValid(field) {
        const value = answers[field.id];

        if (!field.required) {
            return true;
        }

        if (field.type === "multi_select" || field.type === "multi_select_searchable" || field.type === "link_list") {
            return Array.isArray(value) && value.length > 0;
        }

        if (!value) {
            return false;
        }

        return String(value).trim() !== "";
    }

    function validateStep(step) {
        for (const field of step.fields || []) {
            if (!isFieldValid(field)) {
                return false;
            }
        }
        return true;
    }

    function currentStep() {
        const visibleSteps = ensureCurrentStepInBounds();
        return visibleSteps[currentIndex];
    }

    function isProfileStep(step) {
        return step && step.step_id === PROFILE_STEP_ID;
    }

    function serializeAnswers({ profileCompleted = false, extendedCompleted = false } = {}) {
        const payloadAnswers = { ...answers };
        if (profileCompleted) {
            payloadAnswers.profile_completion_completed = true;
        }
        if (extendedCompleted) {
            payloadAnswers.extended_onboarding_completed = true;
        }
        return payloadAnswers;
    }

    function renderStep() {
        document.querySelectorAll(".custom-dropdown").forEach(function (el) { el.remove(); });
        const visibleSteps = ensureCurrentStepInBounds();
        const step = visibleSteps[currentIndex];
        setCompletionMessage("", "");

        flowName.textContent = normalizeText(flow.flow_name || "Covise onboarding");
        flowIntro.textContent = normalizeText(
            flow.intro || "Set up your profile first, then continue with the deeper onboarding when you are ready."
        );

        stepTitle.textContent = normalizeText(step.title || "");
        const descriptionText = normalizeText(step.description || "");
        stepDescription.hidden = !descriptionText;
        stepDescription.textContent = descriptionText;

        const progress = ((currentIndex + 1) / visibleSteps.length) * 100;
        progressLineFill.style.width = progress + "%";
        if (progressStep) progressStep.textContent = "Step " + (currentIndex + 1) + " of " + visibleSteps.length;
        if (progressLabel) progressLabel.textContent = normalizeText(step.progress_label || step.title || "Profile");

        stepFields.innerHTML = "";

        (step.fields || []).forEach((field) => {
            const block = document.createElement("div");
            block.className = "field-block";

            const labelRow = document.createElement("div");
            labelRow.className = "field-head";

            const label = document.createElement("label");
            label.className = "field-label" + (field.required ? "" : " is-optional");
            label.htmlFor = field.id;
            label.textContent = normalizeText(field.label || "");
            labelRow.appendChild(label);

            const control = buildControl(field);
            if (field.type === "link_list") {
                const addButton = control.querySelector(".link-add");
                if (addButton) {
                    labelRow.appendChild(addButton);
                }
            }
            block.appendChild(labelRow);
            block.appendChild(control);

            if (field.helper_text && field.type !== "file_upload_image") {
                const helper = document.createElement("p");
                helper.className = "helper-text";
                helper.textContent = normalizeText(field.helper_text);
                block.appendChild(helper);
            }

            stepFields.appendChild(block);
        });

        finishLaterBtn.disabled = false;
        nextBtn.textContent = "Continue onboarding";
        updateButtons();
    }

    function updateButtons() {
        const step = currentStep();
        const valid = validateStep(step);
        nextBtn.disabled = !valid;
    }

    function getCsrfToken() {
        const cookie = document.cookie
            .split("; ")
            .find((row) => row.startsWith("csrftoken="));
        return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
    }

    async function submitOnboarding({ profileCompleted = false, extendedCompleted = false } = {}) {
        const formData = new FormData();
        formData.append(
            "payload",
            JSON.stringify({
                flow_name: flow.flow_name || "Covise onboarding",
                answers: serializeAnswers({ profileCompleted, extendedCompleted }),
            })
        );

        if (pendingFiles.profile_image instanceof File) {
            formData.append("profile_image", pendingFiles.profile_image);
        }

        const response = await fetch(config.submitUrl, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrfToken(),
            },
            body: formData,
        });

        if (!response.ok) {
            let payload = null;
            try {
                payload = await response.json();
            } catch (error) {
                payload = null;
            }
            throw new Error(payload && payload.error ? payload.error : "We could not save your onboarding right now. Please try again.");
        }
    }

    async function completeProfileAndExit() {
        setCompletionMessage("Saving your profile...", "");
        nextBtn.disabled = true;

        try {
            await submitOnboarding({ profileCompleted: true, extendedCompleted: false });
        } catch (error) {
            setCompletionMessage(error.message || "We could not save your profile right now. Please try again.", "error");
            updateButtons();
            return;
        }

        setCompletionMessage("Profile saved. Redirecting you to the guidelines...", "success");
        window.setTimeout(() => {
            window.location.href = completionRedirectUrl || "/";
        }, 450);
    }

    async function continueExtendedOnboarding() {
        setCompletionMessage("Saving your profile...", "");
        nextBtn.disabled = true;

        try {
            await submitOnboarding({ profileCompleted: true, extendedCompleted: false });
        } catch (error) {
            setCompletionMessage(error.message || "We could not save your profile right now. Please try again.", "error");
            updateButtons();
            return;
        }

        currentIndex += 1;
        renderStep();
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    async function goNext() {
        const visibleSteps = ensureCurrentStepInBounds();
        const step = visibleSteps[currentIndex];

        if (isProfileStep(step)) {
            await continueExtendedOnboarding();
            return;
        }

        if (currentIndex < visibleSteps.length - 1) {
            currentIndex += 1;
            renderStep();
            window.scrollTo({ top: 0, behavior: "smooth" });
            return;
        }

        setCompletionMessage(flow.success_message || "Your onboarding is saved.", "success");
        nextBtn.disabled = true;

        try {
            await submitOnboarding({ profileCompleted: true, extendedCompleted: true });
        } catch (error) {
            setCompletionMessage(error.message || "We could not save your onboarding right now. Please try again.", "error");
            nextBtn.disabled = false;
            return;
        }

        window.setTimeout(() => {
            window.location.href = completionRedirectUrl || "/";
        }, 600);
    }

    async function finishLater() {
        setCompletionMessage("Saving your progress...", "");
        finishLaterBtn.disabled = true;
        nextBtn.disabled = true;

        try {
            await submitOnboarding({ profileCompleted: true, extendedCompleted: false });
        } catch (error) {
            setCompletionMessage(error.message || "We could not save your progress right now. Please try again.", "error");
            finishLaterBtn.disabled = false;
            updateButtons();
            return;
        }

        setCompletionMessage("Progress saved. You can continue onboarding later.", "success");
        window.setTimeout(() => {
            window.location.href = completionRedirectUrl || "/";
        }, 400);
    }

    function initializeStartStep() {
        const visibleSteps = getVisibleSteps();
        const index = visibleSteps.findIndex((step) => step.step_id === startStepId);
        if (index >= 0) {
            currentIndex = index;
        }
    }

    finishLaterBtn.addEventListener("click", finishLater);
    nextBtn.addEventListener("click", goNext);

    initializeStartStep();
    renderStep();
})();
