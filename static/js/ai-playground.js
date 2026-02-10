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
  const selfieInput = document.getElementById("selfie-input");
  const selfieUploadZone = document.getElementById("selfie-upload-zone");
  const selfieUploadFilename = document.getElementById("selfie-upload-filename");
  const hairStyleOptions = Array.from(root.querySelectorAll(".js-hair-style-option"));
  const hairColorOptions = Array.from(root.querySelectorAll(".js-hair-color-option"));
  const beardStyleOptions = Array.from(root.querySelectorAll(".js-beard-style-option"));
  const beardColorOptions = Array.from(root.querySelectorAll(".js-beard-color-option"));
  const styleGenerateBtn = document.getElementById("style-generate-btn");
  const styleSelectionStatus = document.getElementById("style-selection-status");
  const defaultSelectionStatusText = (styleSelectionStatus?.textContent || "").trim();
  const selectedHairReferenceImage = document.getElementById("selected-hair-reference-image");
  const selectedHairReferenceLabel = document.getElementById("selected-hair-reference-label");
  const selectedBeardReferenceImage = document.getElementById("selected-beard-reference-image");
  const selectedBeardReferenceLabel = document.getElementById("selected-beard-reference-label");
  const defaultHairReferenceLabel = (selectedHairReferenceLabel?.textContent || "No hairstyle selected.").trim();
  const defaultBeardReferenceLabel = (selectedBeardReferenceLabel?.textContent || "No beard style selected.").trim();
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
  let selectedHairStyleImageUrl = "";
  let selectedHairColorId = "";
  let selectedHairColorName = "";
  let selectedBeardStyleId = "";
  let selectedBeardStyleName = "";
  let selectedBeardStyleImageUrl = "";
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
    [...hairStyleOptions, ...hairColorOptions, ...beardStyleOptions, ...beardColorOptions].forEach((button) => {
      button.disabled = isDisabled;
      button.setAttribute("aria-disabled", isDisabled ? "true" : "false");
    });
    if (styleGenerateBtn) {
      styleGenerateBtn.disabled = isDisabled;
      styleGenerateBtn.setAttribute("aria-disabled", isDisabled ? "true" : "false");
    }
  }

  function setPressedState(options, selectedValue, valueKey) {
    options.forEach((option) => {
      const isSelected = option.dataset[valueKey] === selectedValue;
      option.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
  }

  function setSelectedReference(imageEl, labelEl, imageUrl, labelText, emptyLabel) {
    if (imageEl) {
      imageEl.classList.toggle("hidden", !imageUrl);
      imageEl.src = imageUrl || "";
    }
    if (labelEl) {
      labelEl.textContent = labelText || emptyLabel;
    }
  }

  function getSelectionErrorMessage() {
    if (!selectedHairStyleId) return messages.hairStyleRequired;
    if (!selectedHairColorId) return messages.hairColorRequired;
    if (!selectedBeardStyleId) return messages.beardStyleRequired;
    if (!selectedBeardColorId) return messages.beardColorRequired;
    if (selectedBeardStyleId === "none" && selectedBeardColorId !== "none") {
      return messages.beardColorNeedsStyle;
    }
    return "";
  }

  function updateSelectionStatus() {
    if (!styleSelectionStatus) return;
    const errorMessage = getSelectionErrorMessage();
    if (errorMessage) {
      styleSelectionStatus.textContent =
        defaultSelectionStatusText || "Select hairstyle, hair color, beard style, and beard color.";
      styleSelectionStatus.classList.remove("warning-text");
      return;
    }
    const beardSummary =
      selectedBeardStyleId === "none"
        ? "No beard change"
        : `${selectedBeardStyleName || "Beard"} · ${selectedBeardColorName || "No color"}`;
    styleSelectionStatus.textContent = `${selectedHairStyleName || "Hairstyle"} · ${selectedHairColorName || "No color"} · ${beardSummary}`;
    styleSelectionStatus.classList.remove("warning-text");
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
    selectedHairStyleImageUrl = button.dataset.styleImageUrl || "";
    setPressedState(hairStyleOptions, selectedHairStyleId, "styleId");
    setSelectedReference(
      selectedHairReferenceImage,
      selectedHairReferenceLabel,
      selectedHairStyleImageUrl,
      selectedHairStyleName,
      defaultHairReferenceLabel
    );
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
    selectedBeardStyleImageUrl = button.dataset.styleImageUrl || "";
    if (selectedBeardStyleId === "none" && selectedBeardColorId && selectedBeardColorId !== "none") {
      const noneColorOption = beardColorOptions.find((option) => option.dataset.colorId === "none");
      selectedBeardColorId = "none";
      selectedBeardColorName = noneColorOption?.dataset.colorName || "No color";
      setPressedState(beardColorOptions, selectedBeardColorId, "colorId");
    }
    setPressedState(beardStyleOptions, selectedBeardStyleId, "beardStyleId");
    setSelectedReference(
      selectedBeardReferenceImage,
      selectedBeardReferenceLabel,
      selectedBeardStyleId === "none" ? "" : selectedBeardStyleImageUrl,
      selectedBeardStyleName,
      defaultBeardReferenceLabel
    );
    updateSelectionStatus();
  }

  function handleBeardColorSelection(button) {
    selectedBeardColorId = button.dataset.colorId || "";
    selectedBeardColorName = button.dataset.colorName || "";
    setPressedState(beardColorOptions, selectedBeardColorId, "colorId");
    updateSelectionStatus();
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

  if (styleGenerateBtn) {
    styleGenerateBtn.addEventListener("click", async () => {
      if (!hasSelfie) {
        setGenerateStatus(messages.selfieRequired, true);
        guideToSelfieStep();
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
      formData.append("style_id", selectedHairStyleId);
      formData.append("hair_color_option_id", selectedHairColorId);
      formData.append("beard_style_id", selectedBeardStyleId);
      formData.append("beard_color_option_id", selectedBeardColorId);

      const beardLabel = selectedBeardStyleId === "none" ? "No beard change" : selectedBeardStyleName;
      const sourceLabel = `${selectedHairStyleName} · ${selectedHairColorName} · ${beardLabel} · ${selectedBeardColorName}`;
      await submitGeneration(formData, sourceLabel);
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
  applySelfieZoneState();
  syncSelfieMode();
  setStyleStepEnabled(true);
  updateSelfieControls();
  setSelectedReference(
    selectedHairReferenceImage,
    selectedHairReferenceLabel,
    "",
    "",
    defaultHairReferenceLabel
  );
  setSelectedReference(
    selectedBeardReferenceImage,
    selectedBeardReferenceLabel,
    "",
    "",
    defaultBeardReferenceLabel
  );
  updateSelectionStatus();
})();
