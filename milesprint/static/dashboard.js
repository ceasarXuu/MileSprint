const rows = document.querySelector("#devices");
const status = document.querySelector("#refresh-status");
let timer;
let inFlight = false;
let delay = 5000;

async function refresh() {
  clearTimeout(timer);
  if (document.hidden || inFlight) return;
  inFlight = true;
  try {
    const response = await fetch("/dashboard/rows", {
      headers: { "If-None-Match": rows.dataset.etag },
      signal: AbortSignal.timeout(4000),
    });
    if (response.status !== 304) {
      if (!response.ok) throw new Error("Refresh failed");
      rows.innerHTML = await response.text();
      rows.dataset.etag = response.headers.get("ETag");
    }
    status.textContent = "";
    delay = 5000;
  } catch {
    status.textContent = "更新暂时中断，正在显示上次的数据。";
    delay = Math.min(delay * 2, 60000);
  } finally {
    inFlight = false;
    if (!document.hidden) timer = setTimeout(refresh, delay);
  }
}

document.addEventListener("visibilitychange", refresh);
if (!document.hidden) timer = setTimeout(refresh, delay);
