# Claude API Bridge (Industrial Version)

A high-performance Python bridge that transforms Claude Web SessionKeys into a production-ready, OpenAI-compatible API. 

## 🌟 Features

- **Multi-Account Pool**: Seamless rotation between multiple Claude.ai accounts.
- **Native Tool Use**: Automatically executes local `shell` commands via Claude's intent.
- **Recursive Reasoning**: Handles tool execution loops internally before returning final results.
- **Production Ready**: Includes Systemd service templates and Nginx reverse proxy configs.
- **Chinese Support**: Optimized for Chinese prompting and interaction.

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -e .
   ```

2. **Configure Accounts**:
   Create `accounts.json`:
   ```json
   [
     {"session_key": "sk-ant-sid01...", "org_id": "optional-org-id"},
     {"session_key": "sk-ant-sid02..."}
   ]
   ```

3. **Run Server**:
   ```bash
   python api_server.py
   ```

## 🛠️ Tool Usage

Send a standard OpenAI-compatible request with `tools`:
```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "List files in /tmp"}],
    "tools": [{"type": "function", "function": {"name": "shell", "parameters": {...}}}]
  }'
```

## 📜 Deployment

Refer to the `scripts/` directory for Systemd and Nginx configurations.

## ⚖️ License
MIT
