// Background service worker - maintains WebSocket connection to Python overlay
// Receives captions from content script and forwards them

let WS = null;
let RECONNECT_DELAY = 2000;

function log(msg) { console.log("[CaptionOverlay:bg]", msg); }

function connect() {
  if (WS && (WS.readyState === WebSocket.OPEN || WS.readyState === WebSocket.CONNECTING)) return;

  try {
    log("Connecting to ws://127.0.0.1:9876 ...");
    WS = new WebSocket("ws://127.0.0.1:9876");
  } catch (e) {
    log("Failed: " + e.message);
    scheduleReconnect();
    return;
  }

  WS.onopen = () => {
    log("Connected");
    WS.send(JSON.stringify({ type: "hello" }));
  };

  WS.onclose = (e) => {
    log("Disconnected (code=" + e.code + ")");
    WS = null;
    scheduleReconnect();
  };

  WS.onerror = () => {
    log("Error");
  };
}

function scheduleReconnect() {
  setTimeout(connect, RECONNECT_DELAY);
}

// Listen for captions from content scripts
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === "caption" && WS && WS.readyState === WebSocket.OPEN) {
    WS.send(JSON.stringify(msg));
  }
});

// Keep service worker alive with a periodic task
setInterval(() => {
  if (WS && WS.readyState === WebSocket.OPEN) {
    WS.send(JSON.stringify({ type: "ping" }));
  }
}, 20000);

connect();
log("Service worker started");
