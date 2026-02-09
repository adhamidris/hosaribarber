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
    customStyleRequired:
      root.dataset.msgCustomStyleRequired || "Upload a custom haircut image first.",
    generateFailed: root.dataset.msgGenerateFailed || "Generation request failed.",
    generateStarted: root.dataset.msgGenerateStarted || "Generating preview...",
    generateComplete: root.dataset.msgGenerateComplete || "Preview is ready.",
  };

  const styleStep = document.getElementById("style-step");
  const selfieVideo = document.getElementById("selfie-video");
  const selfiePreview = document.getElementById("selfie-preview");
  const selfieStatus = document.getElementById("selfie-status");
  const selfieInput = document.getElementById("selfie-input");
  const openCameraBtn = document.getElementById("open-selfie-camera-btn");
  const captureSelfieBtn = document.getElementById("capture-selfie-btn");
  const retakeSelfieBtn = document.getElementById("retake-selfie-btn");
  const customStyleForm = document.getElementById("custom-style-form");
  const customStyleInput = document.getElementById("custom-style-input");
  const customStyleSubmitBtn = document.getElementById("custom-style-submit-btn");
  const generateLoader = document.getElementById("generate-loader");
  const generateStatus = document.getElementById("generate-status");
  const generatedResultImage = document.getElementById("generated-result-image");
  const generationLog = document.getElementById("generation-log");

  let hasSelfie = initialHasSelfie;
  let savedSelfieUrl = initialSelfieUrl;
  let pendingPreviewUrl = "";
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
    selfieStatus.textContent = message;
    selfieStatus.classList.toggle("warning-text", Boolean(isError));
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
      return;
    }
    generatedResultImage.src = url;
    generatedResultImage.classList.remove("hidden");
  }

  function setStyleStepEnabled(enabled) {
    if (styleStep) {
      styleStep.classList.toggle("is-disabled", !enabled);
    }
    root.querySelectorAll(".js-generate-style").forEach((button) => {
      button.disabled = !enabled || isGenerating;
    });
    if (customStyleInput) customStyleInput.disabled = !enabled || isGenerating;
    if (customStyleSubmitBtn) customStyleSubmitBtn.disabled = !enabled || isGenerating;
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
  }

  function updateSelfieControls() {
    if (openCameraBtn) openCameraBtn.disabled = isSelfieUploading;
    if (selfieInput) selfieInput.disabled = isSelfieUploading;
    if (captureSelfieBtn) {
      captureSelfieBtn.disabled = isSelfieUploading || !cameraStream;
    }
    if (retakeSelfieBtn) {
      const hasRetakeSource = Boolean(savedSelfieUrl || pendingPreviewUrl);
      retakeSelfieBtn.disabled = isSelfieUploading || !hasRetakeSource;
    }
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
    updateSelfieControls();
    setStyleStepEnabled(false);
    setStatus(messages.selfieUploading, false);

    try {
      const payload = await uploadSelfie(file);
      savedSelfieUrl = payload.selfie.url;
      hasSelfie = true;
      clearPendingSelfie();
      setSelfiePreview(savedSelfieUrl);
      setStyleStepEnabled(true);
      setStatus(messages.selfieSaved, false);
    } catch (error) {
      setStatus(error.message || messages.selfieSaveFailed, true);
      setStyleStepEnabled(hasSelfie);
    } finally {
      isSelfieUploading = false;
      updateSelfieControls();
    }
  }

  async function submitGeneration(formData, sourceLabel) {
    if (!hasSelfie) {
      setGenerateStatus(messages.selfieRequired, true);
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
      if (generationLog && payload.generation) {
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
      setStyleStepEnabled(hasSelfie);
    }
  }

  if (openCameraBtn && captureSelfieBtn && selfieVideo) {
    openCameraBtn.addEventListener("click", async () => {
      stopCamera();
      const attempts = [
        { video: { facingMode: { ideal: "user" } }, audio: false },
        { video: true, audio: false },
      ];
      let lastError = null;

      for (const constraints of attempts) {
        try {
          cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
          selfieVideo.srcObject = cameraStream;
          selfieVideo.classList.remove("hidden");
          updateSelfieControls();
          setStatus(messages.cameraOpened, false);
          return;
        } catch (error) {
          lastError = error;
        }
      }

      updateSelfieControls();
      setStatus(cameraErrorMessage(lastError), true);
    });
  }

  if (captureSelfieBtn && selfieVideo) {
    captureSelfieBtn.addEventListener("click", async () => {
      if (!cameraStream || !selfieVideo.videoWidth || !selfieVideo.videoHeight) {
        setStatus(messages.cameraDenied, true);
        return;
      }

      const canvas = document.createElement("canvas");
      canvas.width = selfieVideo.videoWidth;
      canvas.height = selfieVideo.videoHeight;
      const context = canvas.getContext("2d");
      context.drawImage(selfieVideo, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        async (blob) => {
          if (!blob) return;
          const selfieFile = new File([blob], `selfie-${Date.now()}.jpg`, { type: "image/jpeg" });
          clearPendingPreview();
          pendingPreviewUrl = URL.createObjectURL(selfieFile);
          setSelfiePreview(pendingPreviewUrl);
          setStatus(messages.selfieCaptured, false);
          await autoSaveSelfie(selfieFile);
        },
        "image/jpeg",
        0.92
      );
    });
  }

  if (retakeSelfieBtn) {
    retakeSelfieBtn.addEventListener("click", () => {
      clearPendingSelfie();
      setSelfiePreview(savedSelfieUrl);
      setStatus(messages.selfieRetakeReady, false);
    });
  }

  if (selfieInput) {
    selfieInput.addEventListener("change", async () => {
      const file = selfieInput.files && selfieInput.files[0];
      if (!file) return;
      clearPendingPreview();
      pendingPreviewUrl = URL.createObjectURL(file);
      setSelfiePreview(pendingPreviewUrl);
      setStatus(messages.selfieSelected, false);
      await autoSaveSelfie(file);
    });
  }

  root.querySelectorAll(".js-generate-style").forEach((button) => {
    button.addEventListener("click", async () => {
      const styleId = button.dataset.styleId;
      if (!styleId) return;
      const formData = new FormData();
      formData.append("style_id", styleId);
      const styleName =
        button.closest(".photo-item")?.querySelector("strong")?.textContent?.trim() || "Curated style";
      await submitGeneration(formData, styleName);
    });
  });

  if (customStyleForm && customStyleInput) {
    customStyleForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const file = customStyleInput.files && customStyleInput.files[0];
      if (!file) {
        setGenerateStatus(messages.customStyleRequired, true);
        return;
      }
      const formData = new FormData();
      formData.append("custom_style_image", file);
      await submitGeneration(formData, "Custom style");
      customStyleInput.value = "";
    });
  }

  window.addEventListener("beforeunload", () => {
    stopCamera();
    clearPendingPreview();
  });

  setSelfiePreview(savedSelfieUrl);
  setStyleStepEnabled(hasSelfie);
  updateSelfieControls();
})();
