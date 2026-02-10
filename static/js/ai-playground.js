(function () {
  const root = document.getElementById("ai-playground-root");
  if (!root) return;

  const uploadUrl = root.dataset.selfieUploadUrl;
  const generateUrl = root.dataset.generateUrl;
  const initialHasSelfie = root.dataset.hasSelfie === "true";
  const initialSelfieUrl = root.dataset.selfieUrl || "";

  const messages = {
    cameraOpened: root.dataset.msgCameraOpened || "Camera is ready. Capture your selfie.",
    cameraDenied: root.dataset.msgCameraDenied || "Camera access failed. Use file upload instead.",
    cameraBusy:
      root.dataset.msgCameraBusy ||
      "Camera is in use by another app or tab. Close other camera apps and retry.",
    cameraNotFound: root.dataset.msgCameraNotFound || "No camera device was found on this device.",
    cameraSecureContext:
      root.dataset.msgCameraSecureContext ||
      "Camera requires HTTPS (or localhost). Open the page over a secure connection.",
    selfieRequired: root.dataset.msgSelfieRequired || "Upload a selfie first.",
    selfieUploading: root.dataset.msgSelfieUploading || "Saving selfie...",
    selfieSaved: root.dataset.msgSelfieSaved || "Selfie saved.",
    selfieSaveFailed: root.dataset.msgSelfieSaveFailed || "Could not save selfie.",
    selfieCaptured: root.dataset.msgSelfieCaptured || "Selfie captured. Saving...",
    selfieSelected: root.dataset.msgSelfieSelected || "Selfie selected. Saving...",
    selfieRetakeReady:
      root.dataset.msgSelfieRetakeReady || "Retake ready. Capture or upload a new selfie.",
    hairStyleRequired: root.dataset.msgHairStyleRequired || "Choose a hairstyle first.",
    hairColorRequired: root.dataset.msgHairColorRequired || "Choose a hair color option first.",
    beardStyleRequired: root.dataset.msgBeardStyleRequired || "Choose a beard style option first.",
    beardColorRequired: root.dataset.msgBeardColorRequired || "Choose a beard color option first.",
    beardColorNeedsStyle:
      root.dataset.msgBeardColorNeedsStyle || "Choose a beard style before applying beard color.",
    generateFailed: root.dataset.msgGenerateFailed || "Generation request failed.",
    generateStarted: root.dataset.msgGenerateStarted || "Generating preview...",
    generateComplete: root.dataset.msgGenerateComplete || "Preview is ready.",
    generateCtaReady: root.dataset.msgGenerateCtaReady || "Generate",
    generateCtaPrompt:
      root.dataset.msgGenerateCtaPrompt || "Choose a Hair/Beard style to generate",
  };

  const selfieStep = document.getElementById("selfie-step");
  const selfieInputGrid = document.getElementById("selfie-input-grid");
  const selfiePreviewBlock = document.getElementById("selfie-preview-block");
  const styleStep = document.getElementById("style-step");
  const selfieVideo = document.getElementById("selfie-video");
  const selfiePreview = document.getElementById("selfie-preview");
  const selfieStatus = document.getElementById("selfie-status");
  const cameraSelfieBlock = document.getElementById("camera-selfie-block");
  const selfieTakePhotoBtn = document.getElementById("selfie-take-photo-btn");
  const selfieReplaceBtn = document.getElementById("selfie-replace-btn");
  const selfieGenerateBtn = document.getElementById("selfie-generate-btn");
  const selfieInput = document.getElementById("selfie-input");
  const selfieUploadZone = document.getElementById("selfie-upload-zone");
  const selfieUploadFilename = document.getElementById("selfie-upload-filename");
  const selfieGenerationBlock = document.getElementById("selfie-generation-block");
  const hairStyleOptions = Array.from(root.querySelectorAll(".js-hair-style-option"));
  const hairColorOptions = Array.from(root.querySelectorAll(".js-hair-color-option"));
  const beardStyleOptions = Array.from(root.querySelectorAll(".js-beard-style-option"));
  const beardColorOptions = Array.from(root.querySelectorAll(".js-beard-color-option"));
  const lookBuilder = root.querySelector(".ai-look-builder");
  const builderTabs = Array.from(root.querySelectorAll(".js-builder-tab"));
  const hairBuilderPanel = document.getElementById("hair-builder-panel");
  const beardBuilderPanel = document.getElementById("beard-builder-panel");
  const styleSelectionStatus = document.getElementById("style-selection-status");
  const defaultSelectionStatusText = (styleSelectionStatus?.textContent || "").trim();
  const generateLoader = document.getElementById("generate-loader");
  const generateStatus = document.getElementById("generate-status");
  const generatedResultBlock = document.getElementById("generated-result-block");
  const generatedResultImage = document.getElementById("generated-result-image");
  const generationLog = document.getElementById("generation-log");
  let hasSelfie = initialHasSelfie;
  let savedSelfieUrl = initialSelfieUrl;
  let pendingPreviewUrl = "";
  let selfieHasFile = Boolean(initialSelfieUrl);
  let selfieIsSaved = Boolean(initialSelfieUrl);
  let selectedHairStyleId = "";
  let selectedHairStyleName = "";
  let selectedHairColorId = "";
  let selectedHairColorName = "";
  let selectedBeardStyleId = "";
  let selectedBeardStyleName = "";
  let selectedBeardColorId = "";
  let selectedBeardColorName = "";
  let cameraStream = null;
  let isGenerating = false;
  let isSelfieUploading = false;

  function getCookie(name) {
    const value = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${name}=`));
    return value ? decodeURIComponent(value.split("=").slice(1).join("=")) : "";
  }

  function setStatus(message, isError) {
    if (!selfieStatus) return;
    const normalizedMessage = (message || "").trim();
    if (!normalizedMessage) {
      selfieStatus.textContent = "";
      selfieStatus.classList.remove("warning-text");
      selfieStatus.classList.add("hidden");
      return;
    }
    const hideSavedMessage = !isError && hasSelfie && normalizedMessage === messages.selfieSaved;
    selfieStatus.textContent = normalizedMessage;
    selfieStatus.classList.toggle("warning-text", Boolean(isError));
    selfieStatus.classList.toggle("hidden", hideSavedMessage);
  }

  function setGenerateStatus(message, isError) {
    if (!generateStatus) return;
    generateStatus.textContent = message;
    generateStatus.classList.toggle("warning-text", Boolean(isError));
  }

  function setGenerateLoading(isLoading) {
    if (!generateLoader) return;
    generateLoader.classList.toggle("hidden", !isLoading);
  }

  function setGeneratedImage(url) {
    if (!generatedResultImage) return;
    if (!url) {
      generatedResultImage.src = "";
      generatedResultImage.classList.add("hidden");
      if (generatedResultBlock) generatedResultBlock.classList.add("hidden");
      return;
    }
    generatedResultImage.src = url;
    generatedResultImage.classList.remove("hidden");
    if (generatedResultBlock) generatedResultBlock.classList.remove("hidden");
  }

  function setUploadFilename(target, fileName) {
    if (!target) return;
    const trimmed = (fileName || "").trim();
    target.textContent = trimmed;
    target.classList.toggle("hidden", !trimmed);
  }

  function setDropzoneActive(target, isActive) {
    if (!target) return;
    target.classList.toggle("is-dragover", Boolean(isActive));
  }

  function setZoneState(zone, state) {
    if (!zone) return;
    const hasFile = Boolean(state?.hasFile);
    const saved = hasFile && Boolean(state?.saved);
    const loading = Boolean(state?.loading);
    zone.classList.toggle("has-file", hasFile);
    zone.classList.toggle("is-saved", saved);
    zone.classList.toggle("is-loading", loading);
    zone.setAttribute("aria-busy", loading ? "true" : "false");
  }

  function applySelfieZoneState() {
    setZoneState(selfieUploadZone, {
      hasFile: selfieHasFile,
      saved: selfieIsSaved,
      loading: isSelfieUploading,
    });
  }

  function enableZoneKeyboardSupport(zone, input) {
    if (!zone || !input) return;
    zone.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      if (!input.disabled) input.click();
    });
  }

  function attachDropzone(zone, input, onFileSelected) {
    if (!zone || !input) return;

    const clearDragState = () => setDropzoneActive(zone, false);
    const onDragOver = (event) => {
      event.preventDefault();
      if (input.disabled) return;
      setDropzoneActive(zone, true);
    };
    const onDragLeave = (event) => {
      event.preventDefault();
      clearDragState();
    };
    const onDrop = async (event) => {
      event.preventDefault();
      clearDragState();
      if (input.disabled) return;
      const file = event.dataTransfer?.files?.[0];
      if (!file) return;
      await onFileSelected(file);
    };

    zone.addEventListener("dragenter", onDragOver);
    zone.addEventListener("dragover", onDragOver);
    zone.addEventListener("dragleave", onDragLeave);
    zone.addEventListener("dragend", clearDragState);
    zone.addEventListener("drop", onDrop);
  }

  function setStyleStepEnabled(enabled) {
    if (styleStep) {
      styleStep.classList.toggle("is-disabled", !enabled);
      styleStep.setAttribute("aria-disabled", enabled ? "false" : "true");
    }
    const isDisabled = !enabled || isGenerating;
    [...hairStyleOptions, ...hairColorOptions, ...beardStyleOptions, ...beardColorOptions, ...builderTabs].forEach(
      (button) => {
        button.disabled = isDisabled;
        button.setAttribute("aria-disabled", isDisabled ? "true" : "false");
      }
    );
    updateGenerateActionCta();
  }

  function setPressedState(options, selectedValue, valueKey) {
    options.forEach((option) => {
      const isSelected = option.dataset[valueKey] === selectedValue;
      option.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
  }

  function switchBuilderTab(tabKey) {
    if (lookBuilder) {
      lookBuilder.dataset.activeBuilder = tabKey;
    }
    builderTabs.forEach((tab) => {
      const isActive = tab.dataset.builderTab === tabKey;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-pressed", isActive ? "true" : "false");
      tab.setAttribute("aria-expanded", isActive ? "true" : "false");
    });
    if (hairBuilderPanel) {
      hairBuilderPanel.classList.toggle("hidden", tabKey !== "hair");
    }
    if (beardBuilderPanel) {
      beardBuilderPanel.classList.toggle("hidden", tabKey !== "beard");
    }
  }

  function getSelectionErrorMessage() {
    const hasHairStyle = Boolean(selectedHairStyleId && selectedHairStyleId !== "none");
    const hasBeardStyleChange = Boolean(selectedBeardStyleId && selectedBeardStyleId !== "none");
    if (!hasHairStyle && !hasBeardStyleChange) return messages.generateCtaPrompt;
    if (!selectedHairColorId) return messages.hairColorRequired;
    if (!selectedBeardStyleId) return messages.beardStyleRequired;
    if (!selectedBeardColorId) return messages.beardColorRequired;
    if (selectedBeardStyleId === "none" && selectedBeardColorId !== "none") {
      return messages.beardColorNeedsStyle;
    }
    return "";
  }

  function hasChosenLookStyle() {
    return Boolean(selectedHairStyleId && selectedHairStyleId !== "none") || Boolean(selectedBeardStyleId && selectedBeardStyleId !== "none");
  }

  function updateGenerateActionCta() {
    if (!selfieGenerateBtn) return;
    const hasStyleSelection = hasChosenLookStyle();
    const label = hasStyleSelection ? messages.generateCtaReady : messages.generateCtaPrompt;
    selfieGenerateBtn.textContent = label;
    const disabled = !hasSelfie || isGenerating || isSelfieUploading || !hasStyleSelection;
    selfieGenerateBtn.disabled = disabled;
    selfieGenerateBtn.setAttribute("aria-disabled", disabled ? "true" : "false");
    selfieGenerateBtn.classList.toggle("btn-outline", !hasStyleSelection);
  }

  function updateSelectionStatus() {
    if (!styleSelectionStatus) {
      updateGenerateActionCta();
      return;
    }
    const errorMessage = getSelectionErrorMessage();
    if (errorMessage) {
      styleSelectionStatus.textContent =
        defaultSelectionStatusText || "Select hairstyle, hair color, beard style, and beard color.";
      styleSelectionStatus.classList.remove("warning-text");
      updateGenerateActionCta();
      return;
    }
    const hairSummary = selectedHairStyleId && selectedHairStyleId !== "none"
      ? `${selectedHairStyleName || "Hairstyle"} · ${selectedHairColorName || "Default"}`
      : "No haircut change";
    const beardSummary =
      selectedBeardStyleId === "none"
        ? "No beard change"
        : `${selectedBeardStyleName || "Beard"} · ${selectedBeardColorName || "Default"}`;
    styleSelectionStatus.textContent = `${hairSummary} · ${beardSummary}`;
    styleSelectionStatus.classList.remove("warning-text");
    updateGenerateActionCta();
  }

  function syncSelfieMode() {
    const hasSavedPreview = Boolean(hasSelfie && savedSelfieUrl);
    if (selfieInputGrid) {
      selfieInputGrid.classList.toggle("hidden", hasSavedPreview);
    }
    if (selfiePreviewBlock) {
      selfiePreviewBlock.classList.toggle("hidden", !hasSavedPreview);
    }
    if (hasSavedPreview) {
      setSelfiePreview(savedSelfieUrl);
    }
    if (selfieGenerationBlock) {
      selfieGenerationBlock.classList.toggle("hidden", !hasSavedPreview);
    }
    updateGenerateActionCta();
  }

  function guideToSelfieStep() {
    syncSelfieMode();
    setStatus(messages.selfieRequired, true);
    const focusTarget = selfieUploadZone || cameraSelfieBlock || selfieInput;
    const scrollTarget = focusTarget || selfieStep;
    if (!scrollTarget) return;
    scrollTarget.scrollIntoView({ behavior: "smooth", block: "center" });
    if (typeof focusTarget?.focus === "function") {
      window.setTimeout(() => {
        try {
          focusTarget.focus({ preventScroll: true });
        } catch (_) {
          focusTarget.focus();
        }
      }, 220);
    }
  }

  function setSelfiePreview(src) {
    if (!selfiePreview) return;
    if (!src) {
      selfiePreview.src = "";
      selfiePreview.classList.add("hidden");
      return;
    }
    selfiePreview.src = src;
    selfiePreview.classList.remove("hidden");
  }

  function clearPendingPreview() {
    if (pendingPreviewUrl) {
      URL.revokeObjectURL(pendingPreviewUrl);
      pendingPreviewUrl = "";
    }
  }

  function clearPendingSelfie() {
    clearPendingPreview();
    if (selfieInput) selfieInput.value = "";
    selfieHasFile = false;
    selfieIsSaved = false;
    setUploadFilename(selfieUploadFilename, "");
    applySelfieZoneState();
  }

  function updateSelfieControls() {
    if (cameraSelfieBlock) {
      cameraSelfieBlock.disabled = isSelfieUploading;
      cameraSelfieBlock.classList.toggle("is-loading", isSelfieUploading);
      cameraSelfieBlock.setAttribute("aria-busy", isSelfieUploading ? "true" : "false");
    }
    if (selfieInput) selfieInput.disabled = isSelfieUploading;
    if (selfieTakePhotoBtn) selfieTakePhotoBtn.disabled = isSelfieUploading;
    if (selfieReplaceBtn) selfieReplaceBtn.disabled = isSelfieUploading;
    if (selfieUploadZone) {
      selfieUploadZone.classList.toggle("is-disabled", isSelfieUploading);
      selfieUploadZone.setAttribute("aria-disabled", isSelfieUploading ? "true" : "false");
      if (isSelfieUploading) setDropzoneActive(selfieUploadZone, false);
    }
    applySelfieZoneState();
    updateGenerateActionCta();
  }

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      cameraStream = null;
    }
  }

  function cameraErrorMessage(error) {
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return messages.cameraSecureContext;
    }
    const errorName = error?.name || "";
    if (errorName === "NotAllowedError" || errorName === "SecurityError") {
      return messages.cameraDenied;
    }
    if (errorName === "NotReadableError" || errorName === "TrackStartError") {
      return messages.cameraBusy;
    }
    if (errorName === "NotFoundError" || errorName === "OverconstrainedError") {
      return messages.cameraNotFound;
    }
    return messages.cameraDenied;
  }

  async function startCameraStream() {
    stopCamera();
    const attempts = [
      { video: { facingMode: { ideal: "user" } }, audio: false },
      { video: true, audio: false },
    ];
    let lastError = null;

    for (const constraints of attempts) {
      try {
        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        if (selfieVideo) {
          selfieVideo.srcObject = cameraStream;
          try {
            await selfieVideo.play();
          } catch (_) {
            // Ignore autoplay restrictions; metadata wait below still handles readiness.
          }
          if (!selfieVideo.videoWidth || !selfieVideo.videoHeight) {
            await new Promise((resolve) => {
              selfieVideo.addEventListener("loadedmetadata", resolve, { once: true });
            });
          }
        }
        return true;
      } catch (error) {
        lastError = error;
      }
    }

    setStatus(cameraErrorMessage(lastError), true);
    return false;
  }

  async function uploadSelfie(file) {
    const csrfToken = getCookie("csrftoken");
    const formData = new FormData();
    formData.append("image", file);

    const response = await fetch(uploadUrl, {
      method: "POST",
      headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
      credentials: "same-origin",
      body: formData,
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || messages.selfieSaveFailed);
    }
    return payload;
  }

  async function autoSaveSelfie(file) {
    if (!file || isSelfieUploading) return;

    isSelfieUploading = true;
    selfieHasFile = true;
    selfieIsSaved = false;
    applySelfieZoneState();
    updateSelfieControls();
    setStyleStepEnabled(false);
    setStatus(messages.selfieUploading, false);

    try {
      const payload = await uploadSelfie(file);
      savedSelfieUrl = payload.selfie.url;
      hasSelfie = true;
      clearPendingSelfie();
      setSelfiePreview(savedSelfieUrl);
      setUploadFilename(selfieUploadFilename, file.name || "");
      selfieHasFile = true;
      selfieIsSaved = true;
      applySelfieZoneState();
      setStyleStepEnabled(true);
      syncSelfieMode();
      setStatus(messages.selfieSaved, false);
    } catch (error) {
      selfieHasFile = true;
      selfieIsSaved = false;
      applySelfieZoneState();
      setStatus(error.message || messages.selfieSaveFailed, true);
      setStyleStepEnabled(true);
      syncSelfieMode();
    } finally {
      isSelfieUploading = false;
      applySelfieZoneState();
      updateSelfieControls();
    }
  }

  async function handleSelfieSelection(file, statusMessage) {
    if (!file) return;
    clearPendingPreview();
    pendingPreviewUrl = URL.createObjectURL(file);
    setSelfiePreview(pendingPreviewUrl);
    setUploadFilename(selfieUploadFilename, file.name || "");
    selfieHasFile = true;
    selfieIsSaved = false;
    applySelfieZoneState();
    setStatus(statusMessage || messages.selfieSelected, false);
    await autoSaveSelfie(file);
  }

  async function submitGeneration(formData, sourceLabel) {
    if (!hasSelfie) {
      setGenerateStatus(messages.selfieRequired, true);
      guideToSelfieStep();
      return;
    }
    if (isGenerating) return;

    isGenerating = true;
    setStyleStepEnabled(true);
    setGenerateLoading(true);
    setGenerateStatus(messages.generateStarted, false);

    try {
      const csrfToken = getCookie("csrftoken");
      const response = await fetch(generateUrl, {
        method: "POST",
        headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
        credentials: "same-origin",
        body: formData,
      });

      let payload = {};
      try {
        payload = await response.json();
      } catch (_) {
        payload = {};
      }

      if (!response.ok || !payload.ok) {
        const rawError = payload.error || messages.generateFailed;
        const rawDetails = typeof payload.details === "string" ? payload.details.trim() : "";
        const compactDetails = rawDetails.replace(/\s+/g, " ").slice(0, 200);
        const message = compactDetails ? `${rawError} (${compactDetails})` : rawError;
        throw new Error(message);
      }

      const resultUrl = payload?.generation?.result_url || "";
      if (resultUrl) {
        setGeneratedImage(resultUrl);
      }
      setGenerateStatus(payload.message || messages.generateComplete, false);
      if (generationLog && payload.generation && !payload.reused) {
        const item = document.createElement("li");
        const provider = payload.generation.provider || "unknown";
        const ms = Number.isFinite(payload.generation.processing_ms)
          ? `${payload.generation.processing_ms}ms`
          : "";
        item.textContent = `${sourceLabel} · #${payload.generation.id} · ${payload.generation.status} · ${provider}${
          ms ? ` · ${ms}` : ""
        }`;
        generationLog.prepend(item);
      }
    } catch (error) {
      setGenerateStatus(error.message || messages.generateFailed, true);
    } finally {
      isGenerating = false;
      setGenerateLoading(false);
      setStyleStepEnabled(true);
    }
  }

  async function captureSelfieFromCamera() {
    if (!selfieVideo || isSelfieUploading) return;
    const started = await startCameraStream();
    if (!started || !cameraStream || !selfieVideo.videoWidth || !selfieVideo.videoHeight) {
      setStatus(messages.cameraDenied, true);
      stopCamera();
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = selfieVideo.videoWidth;
    canvas.height = selfieVideo.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(selfieVideo, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      async (blob) => {
        if (!blob) {
          stopCamera();
          return;
        }
        const selfieFile = new File([blob], `selfie-${Date.now()}.jpg`, { type: "image/jpeg" });
        await handleSelfieSelection(selfieFile, messages.selfieCaptured);
        stopCamera();
      },
      "image/jpeg",
      0.92
    );
  }

  if (cameraSelfieBlock) {
    cameraSelfieBlock.addEventListener("click", async () => {
      await captureSelfieFromCamera();
    });
  }

  if (selfieTakePhotoBtn) {
    selfieTakePhotoBtn.addEventListener("click", async () => {
      await captureSelfieFromCamera();
    });
  }

  if (selfieInput) {
    selfieInput.addEventListener("change", async () => {
      const file = selfieInput.files && selfieInput.files[0];
      if (!file) return;
      await handleSelfieSelection(file, messages.selfieSelected);
    });
  }

  if (selfieReplaceBtn) {
    selfieReplaceBtn.addEventListener("click", () => {
      hasSelfie = false;
      savedSelfieUrl = "";
      clearPendingSelfie();
      setSelfiePreview("");
      syncSelfieMode();
      setStatus(messages.selfieRetakeReady, false);
      if (typeof selfieUploadZone?.focus === "function") {
        selfieUploadZone.focus();
      }
    });
  }

  function handleHairStyleSelection(button) {
    selectedHairStyleId = button.dataset.styleId || "";
    selectedHairStyleName = button.dataset.styleName || "";
    setPressedState(hairStyleOptions, selectedHairStyleId, "styleId");
    updateSelectionStatus();
  }

  function handleHairColorSelection(button) {
    selectedHairColorId = button.dataset.colorId || "";
    selectedHairColorName = button.dataset.colorName || "";
    setPressedState(hairColorOptions, selectedHairColorId, "colorId");
    updateSelectionStatus();
  }

  function handleBeardStyleSelection(button) {
    selectedBeardStyleId = button.dataset.beardStyleId || "";
    selectedBeardStyleName = button.dataset.beardStyleName || "";
    if (selectedBeardStyleId === "none" && selectedBeardColorId && selectedBeardColorId !== "none") {
      const noneColorOption = beardColorOptions.find((option) => option.dataset.colorId === "none");
      selectedBeardColorId = "none";
      selectedBeardColorName = noneColorOption?.dataset.colorName || "Default";
      setPressedState(beardColorOptions, selectedBeardColorId, "colorId");
    }
    setPressedState(beardStyleOptions, selectedBeardStyleId, "beardStyleId");
    updateSelectionStatus();
  }

  function handleBeardColorSelection(button) {
    selectedBeardColorId = button.dataset.colorId || "";
    selectedBeardColorName = button.dataset.colorName || "";
    setPressedState(beardColorOptions, selectedBeardColorId, "colorId");
    updateSelectionStatus();
  }

  function initializeDefaultSelections() {
    const defaultHairStyle = hairStyleOptions.find((option) => option.dataset.styleId === "none");
    if (defaultHairStyle) {
      selectedHairStyleId = defaultHairStyle.dataset.styleId || "";
      selectedHairStyleName = defaultHairStyle.dataset.styleName || "Default";
      setPressedState(hairStyleOptions, selectedHairStyleId, "styleId");
    }

    const defaultHairColor = hairColorOptions.find((option) => option.dataset.colorId === "none");
    if (defaultHairColor) {
      selectedHairColorId = defaultHairColor.dataset.colorId || "";
      selectedHairColorName = defaultHairColor.dataset.colorName || "Default";
      setPressedState(hairColorOptions, selectedHairColorId, "colorId");
    }

    const defaultBeardStyle = beardStyleOptions.find((option) => option.dataset.beardStyleId === "none");
    if (defaultBeardStyle) {
      selectedBeardStyleId = defaultBeardStyle.dataset.beardStyleId || "";
      selectedBeardStyleName = defaultBeardStyle.dataset.beardStyleName || "Default";
      setPressedState(beardStyleOptions, selectedBeardStyleId, "beardStyleId");
    }

    const defaultBeardColor = beardColorOptions.find((option) => option.dataset.colorId === "none");
    if (defaultBeardColor) {
      selectedBeardColorId = defaultBeardColor.dataset.colorId || "";
      selectedBeardColorName = defaultBeardColor.dataset.colorName || "Default";
      setPressedState(beardColorOptions, selectedBeardColorId, "colorId");
    }
  }

  hairStyleOptions.forEach((button) => {
    button.addEventListener("click", () => handleHairStyleSelection(button));
  });

  hairColorOptions.forEach((button) => {
    button.addEventListener("click", () => handleHairColorSelection(button));
  });

  beardStyleOptions.forEach((button) => {
    button.addEventListener("click", () => handleBeardStyleSelection(button));
  });

  beardColorOptions.forEach((button) => {
    button.addEventListener("click", () => handleBeardColorSelection(button));
  });

  builderTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabKey = tab.dataset.builderTab;
      if (!tabKey) return;
      switchBuilderTab(tabKey);
    });
  });

  async function triggerGenerationRequest() {
    if (!hasSelfie) {
      setGenerateStatus(messages.selfieRequired, true);
      guideToSelfieStep();
      return;
    }

    if (!hasChosenLookStyle()) {
      setGenerateStatus(messages.generateCtaPrompt, true);
      styleStep?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    const validationError = getSelectionErrorMessage();
    if (validationError) {
      setGenerateStatus(validationError, true);
      if (styleSelectionStatus) {
        styleSelectionStatus.textContent = validationError;
        styleSelectionStatus.classList.add("warning-text");
      }
      styleStep?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    const formData = new FormData();
    formData.append("style_id", selectedHairStyleId === "none" ? "" : selectedHairStyleId);
    formData.append("hair_color_option_id", selectedHairColorId);
    formData.append("beard_style_id", selectedBeardStyleId);
    formData.append("beard_color_option_id", selectedBeardColorId);

    const hairLabel =
      selectedHairStyleId && selectedHairStyleId !== "none"
        ? selectedHairStyleName || "Hairstyle"
        : "No haircut change";
    const beardLabel = selectedBeardStyleId === "none" ? "No beard change" : selectedBeardStyleName || "Beard style";
    const sourceLabel = `${hairLabel} · ${selectedHairColorName || "Default"} · ${beardLabel} · ${selectedBeardColorName || "Default"}`;
    await submitGeneration(formData, sourceLabel);
  }

  if (selfieGenerateBtn) {
    selfieGenerateBtn.addEventListener("click", async () => {
      await triggerGenerationRequest();
    });
  }

  enableZoneKeyboardSupport(selfieUploadZone, selfieInput);
  attachDropzone(selfieUploadZone, selfieInput, async (file) => {
    await handleSelfieSelection(file, messages.selfieSelected);
  });

  window.addEventListener("beforeunload", () => {
    stopCamera();
    clearPendingPreview();
  });

  setUploadFilename(selfieUploadFilename, "");
  initializeDefaultSelections();
  applySelfieZoneState();
  syncSelfieMode();
  switchBuilderTab("hair");
  setStyleStepEnabled(true);
  updateSelfieControls();
  updateSelectionStatus();
})();
