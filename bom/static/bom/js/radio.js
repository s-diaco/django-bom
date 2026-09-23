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
  const orgName = form.dataset.organizationName || "";
  const loiRow = document.getElementById("create-part-loi-row");
  const sellerIdentity = document.getElementById("create-part-seller-identity");
  const toleranceInput = document.getElementById("id_tolerance");
  const sellerNameInput = document.getElementById("id_name");
  const sellerPartNumberInput = document.getElementById("id_seller_part_number");
  const codeInput = document.getElementById("id_number_item");
  const materialRadios = form.querySelectorAll('input[name="material"]');

  function selectedMaterial() {
    const checked = form.querySelector('input[name="material"]:checked');
    return checked ? checked.value : "";
  }

  function isRawMaterial(code) {
    return rawCodes.indexOf(code) !== -1;
  }

  function applyToggles() {
    const raw = isRawMaterial(selectedMaterial());

    if (loiRow) {
      loiRow.style.display = raw ? "" : "none";
      if (!raw && toleranceInput) {
        toleranceInput.value = "0";
      }
    }

    if (sellerIdentity) {
      sellerIdentity.style.display = raw ? "" : "none";
      if (!raw) {
        if (sellerNameInput) {
          sellerNameInput.value = orgName;
        }
        if (sellerPartNumberInput && codeInput) {
          sellerPartNumberInput.value = codeInput.value;
        }
      }
    }
  }

  materialRadios.forEach((radio) => {
    radio.addEventListener("change", applyToggles);
  });

  if (codeInput) {
    codeInput.addEventListener("input", () => {
      if (!isRawMaterial(selectedMaterial()) && sellerPartNumberInput) {
        sellerPartNumberInput.value = codeInput.value;
      }
    });
  }

  applyToggles();
})();
