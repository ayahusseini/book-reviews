document.addEventListener("DOMContentLoaded", function () {
  renderMathInElement(document.querySelector(".post-content"), {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "$", right: "$", display: false }
    ]
  });
});