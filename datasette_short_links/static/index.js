async function main() {
  const BASE_URL = window.DATASETTE_SHORT_LINKS_BASE_URL;
  const SKIP_BUTTON = window.DATASETTE_SHORT_LINKS_SKIP_BUTTON;

  if (SKIP_BUTTON) return;
  const button = document.createElement("button");
  button.innerText = "Copy URL";
  async function onClick() {
    const response = await fetch(`${BASE_URL}-/datasette-short-links/claim`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        path: window.location.pathname,
        querystring: window.location.search,
      }),
    });
    const data = await response.json();
    const url = window.location.origin + data.url_path;
    navigator.clipboard.writeText(url).then(() => {
      button.innerText = "Copied!";
      setTimeout(() => (button.innerText = "Copy URL"), 1000);
    });
  }
  button.addEventListener("click", onClick);
  document.querySelector("footer").appendChild(button);
}
document.addEventListener("DOMContentLoaded", main);
