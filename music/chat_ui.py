


#
#
#暂时不行
#
#








import asyncio
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# 这一行的路径，根据你的 openagents 版本可能略有不同
from openagents.client.agent_client import AgentClient

app = FastAPI()

# 全局 client + 一个简单的队列，存 alex 的回复
client: Optional[AgentClient] = None
reply_queue: "asyncio.Queue[str]" = asyncio.Queue()


class ChatRequest(BaseModel):
    message: str


# ========== 连接 OpenAgents 网络，并监听 alex 的回复 ==========

async def run_openagents_client():
    """
    作为一个“人类客户端”连到你的网络，监听 alex 在 general 频道里的消息。
    """
    global client
    client = AgentClient()

    # 1. 连接到网络
    # host/port 要和你 NetworkConfig 里的 grpc 或 http 配置对应
    await client.connect(
        host="127.0.0.1",
        port=8600,             # 例如：你的 gRPC 端口，如果是 HTTP，要改成对应写法
        agent_id="web-ui",     # 给这个前端客户端起个 ID
    )

    # 2. 加入 workspace，名字要和你网络里的一致（一般是 "main" 或 "default"）
    await client.join_workspace("main")

    # 3. 定义收到消息时的回调
    async def handle_message(message):
        """
        所有从网络来的消息都会经过这里。
        我们只关心 alex 在 general 频道里的聊天消息。
        """
        try:
            msg_type = getattr(message, "type", "")
            sender_id = getattr(message, "sender_id", "")
            channel = getattr(message, "channel", "") or getattr(
                message, "target_channel", ""
            )

            # 只收 alex 在 general 发的频道消息
            if msg_type != "channel_message":
                return
            if sender_id != "alex":
                return
            if channel not in ("general", "#general"):
                return

            text = None

            # 内容可能在 content 或 payload 里
            content = getattr(message, "content", None)
            if isinstance(content, str):
                text = content
            elif isinstance(content, dict):
                text = (
                    content.get("text")
                    or content.get("content")
                    or content.get("message")
                )

            if text is None:
                payload = getattr(message, "payload", None)
                if isinstance(payload, dict):
                    text = (
                        payload.get("text")
                        or payload.get("content")
                        or payload.get("message")
                    )

            if not text:
                text = "[收到 alex 的消息，但未能解析文本内容]"

            await reply_queue.put(text)

        except Exception as e:
            print("handle_message error:", e)

    # 注册回调，开始监听
    client.on_message = handle_message
    print("✅ Web UI client 已连接到 OpenAgents 网络，开始 listen()")
    await client.listen()   # 一直挂起，直到断开


@app.on_event("startup")
async def on_startup():
    # 后台任务：连接 OpenAgents 网络
    asyncio.create_task(run_openagents_client())


@app.on_event("shutdown")
async def on_shutdown():
    global client
    if client:
        try:
            await client.close()
        except Exception:
            pass
        client = None


# ========== 前端页面：GET / 返回简单聊天 UI ==========

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>和 Alex 聊天（OpenAgents）</title>
  <style>
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f3f4f6;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
    }
    .chat-container {
      width: 420px;
      max-width: 95vw;
      height: 600px;
      background: #ffffff;
      border-radius: 16px;
      box-shadow: 0 18px 45px rgba(15,23,42,0.18);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .chat-header {
      padding: 10px 14px;
      background: #4f46e5;
      color: #fff;
      font-size: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .chat-header-title {
      font-weight: 600;
    }
    .chat-body {
      flex: 1;
      padding: 10px 12px;
      overflow-y: auto;
      background: #f9fafb;
    }
    .msg {
      margin-bottom: 8px;
      display: flex;
    }
    .msg-user {
      justify-content: flex-end;
    }
    .msg-alex {
      justify-content: flex-start;
    }
    .bubble {
      max-width: 80%;
      padding: 8px 12px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .bubble-user {
      background: #4f46e5;
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .bubble-alex {
      background: #e5e7eb;
      color: #111827;
      border-bottom-left-radius: 4px;
    }
    .chat-input-area {
      display: flex;
      gap: 6px;
      padding: 8px;
      border-top: 1px solid #e5e7eb;
      background: #fff;
    }
    .chat-input {
      flex: 1;
      border-radius: 999px;
      border: 1px solid #d1d5db;
      padding: 8px 12px;
      font-size: 14px;
      outline: none;
    }
    .chat-send-btn {
      padding: 8px 14px;
      border-radius: 999px;
      border: none;
      background: #4f46e5;
      color: #fff;
      cursor: pointer;
      font-size: 14px;
      white-space: nowrap;
    }
    .chat-send-btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  </style>
</head>
<body>
  <div class="chat-container">
    <div class="chat-header">
      <span class="chat-header-title">Alex（OpenAgents 网络）</span>
      <span style="font-size: 12px; opacity: 0.8;">general 频道</span>
    </div>
    <div class="chat-body" id="chatBody"></div>
    <div class="chat-input-area">
      <input id="chatInput" class="chat-input" placeholder="对 Alex 说点什么…" />
      <button id="chatSendBtn" class="chat-send-btn">发送</button>
    </div>
  </div>

  <script>
    const chatBody = document.getElementById("chatBody");
    const chatInput = document.getElementById("chatInput");
    const chatSendBtn = document.getElementById("chatSendBtn");

    function appendMessage(role, text) {
      const msgDiv = document.createElement("div");
      msgDiv.className = "msg " + (role === "user" ? "msg-user" : "msg-alex");

      const bubble = document.createElement("div");
      bubble.className = "bubble " + (role === "user" ? "bubble-user" : "bubble-alex");
      bubble.textContent = text;

      msgDiv.appendChild(bubble);
      chatBody.appendChild(msgDiv);
      chatBody.scrollTop = chatBody.scrollHeight;
    }

    async function sendMessage() {
      const text = chatInput.value.trim();
      if (!text) return;

      appendMessage("user", text);
      chatInput.value = "";
      chatInput.focus();
      chatSendBtn.disabled = true;
      chatSendBtn.textContent = "等待 Alex…";

      try {
        const resp = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        });

        const data = await resp.json();
        appendMessage("alex", data.reply || "Alex 没有返回内容");
      } catch (err) {
        console.error(err);
        appendMessage("alex", "后端错误，请检查 ui_server 控制台。");
      } finally {
        chatSendBtn.disabled = false;
        chatSendBtn.textContent = "发送";
      }
    }

    chatSendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
      }
    });
  </script>
</body>
</html>
    """


# ========== /chat：发消息到 general，等待 alex 回复 ==========

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if client is None:
        return {"reply": "UI 客户端还没连上 OpenAgents 网络，请稍后再试。"}

    # 清空旧队列，避免拿到之前的回复
    try:
        while True:
            reply_queue.get_nowait()
    except asyncio.QueueEmpty:
        pass

    # 1. 通过 AgentClient 往 general 频道发消息
    await client.send_channel_message(
        "general",
        req.message,
    )

    # 2. 等 alex 在 general 里回一条（handle_message 会写入队列）
    try:
        reply = await asyncio.wait_for(reply_queue.get(), timeout=30.0)
    except asyncio.TimeoutError:
        reply = "Alex 没有在 30 秒内回应，可能忙碌或未收到消息。"

    return {"reply": reply}
