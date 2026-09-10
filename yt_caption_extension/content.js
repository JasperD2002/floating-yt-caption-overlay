// Content script - runs on YouTube pages
// Reads captions and sends them to the background service worker

function log(msg) { console.log("[CaptionOverlay:content]", msg); }

let lastSent = "";

function poll() {
  const selectors = [
    ".ytp-caption-segment",
    ".captions-text span",
    ".caption-window-text span",
    "[class*='caption'] [class*='segment']",
  ];
  let text = "";
  for (const sel of selectors) {
    const segs = document.querySelectorAll(sel);
    if (segs.length) {
      text = Array.from(segs).map(s => s.textContent.trim()).filter(Boolean).join(" ");
      if (text) break;
    }
  }
  if (text && text !== lastSent) {
    lastSent = text;
    chrome.runtime.sendMessage({ type: "caption", text }).catch(() => {});
    log("Sent: " + text);
  }
}

setInterval(poll, 300);
log("Content script loaded");
