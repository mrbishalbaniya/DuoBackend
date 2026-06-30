(function () {
  function toggleSecretField(button) {
    const input = document.getElementById(button.dataset.target);
    if (!input) return;

    const show = input.type === "password";
    input.type = show ? "text" : "password";

    const icon = button.querySelector("i");
    if (icon) {
      icon.classList.toggle("fa-eye", !show);
      icon.classList.toggle("fa-eye-slash", show);
    }

    const label = button.querySelector(".duo-secret-toggle-label");
    if (label) {
      label.textContent = show ? "Hide" : "Show";
    }

    button.setAttribute("aria-label", show ? "Hide value" : "Show value");
  }

  document.addEventListener("click", function (event) {
    const button = event.target.closest(".duo-secret-toggle");
    if (!button) return;
    event.preventDefault();
    toggleSecretField(button);
  });
})();
