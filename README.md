# Entelechy

> A 24/7 autonomous AI agent with long-term memory, plugin system, and browser automation

[English](#english) | [中文](#中文)

---

## English

### Overview

Entelechy is an autonomous agent runtime that runs continuously, making decisions and taking actions based on LLM responses. It features:

- **Persistent Agent Loop** - Never-ending autonomous operation with LLM calls and tool execution
- **Long-term Memory** - Markdown-based storage with semantic search and retrieval
- **Plugin System** - Runtime-loadable plugins that extend functionality
- **Browser Automation** - Playwright-based browser control

### Quick Start

#### 1. Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

#### 2. Configure

Edit `config.yaml`:
```yaml
agent:
  provider: "openai"        # or "anthropic"
  model: "openrouter/free"  # your model
  max_tokens: 8000

browser:
  headless: true

logging:
  level: "INFO"
```

Edit `.env` with your API keys:
```bash
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
# or for Anthropic:
# ANTHROPIC_API_KEY=your_key_here
```

#### 3. Run

```bash
python main.py
```

### Docker

```bash
docker-compose up -d
```

---

## 中文

### 简介

Entelechy 是一个自主智能体运行时，能够持续运行、做出决策并根据 LLM 响应执行操作。特性包括：

- **持续智能体循环** - 永不停歇的自主运行，包含 LLM 调用和工具执行
- **长期记忆** - 基于 Markdown 的存储，支持语义搜索和检索
- **插件系统** - 运行时可加载的插件，扩展功能
- **浏览器自动化** - 基于 Playwright 的浏览器控制

### 快速开始

#### 1. 安装

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

#### 2. 配置

编辑 `config.yaml` 和 `.env` 文件（见上文英文部分）

#### 3. 运行

```bash
python main.py
```

### Docker 部署

```bash
docker-compose up -d
```
