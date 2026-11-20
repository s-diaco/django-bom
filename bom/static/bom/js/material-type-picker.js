(function initMaterialTypePickers() {
  function setup(root) {
    if (!root || root.dataset.pickerReady === "1") {
      return;
    }
    root.dataset.pickerReady = "1";

    const kindBtns = root.querySelectorAll("[data-kind].bom-type-picker-kind-btn");
    const thumb = root.querySelector("[data-kind-thumb]");
    const subtypes = root.querySelector("[data-subtypes]");
    const select = root.querySelector("[data-subtype-select]");
    const options = Array.from(
      root.querySelectorAll(".bom-type-picker-option[data-kind]")
    );

    function radiosFor(kind) {
      return options.filter((el) => el.getAttribute("data-kind") === kind);
    }

    function checkedRadio() {
      return root.querySelector('input[name="material"]:checked');
    }

    function syncSelect(kind) {
      if (!select) {
        return;
      }
      const visible = radiosFor(kind);
      select.replaceChildren();
      visible.forEach((el) => {
        const input = el.querySelector('input[type="radio"]');
        if (!input) {
          return;
        }
        const opt = document.createElement("option");
        opt.value = input.value;
        opt.textContent = (
          el.querySelector(".bom-type-picker-option-label") || el
        ).textContent.trim();
        if (input.checked) {
          opt.selected = true;
        }
        select.appendChild(opt);
      });
      const checked = checkedRadio();
      if (checked && checked.getAttribute("data-kind") === kind) {
        select.value = checked.value;
      } else if (select.options.length) {
        select.selectedIndex = 0;
      }
    }

    function setKind(kind, { user } = {}) {
      root.dataset.selectedKind = kind;
      if (thumb) {
        thumb.dataset.at = kind;
      }
      kindBtns.forEach((btn) => {
        btn.setAttribute(
          "aria-pressed",
          btn.getAttribute("data-kind") === kind ? "true" : "false"
        );
      });

      const visible = radiosFor(kind);

      // One subtype: kind alone is enough (progressive disclosure).
      if (subtypes) {
        const show = visible.length > 1;
        subtypes.hidden = !show;
        subtypes.classList.toggle("is-open", show);
      }

      const checked = checkedRadio();
      const checkedKind = checked && checked.getAttribute("data-kind");
      if (!checked || checkedKind !== kind) {
        const first = visible[0] && visible[0].querySelector('input[type="radio"]');
        if (first) {
          first.checked = true;
          if (user) {
            first.dispatchEvent(new Event("change", { bubbles: true }));
          }
        }
      } else if (user && checked) {
        checked.dispatchEvent(new Event("change", { bubbles: true }));
      }

      syncSelect(kind);
    }

    kindBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        setKind(btn.getAttribute("data-kind"), { user: true });
      });
    });

    if (select) {
      select.addEventListener("change", () => {
        const radio = root.querySelector(
          'input[name="material"][value="' +
            CSS.escape(select.value) +
            '"]'
        );
        if (!radio) {
          return;
        }
        radio.checked = true;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      });
    }

    const initial =
      root.dataset.selectedKind ||
      (checkedRadio() && checkedRadio().getAttribute("data-kind")) ||
      "product";
    setKind(initial, { user: false });
  }

  document.querySelectorAll("[data-bom-type-picker]").forEach(setup);
})();
