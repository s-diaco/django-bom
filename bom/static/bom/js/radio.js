const costLabel = document.getElementById('id_unit_cost').nextElementSibling;
const sellerName = document.getElementById('id_name');
const noBomTxt = document.getElementById('labelNoBom').innerText;
const wBomTxt = document.getElementById('labelWithBom').innerText;
const currencyTxt = document.getElementById('currencyText').innerText;
const organizationTxt = document.getElementById('organizationName').innerText;

function handleRadioClick() {
  currentElement = document.activeElement
  if (document.getElementById('id_material_2').checked) {
    costLabel.innerText = noBomTxt + ' | ' + currencyTxt;
    sellerName.focus();
    sellerName.value = "";
    currentElement.focus();
  } else {
    costLabel.innerText = wBomTxt + ' | ' + currencyTxt;
    sellerName.focus();
    sellerName.value = organizationTxt;
    currentElement.focus();
  }
}

const radioButtons = document.querySelectorAll(
  'input[name="material"]',
);
radioButtons.forEach(radio => {
  radio.addEventListener('click', handleRadioClick);
});
