const costInput = document.getElementById("id_unit_cost");
const costLabel =
  document.querySelector('label[for="id_unit_cost"]') ||
  (costInput && costInput.nextElementSibling);

// Product overhead is stored on ProductType, not seller unit_cost.
if (costLabel && costInput) {
  costLabel.innerText = costLabel.innerText;
}

(function initCreatePartToggles() {
  const form = document.querySelector("form[data-create-part-toggles]");
  if (!form) {
    return;
  }

  const rawCodes = (form.dataset.rawMaterialCodes || "")
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);
  const loiRow = document.getElementById("create-part-loi-row");
  const sellerSection = document.getElementById("create-part-seller-section");
  const toleranceInput = document.getElementById("id_tolerance");
  const codeInput = document.getElementById("id_number_item");
  const manufacturerPartNumberInput = document.getElementById(
    "id_manufacturer_part_number"
  );
  const manufacturerNameInput = document.getElementById("id_mfg-name");
  const orgName = form.dataset.organizationName || "";
  const materialRadios = form.querySelectorAll('input[name="material"]');

  function selectedMaterial() {
    const checked = form.querySelector('input[name="material"]:checked');
    return checked ? checked.value : "";
  }

  function isRawMaterial(code) {
    return rawCodes.indexOf(code) !== -1;
  }

  function syncManufacturerDefaults() {
    if (isRawMaterial(selectedMaterial())) {
      return;
    }
    if (manufacturerPartNumberInput && codeInput) {
      manufacturerPartNumberInput.value = codeInput.value;
    }
    if (manufacturerNameInput) {
      manufacturerNameInput.value = orgName;
    }
  }

  function applyToggles() {
    const raw = isRawMaterial(selectedMaterial());

    if (loiRow) {
      loiRow.style.display = raw ? "" : "none";
      if (!raw && toleranceInput) {
        toleranceInput.value = "0";
      }
    }

    // Non-raw: no seller/price — cost is calculated from BoM.
    if (sellerSection) {
      sellerSection.style.display = raw ? "" : "none";
    }

    syncManufacturerDefaults();
  }

  materialRadios.forEach((radio) => {
    radio.addEventListener("change", applyToggles);
  });

  if (codeInput) {
    codeInput.addEventListener("input", syncManufacturerDefaults);
  }

  applyToggles();
})();
