import os
import asyncio
import re
import uuid
import subprocess
import json
import logging
from typing import List, Optional, Union, Any
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from claude_webapi import ClaudeClient
from claude_webapi.constants import Model
from claude_webapi.exceptions import AuthenticationError, APIError
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("claude-bridge")

load_dotenv()

app = FastAPI(title="Claude Tool Bridge - Secure Version")
security = HTTPBearer()

ACCOUNTS_FILE = "/home/joe1280/Claude-API/accounts.json"
AUTH_TOKEN = "sk-123456"  # 强制要求的 Token

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

# --- Security Middleware ---

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return credentials.credentials

# --- Secure Tool Execution ---

DANGEROUS_COMMANDS = ["rm ", "mv ", "shutdown", "reboot", ":(", "mkfs", "dd ", "> /dev", "kill "]

async def execute_local_tool(name: str, args: dict) -> str:
    logger.info(f"RUNNING TOOL: {name}({args})")
    if name in ["shell", "bash"]:
        cmd = args.get("command", "").lower()
        
        # 指令黑名单检查
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in cmd:
                logger.warning(f"BLOCKED DANGEROUS COMMAND: {cmd}")
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

@app.get("/v1/models")
async def list_models(token: str = Depends(verify_token)):
    return {"object": "list", "data": [{"id": "claude-sonnet-4-6", "object": "model"}]}

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

    async def get_claude_response(current_history):
        prompt = "\n".join(current_history)
        if not prompt.endswith("Assistant: "):
            prompt += "\nAssistant: "
        async with ClaudeClient(session_key, org_id) as client:
            resp = await client.generate_content(prompt, model=request.model)
            return resp.text

    last_text = ""
    for i in range(3):
        last_text = await get_claude_response(history)
        tool_calls = parse_tool_calls(last_text)
        if not tool_calls: break
            
        history.append(f"Assistant: {last_text}")
        for tc in tool_calls:
            result = await execute_local_tool(tc["name"], tc["arguments"])
            history.append(f"Tool Result: {result}")

    return {
        "choices": [{"message": {"role": "assistant", "content": last_text}, "finish_reason": "stop", "index": 0}],
        "model": request.model,
        "object": "chat.completion"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
