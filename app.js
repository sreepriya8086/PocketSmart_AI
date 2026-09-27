document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('input[type="file"]').forEach(input => {
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file && file.size > 8 * 1024 * 1024) {
        alert("Please choose an image smaller than 8 MB.");
        input.value = "";
      }
    });
  });
});
