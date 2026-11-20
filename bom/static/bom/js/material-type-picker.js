(function initMaterialTypePickers() {
  function setup(root) {
    if (!root || root.dataset.pickerReady === "1") {
      return;
    }
    root.dataset.pickerReady = "1";

    const kindBtns = root.querySelectorAll("[data-kind].bom-type-picker-kind-btn");
    const thumb = root.querySelector("[data-kind-thumb]");
    const subtypes = root.querySelector("[data-subtypes]");
    const options = Array.from(
      root.querySelectorAll(".bom-type-picker-option[data-kind]")
    );

    function radiosFor(kind) {
      return options.filter((el) => el.getAttribute("data-kind") === kind);
    }

    function checkedRadio() {
      return root.querySelector('input[name="material"]:checked');
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
      options.forEach((el) => {
        const match = el.getAttribute("data-kind") === kind;
        el.hidden = !match;
        el.classList.toggle("is-visible", match);
      });

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
    }

    kindBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        setKind(btn.getAttribute("data-kind"), { user: true });
      });
    });

    const initial =
      root.dataset.selectedKind ||
      (checkedRadio() && checkedRadio().getAttribute("data-kind")) ||
      "product";
    setKind(initial, { user: false });
  }

  document.querySelectorAll("[data-bom-type-picker]").forEach(setup);
})();
