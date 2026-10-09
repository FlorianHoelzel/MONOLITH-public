const params = new URLSearchParams(window.location.search);
const target = params.get("target");

document.querySelector("#retry").addEventListener("click", () => {
  if (target) {
    window.location.assign(target);
  }
});
