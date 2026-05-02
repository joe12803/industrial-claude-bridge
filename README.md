# Industrial Claude Bridge & OpenClaw Integration Guide

本项目是 `industrial-claude-bridge` (Python 版核心驱动) 的标准化分发版，配合 `openclaw-zero-token-dist` 可构建一套具备 **本地 Tool 执行**、**多账号池**、**中文 UI 界面** 的工业级 LLM 生产线。

## 🏗️ 整体架构图
1. **User/Feishu** -> 发送请求。
2. **OpenClaw (18790)** -> 提供管理后台和多模型分发。
3. **Claude-API-Bridge (8001)** -> 核心驱动层，负责执行 Shell 工具并与 Claude Web 通信。
4. **Claude Web** -> 执行推理。

## 🚀 部署流程

### 第一步：启动 Claude-API-Bridge (核心驱动)
1. **安装环境**:
   ```bash
   pip install fastapi uvicorn pydantic python-dotenv claude-webapi
   ```
2. **配置账号**:
   将 `accounts.json.example` 重命名为 `accounts.json`，填入你的 Claude `sessionKey`。
3. **设置安全 Token**:
   在 `api_server.py` 中默认要求的 Token 为 `sk-123456`。
4. **启动**:
   ```bash
   python api_server.py
   ```

### 第二步：配置 OpenClaw (网关与界面)
1. **安装依赖**:
   在 `openclaw-zero-token-dist` 目录下执行 `pnpm install`。
2. **配置 Provider**:
   在 OpenClaw UI 界面中添加一个 Provider：
   - **Base URL**: `http://127.0.0.1:8001/v1`
   - **API Key**: `sk-123456`
   - **模型 ID**: `claude-sonnet-4-6`

### 第三步：采矿自动化
配合 `autonomous-mining-toolkit` 使用，通过 Bridge 执行 `driller.py` 提取源码，并将产出的精炼报告自动同步至 `hermes-shared/wiki`。

## 🛡️ 安全加固说明
- **Auth**: 所有请求必须带上 `Bearer sk-123456`。
- **Sandbox**: 驱动层内置指令黑名单，拦截 `rm`, `mv`, `shutdown` 等危险操作。
- **Recursive**: 驱动层自动处理 `<tool_call>` 标签，实现自主递归推理。

## 📜 维护者
- Powered by Hermes Agent & Joe1280
