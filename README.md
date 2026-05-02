# Claude API Bridge (Industrial Version) / 工业化 Claude API 桥接器

[English Version Below]

这是一个高性能的 Python 桥接程序，旨在将 Claude.ai 的 Web 端 SessionKey 转化为生产级别的、兼容 OpenAI 格式的 API 接口。

## 🌟 核心特性 (Features)

- **多账号负载均衡**：支持多个 Claude.ai 账号轮询使用，自动跳过受限账号。
- **原生工具调用 (Tool Use)**：Claude 可直接识别并调用本地 `shell` 命令（如 `ls`, `df`, `grep` 等）。
- **递归推理逻辑**：后端自动处理“工具调用 -> 结果获取 -> 再次推理”的闭环，直到输出最终答案。
- **工业化部署**：内置 Systemd 服务配置与 Nginx 反向代理模板，支持 HTTPS 访问。
- **中文优化**：针对中文提示词和交互进行了深度优化，更符合国内开发需求。

## 🚀 快速开始 (Quick Start)

1. **安装依赖**:
   ```bash
   pip install -e .
   ```

2. **配置账号 (`accounts.json`)**:
   在项目根目录创建 `accounts.json`，填入你的 SessionKey：
   ```json
   [
     {"session_key": "sk-ant-sid01...", "org_id": "optional-org-id"},
     {"session_key": "sk-ant-sid02..."}
   ]
   ```

3. **启动服务**:
   ```bash
   python api_server.py
   ```

## 🛠️ 工具调用示例 (Tool Usage)

你可以发送标准的 OpenAI 格式请求来触发本地命令：
```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "帮我看看 /root 目录下有什么？"}],
    "tools": [{"type": "function", "function": {"name": "shell", "description": "执行本地 shell 命令"}}]
  }'
```

## 📜 生产环境部署 (Deployment)

建议使用 Systemd 进行守护：
- 配置文件见 `scripts/`（需自行创建）。
- 支持 Nginx 反向代理至 `8001` 端口并开启 SSL。

---

[English Version]

A high-performance Python bridge that transforms Claude Web SessionKeys into a production-ready, OpenAI-compatible API.

## 🚀 Key Highlights
- **Account Rotation**: Balance load between multiple accounts.
- **Autonomous Shell**: Native execution of local shell commands.
- **Auto-Recursive**: Internally handles tool loops for seamless integration.
- **Production-Ready**: Systemd & Nginx templates included.

## ⚖️ License
MIT
