import os
import asyncio
import re
import json
import logging
from typing import List, Optional, Union, Any
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from claude_webapi import ClaudeClient
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("claude-bridge")

load_dotenv()

app = FastAPI(title="Claude Tool Bridge - Streaming Version")
security = HTTPBearer()

ACCOUNTS_FILE = "/home/joe1280/Claude-API/accounts.json"
AUTH_TOKEN = "sk-123456"

class AccountManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.accounts = []
        self.index = 0
        self.lock = asyncio.Lock()
        self.load_accounts()

    def load_accounts(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                self.accounts = json.load(f)
        if not self.accounts:
            sk = os.getenv("CLAUDE_SESSION_KEY")
            if sk: self.accounts = [{"session_key": sk}]
        logger.info(f"Loaded {len(self.accounts)} accounts.")

    async def get_next(self):
        async with self.lock:
            if not self.accounts:
                raise HTTPException(status_code=503, detail="No active accounts available")
            acc = self.accounts[self.index]
            self.index = (self.index + 1) % len(self.accounts)
            return acc

account_manager = AccountManager(ACCOUNTS_FILE)

# --- Security ---

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return credentials.credentials

DANGEROUS_COMMANDS = ["rm ", "mv ", "shutdown", "reboot", ":(", "mkfs", "dd ", "> /dev", "kill "]

async def execute_local_tool(name: str, args: dict) -> str:
    if name in ["shell", "bash"]:
        cmd = args.get("command", "").lower()
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in cmd:
                return f"Error: Command '{cmd}' is blocked for security reasons."
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return f"STDOUT:\n{stdout.decode()}\nSTDERR:\n{stderr.decode()}"
        except Exception as e:
            return f"Error: {str(e)}"
    return f"Tool {name} not supported."

def parse_tool_calls(text: str) -> List[dict]:
    pattern = r"<tool_call>(.*?)</tool_call>"
    matches = re.findall(pattern, text, re.DOTALL)
    tool_calls = []
    for m in matches:
        try:
            data = json.loads(m.strip())
            tool_calls.append(data)
        except: continue
    return tool_calls

# --- Models ---

class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = ""

class ChatCompletionRequest(BaseModel):
    model: str = "claude-sonnet-4-6"
    messages: List[ChatMessage]
    tools: Optional[List[dict]] = None
    stream: bool = False

# --- Helper for SSE Formatting ---

def format_sse(content: str, model: str, finish_reason: Optional[str] = None):
    data = {
        "choices": [{
            "delta": {"content": content} if content else {},
            "finish_reason": finish_reason,
            "index": 0
        }],
        "model": model,
        "object": "chat.completion.chunk"
    }
    return f"data: {json.dumps(data)}\n\n"

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, token: str = Depends(verify_token)):
    acc = await account_manager.get_next()
    session_key = acc["session_key"]
    org_id = acc.get("org_id")
    
    TOOL_INSTRUCTION = """
You have access to a local Linux shell. To execute commands, use EXACTLY this format:
<tool_call>{"name": "shell", "arguments": {"command": "your_command"}}</tool_call>
Available tools: shell
"""
    history = []
    if request.tools:
        history.append(f"System: {TOOL_INSTRUCTION}")
    
    for m in request.messages:
        role = "User" if m.role == "user" else "Assistant"
        history.append(f"{role}: {m.content}")

    async def stream_generator():
        current_history = list(history)
        last_text = ""
        
        for i in range(3): # Max 3 recursive tool calls
            prompt = "\n".join(current_history)
            if not prompt.endswith("Assistant: "):
                prompt += "\nAssistant: "
            
            full_response = ""
            async with ClaudeClient(session_key, org_id) as client:
                # 网页端 API 封装通常不支持直接 SSE 代理，我们手动模拟流式
                resp = await client.generate_content(prompt, model=request.model)
                full_response = resp.text

            tool_calls = parse_tool_calls(full_response)
            
            if not tool_calls:
                # 最终结果，流式输出给前端
                if request.stream:
                    yield format_sse(full_response, request.model)
                    yield "data: [DONE]\n\n"
                else:
                    # 如果不是流式，直接结束由外层返回
                    last_text = full_response
                break
            
            # 如果有工具调用，我们先流式输出“思考过程”让前端不掉线
            if request.stream:
                yield format_sse(f"思考中 ({i+1}/3): {full_response}\n", request.model)

            current_history.append(f"Assistant: {full_response}")
            for tc in tool_calls:
                result = await execute_local_tool(tc["name"], tc["arguments"])
                current_history.append(f"Tool Result: {result}")
        
        if not request.stream:
            # 非流式情况下的回退逻辑（实际上很少走到这）
            yield json.dumps({
                "choices": [{"message": {"role": "assistant", "content": full_response}, "finish_reason": "stop", "index": 0}],
                "model": request.model, "object": "chat.completion"
            })

    if request.stream:
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # 非流式直接运行生成器获取最后结果
        acc_text = ""
        async for chunk in stream_generator():
            if not chunk.startswith("data:"):
                return json.loads(chunk)
        raise HTTPException(status_code=500, detail="Stream failed to produce response")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
