(function () {
  function setFieldVisibility(form, classification) {
    const wrappers = form.querySelectorAll("[data-visible-for]");
    wrappers.forEach((wrapper) => {
      const visibleFor = wrapper.getAttribute("data-visible-for");
      const shouldShow = visibleFor === "all" || visibleFor === classification;
      wrapper.hidden = !shouldShow;

      const controls = wrapper.querySelectorAll("input, select, textarea");
      controls.forEach((control) => {
        control.disabled = !shouldShow;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("appointment-entry-modal");
    if (!modal) return;

    const form = modal.querySelector("form");
    const classificationField = form ? form.querySelector('select[name="classification"]') : null;
    const phoneField = form ? form.querySelector('input[name="phone"]') : null;
    const fullNameField = form ? form.querySelector('input[name="full_name"]') : null;
    const serviceFields = form ? form.querySelectorAll('input[name="services"]') : [];
    const selectedServicesCount = form ? form.querySelector(".js-selected-services-count") : null;
    const finalPriceEl = form ? form.querySelector(".js-final-price") : null;
    const lookupHint = form ? form.querySelector(".js-phone-lookup-hint") : null;
    const lookupUrl = form ? form.dataset.clientLookupUrl : "";
    const clientFoundMessage = form ? form.dataset.clientFoundMessage : "";
    const clientMissingMessage = form ? form.dataset.clientMissingMessage : "";
    let lookupTimer = null;
    let lookupRequestId = 0;

    function openModal() {
      modal.classList.add("is-open");
      document.body.classList.add("modal-open");
      if (classificationField) {
        setFieldVisibility(form, classificationField.value || "booking");
      }
    }

    function closeModal() {
      modal.classList.remove("is-open");
      document.body.classList.remove("modal-open");
    }

    function setLookupHint(text) {
      if (!lookupHint) return;
      lookupHint.textContent = text || "";
    }

    function clearAutofilledName() {
      if (!fullNameField || fullNameField.dataset.autofilled !== "1") return;
      fullNameField.value = "";
      delete fullNameField.dataset.autofilled;
    }

    function updateSelectedServicesSummary() {
      if (!serviceFields.length) return;
      let count = 0;
      let total = 0;
      serviceFields.forEach((checkbox) => {
        if (!checkbox.checked) return;
        count += 1;
        const servicePrice = Number.parseFloat(checkbox.dataset.servicePrice || "0");
        if (Number.isFinite(servicePrice)) {
          total += servicePrice;
        }
      });

      if (selectedServicesCount) {
        selectedServicesCount.textContent = String(count);
      }
      if (finalPriceEl) {
        finalPriceEl.textContent = total.toFixed(2);
      }
    }

    async function lookupClientByPhone(phoneValue) {
      if (!phoneValue) {
        clearAutofilledName();
        setLookupHint("");
        return;
      }

      if (!lookupUrl || !classificationField || classificationField.value !== "booking") {
        setLookupHint("");
        return;
      }

      lookupRequestId += 1;
      const requestId = lookupRequestId;
      try {
        const response = await fetch(`${lookupUrl}?phone=${encodeURIComponent(phoneValue)}`);
        if (!response.ok || requestId !== lookupRequestId) return;
        const payload = await response.json();
        if (requestId !== lookupRequestId) return;

        if (payload.exists) {
          if (fullNameField) {
            fullNameField.value = payload.full_name || "";
            fullNameField.dataset.autofilled = "1";
          }
          setLookupHint(clientFoundMessage);
          return;
        }

        clearAutofilledName();
        setLookupHint(clientMissingMessage);
      } catch (_error) {
        if (requestId === lookupRequestId) {
          setLookupHint("");
        }
      }
    }

    const openButtons = document.querySelectorAll('[data-modal-open="appointment-entry-modal"]');
    openButtons.forEach((button) => {
      button.addEventListener("click", openModal);
    });

    const closeButtons = modal.querySelectorAll("[data-modal-close]");
    closeButtons.forEach((button) => {
      button.addEventListener("click", closeModal);
    });

    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        closeModal();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && modal.classList.contains("is-open")) {
        closeModal();
      }
    });

    if (classificationField) {
      classificationField.addEventListener("change", (event) => {
        setFieldVisibility(form, event.target.value || "booking");
        if (phoneField) {
          lookupClientByPhone((phoneField.value || "").trim());
        }
      });
      setFieldVisibility(form, classificationField.value || "booking");
    }

    if (phoneField) {
      phoneField.addEventListener("input", () => {
        if (lookupTimer) {
          clearTimeout(lookupTimer);
        }
        lookupTimer = setTimeout(() => {
          lookupClientByPhone((phoneField.value || "").trim());
        }, 220);
      });
      phoneField.addEventListener("blur", () => {
        lookupClientByPhone((phoneField.value || "").trim());
      });
    }

    if (serviceFields.length) {
      serviceFields.forEach((checkbox) => {
        checkbox.addEventListener("change", updateSelectedServicesSummary);
      });
      updateSelectedServicesSummary();
    }

    if (modal.classList.contains("is-open")) {
      document.body.classList.add("modal-open");
      if (phoneField) {
        lookupClientByPhone((phoneField.value || "").trim());
      }
      updateSelectedServicesSummary();
    }
  });
})();
