<div align="center">

# OpenList MCP Server

**高性能 · 零依赖 · 全功能的 OpenList / AList 模型上下文协议 (MCP) 服务端**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Protocol: MCP](https://img.shields.io/badge/MCP-2024--11--05-orange.svg)](https://modelcontextprotocol.io/)
[![Dependencies: Zero](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#)

[简体中文](README.md) | [English](README_EN.md)

</div>

---

## 📖 简介

**OpenList MCP Server** 是专为大语言模型 (LLM) 与 AI 智能体设计的标准 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 服务端实现。

通过与 [OpenList](https://doc.oplist.org/) / AList 服务端无缝连接，赋予 Claude、Cursor、Gemini、Chatbox 等 AI 助手直接访问和调度所有已挂载存储（包括各类对象存储、WebDAV、本地磁盘与多协议云端存储）的能力。

---

## ⚡ 核心亮点

- **🚀 零外部依赖 (Zero Dependencies)**：100% 采用 Python 3 标准库编写，**无需 `pip install`，无需创建 `venv`**，单个文件即可极速秒级启动。
- **🔌 默认官方端口**：默认接入 OpenList / AList 官方端口 `http://localhost:5244`，同时支持命令行参数与环境变量轻松指定任意端口。
- **🛠️ 23 款全功能核心工具**：涵盖**读、写、搜、本地直传、删、移动、正则批量更名、公开分享管理、离线下载、存储监控**的完整工具链。
- **🛡️ 生产级安全护栏**：
  - **只读保护 (`OPENLIST_READONLY=true`)**：一键开启只读，拦截任何写入与删除调用；
  - **路径白名单 (`OPENLIST_ALLOWED_PATHS="/public,/work"`)**：限制智能体只能在指定安全目录中操作；
  - **防误删确认 (`OPENLIST_CONFIRM_REMOVE=true`)**：删除文件必须显式提供 `confirm=true`。
- **🔄 100% 无缝平替兼容 (Drop-in Replacement)**：底层同时支持官方规范（`openlist.fs.*`）、智能体习惯（`fs*`）以及同类社区项目的全部 snake_case 别名（如 `list_files`、`create_folder`、`get_file_info`、`upload_local_file` 等），**无需修改现有任何 Prompt 或配置即可直接无缝替代**。
- **💡 节约 Prompt Context**：相比将 API 每一个微小动作拆成近百个工具导致上下文被撑爆的方案，本项目提供高信噪比的核心工具矩阵，极大降低模型推理成本与幻觉风险。

---

## 📊 与同类方案对比

| 维度 / 特性 | OpenList 官方原生 HTTP `/mcp` | 社区重型方案 | 本项目 `openlist-mcp-server` |
| :--- | :--- | :--- | :--- |
| **外部依赖** | 需维护 Streamable HTTP Session | 依赖 `mcp`, `httpx`, `pydantic` 等庞大库 | **⚡ 纯标准库 0 外部依赖 (开箱即用)** |
| **冷启动速度** | 中等 | 较慢（导入数十个依赖） | **毫秒级极速冷启动** |
| **安装流程** | 需配置反代与流式端点 | `python3 -m venv venv && pip install -e .` | **单命令直接运行 `python3 server.py`** |
| **工具设计** | 仅 3 个 (`list`, `get`, `link`) | 膨胀至 70~80 个（极耗 Token，易引发幻觉） | **23 款高信噪比核心工具矩阵** |
| **CRUD 文件读写** | ❌ 只读元数据，无法读写文件 | ✅ 支持 | **✅ 完整支持（文本读写、本地直传、创建目录）** |
| **本地文件直传** | ❌ 不支持 | ✅ 支持 | **✅ 原生支持 `fsUploadLocalFile`** |
| **安全防护模式** | ❌ 无 | 部分支持 | **✅ 完整内置（只读模式、白名单、防误删）** |
| **兼容性与别名** | 仅官方 `openlist.fs.*` | 仅支持自定义 snake_case | **✅ 全兼容：官方规范 + 智能体名 + 平替别名** |

---

## 🚀 快速上手

### 1. 环境要求

- Python 3.8 或更高版本
- 运行中的 OpenList 或 AList 实例（默认服务地址为 `http://localhost:5244`）

### 2. 获取代码并运行

```bash
git clone https://github.com/zws13579/openlist-mcp-server.git
cd openlist-mcp-server

# 无需 pip install，直接启动！
python3 server.py
```

### 3. 配置参数参考

支持通过 **命令行参数** 或 **环境变量** 进行配置，优先级为：`命令行参数 > 环境变量 > 默认值`。

| 配置项 | 命令行参数 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **服务端地址** | `--url` | `OPENLIST_URL` / `ALIST_HOST` | `http://localhost:5244` | OpenList / AList API 服务地址 |
| **API Token** | `--token` | `OPENLIST_TOKEN` / `ALIST_TOKEN` | *空* | 后台生成的 API Token（优先鉴权） |
| **管理员用户名** | `--username`, `-u` | `OPENLIST_USERNAME` / `ALIST_USERNAME` | `admin` | 管理员用户名（若未配置 Token） |
| **管理员密码** | `--password`, `-p` | `OPENLIST_PASSWORD` / `ALIST_PASSWORD` | *空* | 管理员登录密码 |
| **安全只读模式** | `--readonly` | `OPENLIST_READONLY` | `false` | 设为 `true` 时拦截所有写入与删除操作 |
| **路径白名单** | `--allowed-paths` | `OPENLIST_ALLOWED_PATHS` | *空* | 限制操作路径（逗号分隔，如 `/public,/work`） |
| **防误删确认** | `--confirm-remove` | `OPENLIST_CONFIRM_REMOVE` | `false` | 设为 `true` 时删除操作必须传 `confirm=true` |

---

## 💻 客户端接入配置

### 1. Claude Desktop

推荐方式：在项目根目录配置 `.env`（权限 `chmod 600 .env`），服务端将自动静默读取，无需在 `args` 中传递任何敏感凭据：

在配置文件中添加（macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`；Windows: `%APPDATA%\Claude\claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "openlist": {
      "command": "python3",
      "args": ["/绝对路径/openlist-mcp-server/server.py"]
    }
  }
}
```

> **安全提示**：使用 `.env` 文件可杜绝系统进程列表 (`ps aux`) 或 Shell 历史暴露明文密码的风险。若使用动态环境变量，推荐通过 `env` 字段传递 `OPENLIST_TOKEN`（后台生成的静态 Token）而非原始管理员密码。

### 2. Cursor / Windsurf

在 Cursor 设置中搜索 `MCP`，添加新 Server：
- **Name**: `openlist`
- **Type**: `command`
- **Command**: `python3 /绝对路径/openlist-mcp-server/server.py`

### 3. VS Code (Continue / Roo-Code / Cline)

在扩展的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "openlist": {
      "command": "python3",
      "args": ["/绝对路径/openlist-mcp-server/server.py"],
      "env": {
        "OPENLIST_URL": "http://localhost:5244",
        "OPENLIST_TOKEN": "你的静态API_TOKEN"
      }
    }
  }
}
```

---

## 🌐 远程网络模式 (SSE 接入指南)

若你的客户端运行在**移动设备、Web 浏览器**，或所在环境**无法直接执行本地 Python 脚本**，可通过 MCP 规范标准的 **SSE (Server-Sent Events)** 网络协议远程连接：

### 1. 启动远程 SSE 网关服务

在任意拥有 Python 3.8+ 环境的主机、云服务器或容器中，通过通用网关启动服务（推荐配置 `--auth` 密钥以保障公网访问安全）：

```bash
# 启动 SSE 网络服务（通过 --port 指定你希望监听的端口，并可设置访问密钥）
npx -y supergateway \
  --port <端口> \
  --stdio "python3 /path/to/openlist-mcp-server/server.py" \
  --auth "YOUR_SECRET_TOKEN"
```

对外访问地址格式（`/sse` 为服务固定路由，其余替换为你实际的网络地址）：
- **域名 / 反向代理环境**: `https://<你的实际域名>/sse`（标准 443 端口，无需填写端口号）
- **直连 IP 端口环境**: `http://<服务器公网IP>:<你指定的端口>/sse`

### 2. 客户端通用连接配置

在支持远程 MCP 协议的客户端（移动端 App / Web 端 / 智能体编排平台）中配置：

- **传输协议 (Transport)**: `SSE`
- **URL**: 填入上方获取的实际地址，例如 `https://<你的实际域名>/sse` 或 `http://<服务器公网IP>:<你指定的端口>/sse`
- **Headers**（若启用了访问密钥）：`Authorization: Bearer YOUR_SECRET_TOKEN`


---

## 🛠️ 工具清单 (Tool Reference)

本服务提供 23 款工具，同时支持官方规范命名、智能体命名与平替 snake_case 别名：

### 1. 文件浏览与检索

| 工具名 | 兼容别名 | 说明 |
| :--- | :--- | :--- |
| `fsList` | `openlist.fs.list`, `list_files` | 列出指定目录下的文件与子文件夹（支持分页与强制刷新） |
| `fsGet` | `openlist.fs.get`, `get_file_info` | 获取文件元数据及高速直接下载链接 (raw_url) |
| `fsLink` | `openlist.fs.link`, `get_download_url` | 获取下载直链、并发推荐数与分块参数 |
| `fsDirs` | `list_dirs` | 轻量化仅获取子目录列表，适合快速探索目录树 |
| `fsSearch` | `search_files` | 跨所有挂载网盘进行全文/文件名搜索 |
| `fsRead` | `read_file` | 安全读取文本/代码文件内容（内置防爆 Token 截断） |

### 2. 文件内容更新与整理 (CRUD)

| 工具名 | 兼容别名 | 说明 |
| :--- | :--- | :--- |
| `fsPutText` | `write_file`, `put_file` | 直接写入或覆盖纯文本内容到云盘指定路径 |
| `fsUploadLocalFile` | `upload_local_file`, `openlist.fs.upload_local_file` | **将智能体所在主机的本地文件直接上传至云盘** |
| `fsMkdir` | `create_folder` | 在指定云盘路径下创建新文件夹 |
| `fsRename` | `rename` | 单文件或单文件夹重命名 |
| `fsBatchRename` | `batch_rename` | 批量映射重命名同一目录下的多个文件 |
| `fsRegexRename` | `regex_rename` | 使用正则表达式批量重命名（如批量清洗番剧命名） |
| `fsMove` | `move` | 批量移动文件列表到新目录 |
| `fsRecursiveMove` | `recursive_move` | 递归聚合移动：将整个目录树完整合并至目标路径 |
| `fsCopy` | `copy` | 批量复制文件列表到新目录 |
| `fsRemove` | `remove` | 删除指定目录下的文件或子目录（支持防误删确认） |
| `fsRemoveEmptyDirectory` | `remove_empty_dirs` | 递归自动清理指定目录下的所有空文件夹 |

### 3. 分享管理与离线任务

| 工具名 | 兼容别名 | 说明 |
| :--- | :--- | :--- |
| `fsCreateShare` | `create_share`, `openlist.share.create` | 为云盘文件/目录创建对外分享链接（支持密码与有效期） |
| `fsListShares` | `list_shares`, `openlist.share.list` | 查询当前所有已创建的有效分享链接列表 |
| `fsDeleteShare` | `delete_share`, `openlist.share.delete` | 删除指定的分享链接 |
| `fsAddOfflineDownload` | `add_offline_download` | 提交离线下载任务（支持 HTTP / HTTPS / 磁力链接） |
| `fsListOfflineTasks` | `list_offline_tasks` | 查询当前后台正在进行的离线下载进度及已完成列表 |
| `fsStorageStatus` | `storage_status` | 实时巡检所有已挂载云盘存储驱动的健康状态 |

---

## 🧪 自动化测试

项目内嵌完整的自动化回归测试套件 `test_server.py`，覆盖协议握手、Schema 校验、异常边界、全生命周期读写与安全拦截：

```bash
# 1. 基础协议与 Schema 测试（无需连机服务）
python3 test_server.py

# 2. 全量联机回归测试（连接至本地默认端口 5244）
python3 test_server.py --password 你的密码
```

测试套件将自动执行 **51 项全方位集成测试**：
- [x] JSON-RPC 2.0 初始化与 Ping/Pong 握手保活
- [x] 23 款核心工具 Schema 完整性与参数校验
- [x] 官方别名与同类项目 snake_case 别名路由平替验证
- [x] 云盘写/读/改/删/本地上传/公开分享生命周期
- [x] `--readonly` 安全只读模式写拦截防护
- [x] `--allowed-paths` 越界路径访问防御拦截
- [x] `--confirm-remove` 防误删确认拦截

---

## 🔒 安全与隐私最佳实践

为了保障生产环境下的多源云存储安全，建议遵循以下安全规范：

1. **避免在进程命令行 (`args`) 传递明文密码**：
   - 绝大多数操作系统下，普通用户可通过 `ps aux` 查看当前正在运行进程的完整命令行参数。
   - **推荐**：使用项目内置支持的 `.env` 本地私有文件，或在客户端配置的 `env` 字段中传递。
   - 将 `.env` 设为严格只读权限：`chmod 600 .env`。
2. **优先使用静态 API Token (`OPENLIST_TOKEN`)**：
   - 建议在 OpenList 后台（设置 -> 基础设置 -> 生成 Token）创建专用的 API 令牌，替代原始管理员明文密码。
3. **分享密码与元数据脱敏**：
   - `fsListShares` 已默认脱敏已有分享链接的提取密码（展示为 `[***]`），防止智能体或第三方日志记录未经授权的访问凭据。
   - `fsGet` 默认屏蔽敏感签名原始串，避免签名参数进入大模型上下文。
4. **按需启用沙箱防御机制**：
   - **公共/只读场景**：传入 `--readonly`，严禁智能体执行任何覆写、重命名或删除动作。
   - **受限目录场景**：传入 `--allowed-paths "/public,/workspace"`，严禁智能体跳出白名单目录访问敏感分区。
   - **重要数据场景**：传入 `--confirm-remove`，任何删除操作必须显式传参 `confirm=true`，有效杜绝模型幻觉导致的数据丢失。

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 开源发布。
欢迎提交 Issue 与 Pull Request 共同改进！
