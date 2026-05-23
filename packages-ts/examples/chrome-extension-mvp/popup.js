// Popup script — UI for the TS-W1 smoke extension.
// Sends a `research` message to the service worker and renders the result.

const today = new Date();
const week = new Date(today.getTime() - 6 * 86_400_000);
const iso = (d) => d.toISOString().slice(0, 10);

document.getElementById("from").value = iso(week);
document.getElementById("to").value = iso(today);

document.getElementById("go").addEventListener("click", async () => {
  const station = document.getElementById("station").value.trim();
  const fromDate = document.getElementById("from").value;
  const toDate = document.getElementById("to").value;
  const out = document.getElementById("out");
  out.textContent = "Loading…";
  try {
    const reply = await chrome.runtime.sendMessage({
      type: "research",
      station,
      fromDate,
      toDate,
    });
    if (reply?.ok) {
      out.textContent = JSON.stringify(reply.rows, null, 2);
    } else {
      out.textContent = `Error: ${reply?.error ?? "no reply"}`;
    }
  } catch (err) {
    out.textContent = `Error: ${err?.message ?? String(err)}`;
  }
});
