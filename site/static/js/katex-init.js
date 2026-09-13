document.addEventListener("DOMContentLoaded", function () {
  renderMathInElement(document.querySelector(".markdown-body"), {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "$", right: "$", display: false }
    ]
  });
});