<div align="center">

# OpenList MCP Server

**High-performance, Zero-dependency, Full-featured Model Context Protocol (MCP) Server for OpenList & AList**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Protocol: MCP](https://img.shields.io/badge/MCP-2024--11--05-orange.svg)](https://modelcontextprotocol.io/)
[![Dependencies: Zero](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#)

[简体中文](README.md) | [English](README_EN.md)

</div>

---

## 📖 Introduction

**OpenList MCP Server** is a production-grade [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built for LLMs and autonomous AI agents.

By connecting directly to an [OpenList](https://doc.oplist.org/) or AList backend, it empowers AI assistants like Claude, Cursor, Gemini, and Chatbox to explore, read, write, organize, share, and download across dozens of mounted storage drivers (such as object storages, WebDAV, local mounts, and multi-protocol remote storages).

---

## ⚡ Highlights

- **🚀 Zero External Dependencies**: 100% written with Python standard library. **No `pip install`, no `venv` required**. Instant startup anywhere.
- **🔌 Official Default Port**: Connects to `http://localhost:5244` by default; easily configured via CLI flags or environment variables.
- **🛠️ 23 High-Value Core Tools**: Covers reading, writing, searching, local file upload, deletion, moving, regex renaming, public share management, offline downloads, and storage monitoring.
- **🛡️ Production Security Guardrails**:
  - **Read-Only Mode (`OPENLIST_READONLY=true`)**: Blocks any mutating or deleting calls;
  - **Path Allowlist (`OPENLIST_ALLOWED_PATHS="/public,/work"`)**: Confines agent activity to designated safe directories;
  - **Delete Confirmation (`OPENLIST_CONFIRM_REMOVE=true`)**: Requires `confirm=true` before deletion.
- **🔄 100% Drop-in Compatibility**: Supports official OpenList names (`openlist.fs.*`), camelCase conventions (`fs*`), and snake_case aliases (`list_files`, `get_file_info`, `upload_local_file`, `create_folder`, etc.) for seamless replacement without altering prompts.
- **💡 Token-Efficient Design**: Avoids bloating the context window with dozens of redundant tools, significantly lowering token cost and eliminating LLM tool hallucinations.

---

## 📊 Comparison

| Feature | OpenList Native HTTP `/mcp` | Bloated Community Alternatives | This Project (`openlist-mcp-server`) |
| :--- | :--- | :--- | :--- |
| **Dependencies** | Requires SSE session management | `mcp`, `httpx`, `pydantic`, etc. | **⚡ 0 Dependencies (Pure Python Stdlib)** |
| **Cold Start** | Moderate | Slow (imports dozens of packages) | **Sub-millisecond Cold Start** |
| **Installation** | Reverse proxy config required | `venv` + `pip install -e .` | **Zero setup: `python3 server.py` directly** |
| **Tools Count** | 3 tools (read-only) | 70–80 tools (severe prompt token bloat) | **23 High-Signal Core Tools** |
| **CRUD Operations** | ❌ Metadata view only | ✅ Supported | **✅ Full support (read, write, local upload, mkdir)** |
| **Direct Local Upload**| ❌ Not supported | ✅ Supported | **✅ Native support (`fsUploadLocalFile`)** |
| **Security Guardrails**| ❌ None | Partial | **✅ Comprehensive (Readonly, Allowlist, Confirm)** |
| **Drop-in Compatibility**| OpenList `openlist.fs.*` only | Custom snake_case only | **✅ 100% Multi-spec & Drop-in Compatibility** |

---

## 🚀 Quick Start

### 1. Requirements

- Python 3.8 or higher
- A running OpenList or AList instance (default: `http://localhost:5244`)

### 2. Run Directly

```bash
git clone https://github.com/zws13579/openlist-mcp-server.git
cd openlist-mcp-server

# Zero dependencies — run directly!
python3 server.py
```

### 3. Configuration

Configuration priority: `CLI Arguments > Environment Variables > Defaults`.

| Option | CLI Flag | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Server URL** | `--url` | `OPENLIST_URL` / `ALIST_HOST` | `http://localhost:5244` | OpenList / AList API endpoint |
| **API Token** | `--token` | `OPENLIST_TOKEN` / `ALIST_TOKEN` | *empty* | Backend API token (highest priority) |
| **Username** | `--username`, `-u` | `OPENLIST_USERNAME` / `ALIST_USERNAME` | `admin` | Admin username |
| **Password** | `--password`, `-p` | `OPENLIST_PASSWORD` / `ALIST_PASSWORD` | *empty* | Admin password |
| **Read-Only** | `--readonly` | `OPENLIST_READONLY` | `false` | Intercept write/delete operations |
| **Allowed Paths** | `--allowed-paths` | `OPENLIST_ALLOWED_PATHS` | *empty* | Comma-separated path whitelist |
| **Confirm Remove**| `--confirm-remove`| `OPENLIST_CONFIRM_REMOVE` | `false` | Enforce `confirm=true` on deletion |

---

## 💻 Client Configuration

### Claude Desktop

**Recommended**: Store credentials securely in `.env` (with `chmod 600 .env`). The server automatically detects and loads it without exposing plaintext secrets in `args`:

```json
{
  "mcpServers": {
    "openlist": {
      "command": "python3",
      "args": ["/path/to/openlist-mcp-server/server.py"]
    }
  }
}
```

> **Security Note**: Using `.env` prevents exposing credentials to operating system process monitors (`ps aux`) and command-line shell history. If configuring dynamic environment variables, pass `OPENLIST_TOKEN` via the `env` dictionary instead of raw passwords.

---

## 🌐 Remote Access without Local Python (SSE Mode)

If your client runs on **mobile devices, web browsers**, or in an environment where **local Python execution is restricted**, connect via the standard **SSE (Server-Sent Events)** protocol:

### 1. Start Remote SSE Gateway

Launch the gateway on any host, cloud server, or container with Python 3.8+ installed (configuring an `--auth` secret key is recommended for network security):

```bash
# Launch SSE gateway on port 8000
npx -y supergateway \
  --port 8000 \
  --stdio "python3 /path/to/openlist-mcp-server/server.py" \
  --auth "YOUR_SECRET_TOKEN"
```

When proxied via Nginx / Caddy with HTTPS, your public endpoint becomes:
```text
https://mcp.yourdomain.com/sse
```

### 2. Client Connection Setup

In any client supporting remote MCP (mobile apps, web agents, orchestration platforms):

- **Transport**: `SSE`
- **URL**: `https://mcp.yourdomain.com/sse` (or `http://YOUR_SERVER_IP:8000/sse`)
- **Headers** (if `--auth` enabled): `Authorization: Bearer YOUR_SECRET_TOKEN`


## 🛠️ Tool Reference (23 Tools)

### 1. Exploration & Reading
- `fsList` / `list_files` / `openlist.fs.list`: List directory items.
- `fsGet` / `get_file_info` / `openlist.fs.get`: Retrieve file metadata and raw download URL.
- `fsLink` / `get_download_url` / `openlist.fs.link`: Fetch direct stream URL and concurrency specs.
- `fsDirs` / `list_dirs`: Fast directory-only exploration.
- `fsSearch` / `search_files`: Global cross-storage keyword search.
- `fsRead` / `read_file`: Safe text/code reader with length limits.

### 2. File Organization & Local Transfer
- `fsPutText` / `write_file`: Create or overwrite text files.
- `fsUploadLocalFile` / `upload_local_file`: Upload local files to cloud drive.
- `fsMkdir` / `create_folder`: Create directories.
- `fsRename` / `rename`: Rename a single file or directory.
- `fsBatchRename` / `batch_rename`: Map-based batch renaming.
- `fsRegexRename` / `regex_rename`: Regular-expression batch renaming.
- `fsMove` / `move`: Move files between directories.
- `fsRecursiveMove` / `recursive_move`: Recursively merge directory trees.
- `fsCopy` / `copy`: Copy files between directories.
- `fsRemove` / `remove`: Delete files or subdirectories.
- `fsRemoveEmptyDirectory` / `remove_empty_dirs`: Prune empty directories recursively.

### 3. Share & Task Management
- `fsCreateShare` / `create_share`: Create public sharing links with optional password & expiration.
- `fsListShares` / `list_shares`: View all active share links.
- `fsDeleteShare` / `delete_share`: Revoke and delete a share link.
- `fsAddOfflineDownload` / `add_offline_download`: Submit magnet / HTTP download tasks.
- `fsListOfflineTasks` / `list_offline_tasks`: Track running and finished offline tasks.
- `fsStorageStatus` / `storage_status`: Health audit of all mounted cloud drivers.

---

## 🧪 Testing

Run all 51 automated regression test cases:

```bash
# Offline protocol and schema tests
python3 test_server.py

# Full integration test against your instance
python3 test_server.py --password YOUR_PASSWORD
```

---

## 🔒 Security & Privacy Best Practices

1. **Avoid CLI Passwords**: Ordinary users on Linux/macOS can inspect running process arguments via `ps aux`. Always use `.env` (`chmod 600 .env`) or client `env` fields.
2. **Prefer Static API Tokens (`OPENLIST_TOKEN`)**: Generate tokens from the OpenList admin settings to avoid exposing root credentials.
3. **Password Masking**: `fsListShares` automatically masks share passwords as `[***]` to prevent unauthorized leakage into LLM contexts or logs.
4. **Defense in Depth**: Use `--readonly` for read-only agents, `--allowed-paths` to lock down storage subtrees, and `--confirm-remove` to prevent unintended data loss from LLM hallucinations.

---

## 📄 License

Released under the [MIT License](LICENSE).
