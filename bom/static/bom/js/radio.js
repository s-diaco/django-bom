const costInput = document.getElementById("id_unit_cost");
const costLabel =
  document.querySelector('label[for="id_unit_cost"]') ||
  (costInput && costInput.nextElementSibling);

// Product overhead is stored on ProductType, not seller unit_cost.
if (costLabel && costInput) {
  costLabel.innerText = costLabel.innerText;
}
