(() => {
  const code = (location.pathname.split("/").pop() || "").toUpperCase();
  const $ = (id) => document.getElementById(id);
  const messagesEl = $("messages");
  const inputEl = $("input");
  const typingEl = $("typing");
  const toastEl = $("toast");
  const quickBar = $("quickBar");

  const name = (localStorage.getItem("ts_name") || "").trim().slice(0, 12) || "汤友";
  const pidKey = `ts_pid_${code}`;
  const pid = localStorage.getItem(pidKey) || "";
  let ws = null;
  let me = { pid, name, is_host: false };
  let game = null;
  let pingTimer = null;
  let reconnectDelay = 1000;
  let closedByUser = false;

  $("roomCode").textContent = code;

  function wsUrl() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const params = new URLSearchParams();
    if (me.pid) params.set("pid", me.pid);
    params.set("name", me.name);
    return `${proto}://${location.host}/ws/${code}?${params.toString()}`;
  }

  function connect() {
    ws = new WebSocket(wsUrl());

    ws.onopen = () => {
      reconnectDelay = 1000;
      startPing();
    };

    ws.onmessage = (ev) => {
      let data;
      try { data = JSON.parse(ev.data); } catch { return; }
      handle(data);
    };

    ws.onclose = () => {
      stopPing();
      if (closedByUser) return;
      appendLocalSystem("连接断开，重连中…");
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 1.6, 8000);
    };

    ws.onerror = () => {};
  }

  function startPing() {
    stopPing();
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
    }, 25000);
  }

  function stopPing() {
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = null;
  }

  function handle(data) {
    switch (data.type) {
      case "init":
        me = data.you;
        if (me.pid) localStorage.setItem(pidKey, me.pid);
        game = data.game;
        if (!data.llm) appendLocalSystem("⚠️ 服务器未配置 LLM，暂时无法出题");
        (data.history || []).forEach(renderMessage);
        renderPlayers(data.players || []);
        renderQuickBar();
        break;
      case "players":
        renderPlayers(data.players || []);
        break;
      case "msg":
        renderMessage(data);
        break;
      case "game":
        game = data.game;
        renderQuickBar();
        break;
      case "typing":
        typingEl.classList.toggle("hidden", !data.on);
        break;
      case "fatal":
        appendLocalSystem(data.text || "发生错误");
        break;
      default:
        break;
    }
  }

  function renderPlayers(players) {
    const bar = $("playersBar");
    bar.innerHTML = "";
    const online = players.filter((p) => p.online).length;
    $("onlineCount").textContent = String(online);
    players.forEach((p) => {
      const tag = document.createElement("span");
      tag.className = "player-tag" + (p.online ? "" : " offline");
      tag.textContent = (p.is_host ? "👑 " : "") + p.name + (p.pid === me.pid ? "（我）" : "");
      bar.appendChild(tag);
    });
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function renderMessage(m) {
    const row = document.createElement("div");
    row.className = `msg ${m.role || "player"}`;
    if (m.role === "system") {
      row.innerHTML = `<div class="bubble system">${esc(m.text)}</div>`;
    } else {
      const mine = m.role === "player" && m.name === me.name;
      row.classList.toggle("mine", mine);
      row.innerHTML = `
        <div class="meta">${m.role === "bot" ? "🍲 " : ""}${esc(m.name || "")}</div>
        <div class="bubble">${esc(m.text)}</div>`;
    }
    messagesEl.appendChild(row);
    scrollBottom();
  }

  function appendLocalSystem(text) {
    renderMessage({ role: "system", text });
  }

  function scrollBottom() {
    requestAnimationFrame(() => { messagesEl.scrollTop = messagesEl.scrollHeight; });
  }

  function toast(text) {
    toastEl.textContent = text;
    toastEl.classList.remove("hidden");
    setTimeout(() => toastEl.classList.add("hidden"), 1800);
  }

  function send(text) {
    if (!text) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "say", text }));
    } else {
      toast("连接中，请稍后");
    }
  }

  function renderQuickBar() {
    quickBar.innerHTML = "";
    const active = game && game.active;
    const buttons = active
      ? [
          { label: "提问", prefix: "提问 " },
          { label: "猜汤底", prefix: "猜汤底 " },
          { label: "提示", send: "提示" },
          { label: "汤面", send: "汤面" },
          { label: "揭晓", send: "揭晓" },
          { label: "结束", send: "结束" },
        ]
      : [{ label: "🫕 开一锅", send: "开汤" }];

    buttons.forEach((b) => {
      const btn = document.createElement("button");
      btn.className = "chip";
      btn.textContent = b.label;
      btn.onclick = () => {
        if (b.prefix) {
          inputEl.value = b.prefix;
          inputEl.focus();
        } else {
          send(b.send);
        }
      };
      quickBar.appendChild(btn);
    });
  }

  $("sendBtn").onclick = () => {
    const text = (inputEl.value || "").trim();
    if (!text) return;
    send(text);
    inputEl.value = "";
    inputEl.focus();
  };

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("sendBtn").click();
  });

  $("shareBtn").onclick = async () => {
    const url = location.href;
    try {
      await navigator.clipboard.writeText(url);
      toast("链接已复制，去群里粘贴吧");
    } catch {
      prompt("复制链接分享到群里：", url);
    }
  };

  $("playersBtn").onclick = () => {
    $("playersBar").classList.toggle("expand");
  };

  connect();
})();
