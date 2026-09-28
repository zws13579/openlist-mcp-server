#!/usr/bin/env python3
"""
OpenList MCP Server (Enhanced & Zero-Dependency Edition)
=========================================================
High-performance, zero-dependency Model Context Protocol (MCP) server for OpenList / AList.
Provides complete cloud drive management (read/write/search/rename/local upload/share/offline/monitoring)
for AI agents and LLM clients.

Default connection: http://localhost:5244
Zero external dependencies: Pure Python standard library (3.8+)
"""

import sys
import os
import json
import re
import argparse
import urllib.request
import urllib.error
import urllib.parse
import ssl
from typing import Any, Dict, List, Optional


# ==========================================
# 环境变量加载（纯标准库实现，支持当前目录 .env）
# ==========================================

def load_dotenv(dotenv_path: Optional[str] = None):
    """纯标准库轻量加载 .env 文件，无需任何第三方依赖"""
    if dotenv_path is None:
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

load_dotenv()


# ==========================================
# 配置解析（命令行参数 > 环境变量/.env > 默认配置）
# ==========================================

def parse_args():
    parser = argparse.ArgumentParser(description="OpenList MCP Server")
    parser.add_argument("--url", dest="url", default=None, help="OpenList / AList API 服务端地址 (默认: http://localhost:5244)")
    parser.add_argument("--token", dest="token", default=None, help="OpenList API Token (优先级高于账号密码)")
    parser.add_argument("--username", "-u", dest="username", default=None, help="OpenList 管理员用户名 (默认: admin)")
    parser.add_argument("--password", "-p", dest="password", default=None, help="OpenList 管理员密码")
    parser.add_argument("--readonly", dest="readonly", action="store_true", default=None, help="开启安全只读模式（禁止写入、删除、重命名）")
    parser.add_argument("--allowed-paths", dest="allowed_paths", default=None, help="限制操作路径白名单 (逗号分隔，如: /public,/work)")
    parser.add_argument("--confirm-remove", dest="confirm_remove", action="store_true", default=None, help="删除操作必须提供 confirm=true 确认")
    parser.add_argument("--insecure", dest="insecure", action="store_true", default=None, help="跳过 HTTPS 证书验证（适用于内网自签名证书）")
    args, _ = parser.parse_known_args()
    return args

_cli_args = parse_args()

# 基础服务端地址（默认 5244 端口）
OPENLIST_URL = (
    _cli_args.url
    or os.environ.get("OPENLIST_URL")
    or os.environ.get("ALIST_HOST")
    or "http://localhost:5244"
).rstrip("/")
if OPENLIST_URL.endswith("/api"):
    OPENLIST_URL = OPENLIST_URL[:-4].rstrip("/")

# 认证配置
OPENLIST_TOKEN = _cli_args.token or os.environ.get("OPENLIST_TOKEN") or os.environ.get("ALIST_TOKEN")
OPENLIST_USER = _cli_args.username or os.environ.get("OPENLIST_USERNAME") or os.environ.get("ALIST_USERNAME") or "admin"
OPENLIST_PASS = _cli_args.password or os.environ.get("OPENLIST_PASSWORD") or os.environ.get("ALIST_PASSWORD") or ""

# 安全控制选项
_env_readonly = os.environ.get("OPENLIST_READONLY", "").lower() in ("true", "1", "yes")
OPENLIST_READONLY = _cli_args.readonly if _cli_args.readonly is not None else _env_readonly

_env_allowed = os.environ.get("OPENLIST_ALLOWED_PATHS", "")
OPENLIST_ALLOWED_PATHS = [p.strip() for p in (_cli_args.allowed_paths or _env_allowed).split(",") if p.strip()]

_env_confirm = os.environ.get("OPENLIST_CONFIRM_REMOVE", "").lower() in ("true", "1", "yes")
OPENLIST_CONFIRM_REMOVE = _cli_args.confirm_remove if _cli_args.confirm_remove is not None else _env_confirm

_env_insecure = os.environ.get("OPENLIST_INSECURE_SSL", "").lower() in ("true", "1", "yes")
OPENLIST_INSECURE = _cli_args.insecure if _cli_args.insecure is not None else _env_insecure

_ssl_context: Optional[ssl.SSLContext] = None
if OPENLIST_INSECURE:
    _ssl_context = ssl._create_unverified_context()

def http_urlopen(req: urllib.request.Request, timeout: int = 25):
    """统一执行 HTTP/HTTPS 网络请求（自动处理 SSL 校验策略）"""
    if _ssl_context is not None:
        return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context)
    return urllib.request.urlopen(req, timeout=timeout)

_cached_token: Optional[str] = OPENLIST_TOKEN



# ==========================================
# 安全防御校验
# ==========================================

def check_write_permission(action_name: str = "写操作"):
    """拦截只读模式下的写操作"""
    if OPENLIST_READONLY:
        raise PermissionError(f"操作被拦截：当前已开启安全只读模式 (OPENLIST_READONLY=true)，禁止执行 [{action_name}]。")

def check_path_allowed(path: str):
    """验证操作路径是否在白名单内"""
    if not OPENLIST_ALLOWED_PATHS:
        return
    norm = "/" + path.strip("/")
    allowed = any(norm == ap or norm.startswith(ap.rstrip("/") + "/") for ap in OPENLIST_ALLOWED_PATHS)
    if not allowed:
        raise PermissionError(f"操作被拦截：目标路径 [{path}] 不在白名单允许范围内 ({', '.join(OPENLIST_ALLOWED_PATHS)})。")


# ==========================================
# 网络通信与鉴权重试机制
# ==========================================

def get_token() -> str:
    """获取访问 Token（若无静态 Token 则通过账号密码自动登录并缓存）"""
    global _cached_token
    if _cached_token:
        return _cached_token

    url = f"{OPENLIST_URL}/api/auth/login"
    payload = json.dumps({"username": OPENLIST_USER, "password": OPENLIST_PASS}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with http_urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == 200:
                _cached_token = data["data"]["token"]
                return _cached_token
            raise RuntimeError(f"OpenList 登录失败: {data.get('message')}")
    except Exception as e:
        raise RuntimeError(f"无法连接到 OpenList 服务端 ({url}): {e}")


def api_request(endpoint: str, payload: Optional[Dict[str, Any]] = None, method: str = "POST") -> Any:
    """统一向 OpenList API 发送请求并处理状态码、鉴权及自动重新握手"""
    global _cached_token
    token = get_token()
    url = f"{OPENLIST_URL}/api/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None and method != "GET" else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with http_urlopen(req, timeout=25) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            code = res.get("code")

            if code == 401:
                # Token 过期或失效，尝试重登刷新
                _cached_token = None
                token = get_token()
                headers["Authorization"] = token
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with http_urlopen(req, timeout=25) as retry_resp:
                    res = json.loads(retry_resp.read().decode("utf-8"))
                    code = res.get("code")

            if code == 200:
                return res.get("data")
            elif code == 404 and "search" in endpoint:
                raise RuntimeError("当前 OpenList 未开启全局搜索索引（可在 OpenList 管理后台 -> 设置 -> 搜索索引 中开启）。")
            else:
                raise RuntimeError(res.get("message", f"接口返回错误代码: {code}"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(str(e))


def format_size(bytes_val: int) -> str:
    """人类可读的文件大小格式化"""
    if bytes_val <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"


# ==========================================
# 核心业务实现（全功能覆盖）
# ==========================================

def tool_fs_list(path: str = "/", password: str = "", page: int = 1, per_page: int = 0, refresh: bool = False) -> str:
    """列出目录内容"""
    check_path_allowed(path)
    payload = {
        "path": path or "/",
        "password": password,
        "page": page,
        "per_page": per_page,
        "refresh": refresh
    }
    data = api_request("fs/list", payload)
    items = data.get("content") or []
    total = data.get("total", len(items))

    if not items:
        return f"目录 [{path}] 为空。"

    lines = [f"目录 [{path}] 共包含 {len(items)} 项（总计: {total}）："]
    for item in items:
        is_dir = item.get("is_dir", False)
        tag = "[目录]" if is_dir else "[文件]"
        size = format_size(item.get("size", 0)) if not is_dir else "-"
        modified = item.get("modified", "")[:19]
        lines.append(f"  {tag:<6} {item.get('name')}  (大小: {size}, 修改时间: {modified})")
    return "\n".join(lines)


def tool_fs_get(path: str, password: str = "") -> str:
    """获取单个文件或目录的元数据详细信息"""
    check_path_allowed(path)
    data = api_request("fs/get", {"path": path, "password": password})
    lines = [
        f"名称: {data.get('name')}",
        f"类型: {'目录' if data.get('is_dir') else '文件'}",
        f"大小: {format_size(data.get('size', 0))} ({data.get('size')} 字节)",
        f"存储驱动: {data.get('provider', '未知')}",
        f"修改时间: {data.get('modified', '')}",
        f"直链 (raw_url): {data.get('raw_url', '无')}",
    ]
    if data.get("sign"):
        lines.append("直链签名: [已签名受保护]")
    if data.get("readme"):
        lines.append(f"说明文档:\n{data.get('readme')}")
    return "\n".join(lines)


def tool_fs_link(path: str, password: str = "", link_type: str = "") -> str:
    """获取下载直链、并发参数与分块大小"""
    check_path_allowed(path)
    payload = {"path": path, "password": password}
    if link_type:
        payload["type"] = link_type
    data = api_request("fs/link", payload)
    lines = [
        f"文件路径: {path}",
        f"直链下载地址 (URL): {data.get('url', '无')}",
    ]
    header = data.get("header")
    if header:
        lines.append(f"推荐 HTTP 请求头: {json.dumps(header, ensure_ascii=False)}")
    if data.get("concurrency"):
        lines.append(f"推荐多线程并发数: {data.get('concurrency')}")
    if data.get("part_size"):
        lines.append(f"分块大小 (Part Size): {format_size(data.get('part_size'))}")
    return "\n".join(lines)


def tool_fs_dirs(path: str = "/", password: str = "", force_root: bool = False) -> str:
    """轻量化获取子目录结构（快速构建目录树）"""
    check_path_allowed(path)
    data = api_request("fs/dirs", {"path": path or "/", "password": password, "force_root": force_root}) or []
    if not data:
        return f"路径 [{path}] 下无子目录。"

    lines = [f"路径 [{path}] 下的子目录："]
    for d in data:
        lines.append(f"  📁 {d.get('name')} (修改时间: {d.get('modified', '')[:19]})")
    return "\n".join(lines)


def tool_fs_search(keywords: str, parent: str = "/", scope: int = 0, page: int = 1, per_page: int = 50, password: str = "") -> str:
    """跨网盘全局搜索"""
    check_path_allowed(parent)
    payload = {
        "parent": parent or "/",
        "keywords": keywords,
        "scope": scope,
        "page": page,
        "per_page": per_page,
        "password": password
    }
    data = api_request("fs/search", payload)
    items = data.get("content") or []
    if not items:
        return f"在 [{parent}] 下未搜索到包含 '{keywords}' 的文件或文件夹。"

    scope_name = {0: "全部", 1: "文件夹", 2: "文件"}.get(scope, "全部")
    lines = [f"搜索关键词 '{keywords}' (范围: {scope_name}) 共匹配到 {len(items)} 条结果："]
    for it in items:
        tag = "[目录]" if it.get("is_dir") else "[文件]"
        full_p = f"{it.get('parent', '').rstrip('/')}/{it.get('name')}"
        size = format_size(it.get("size", 0)) if not it.get("is_dir") else "-"
        lines.append(f"  {tag:<6} {full_p}  (大小: {size})")
    return "\n".join(lines)


def tool_fs_read(path: str, max_chars: int = 20000, password: str = "") -> str:
    """安全读取云盘文本文件内容（带长度截断保护）"""
    check_path_allowed(path)
    data = api_request("fs/get", {"path": path, "password": password})
    if data.get("is_dir"):
        return f"错误：[{path}] 是一个目录，不能读取为文本文件。"

    size = data.get("size", 0)
    if size > 10 * 1024 * 1024:
        return f"提示：文件大小为 {format_size(size)}，超过安全读取限制（10MB），建议直接获取直链下载。"

    raw_url = data.get("raw_url")
    req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 优先获取底层存储驱动指定的推荐下载头 (如防盗链驱动)
    try:
        link_data = api_request("fs/link", {"path": path, "password": password})
        if link_data.get("url"):
            raw_url = link_data["url"]
        for k, v in (link_data.get("header") or {}).items():
            req_headers[k] = v[0] if isinstance(v, list) else v
    except Exception:
        pass

    if not raw_url:
        return f"错误：无法获取 [{path}] 的真实内容链接。"

    req = urllib.request.Request(raw_url, headers=req_headers)
    with http_urlopen(req, timeout=25) as resp:
        raw_bytes = resp.read(max_chars + 200)

    text = raw_bytes.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... [提示：已截断，仅展示前 {max_chars} 个字符] ..."
    return text


def tool_fs_put_text(path: str, content: str) -> str:
    """直接将纯文本内容写入或覆盖更新到云盘指定路径"""
    check_write_permission("新建/覆写文本文件")
    check_path_allowed(path)
    url = f"{OPENLIST_URL}/api/fs/put"
    token = get_token()
    headers = {
        "Authorization": token,
        "File-Path": urllib.parse.quote(path),
        "Content-Type": "application/octet-stream"
    }
    data_bytes = content.encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="PUT")
    with http_urlopen(req, timeout=25) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if res.get("code") != 200:
            raise RuntimeError(res.get("message", "上传文件失败"))
    return f"成功写入文件: {path} ({len(data_bytes)} 字节)"


def tool_fs_upload_local_file(local_path: str, dst_path: str) -> str:
    """将智能体本地的文件直接上传传输到云盘指定路径"""
    check_write_permission("本地文件上传")
    check_path_allowed(dst_path)

    local_path = os.path.expanduser(local_path)
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"本地文件不存在: {local_path}")
    if os.path.isdir(local_path):
        raise ValueError(f"指定路径是目录而非文件: {local_path}")

    file_size = os.path.getsize(local_path)
    url = f"{OPENLIST_URL}/api/fs/put"
    token = get_token()
    headers = {
        "Authorization": token,
        "File-Path": urllib.parse.quote(dst_path),
        "Content-Type": "application/octet-stream"
    }

    with open(local_path, "rb") as f:
        file_bytes = f.read()

    req = urllib.request.Request(url, data=file_bytes, headers=headers, method="PUT")
    with http_urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if res.get("code") != 200:
            raise RuntimeError(res.get("message", "上传文件失败"))

    return f"成功将本地文件 [{local_path}] 上传至云盘 [{dst_path}] (共 {format_size(file_size)})"


def tool_fs_mkdir(path: str) -> str:
    """创建新文件夹"""
    check_write_permission("创建文件夹")
    check_path_allowed(path)
    api_request("fs/mkdir", {"path": path})
    return f"成功在云盘创建文件夹: {path}"


def tool_fs_rename(path: str, name: str) -> str:
    """单文件/单文件夹重命名"""
    check_write_permission("重命名")
    check_path_allowed(path)
    api_request("fs/rename", {"path": path, "name": name})
    return f"成功将 [{path}] 重命名为 [{name}]"


def tool_fs_batch_rename(src_dir: str, rename_objects: List[Dict[str, str]]) -> str:
    """批量重命名同目录下的多个文件"""
    check_write_permission("批量重命名")
    check_path_allowed(src_dir)
    api_request("fs/batch_rename", {"src_dir": src_dir, "rename_objects": rename_objects})
    return f"成功在 [{src_dir}] 下批量重命名了 {len(rename_objects)} 个文件/文件夹。"


def tool_fs_regex_rename(src_dir: str, src_name_regex: str, new_name_regex: str) -> str:
    """使用正则表达式批量重命名文件"""
    check_write_permission("正则批量重命名")
    check_path_allowed(src_dir)
    api_request("fs/regex_rename", {
        "src_dir": src_dir,
        "src_name_regex": src_name_regex,
        "new_name_regex": new_name_regex
    })
    return f"成功在 [{src_dir}] 执行正则重命名：'{src_name_regex}' -> '{new_name_regex}'"


def tool_fs_move(src_dir: str, dst_dir: str, names: List[str]) -> str:
    """移动指定文件列表到目标文件夹"""
    check_write_permission("移动文件")
    check_path_allowed(src_dir)
    check_path_allowed(dst_dir)
    api_request("fs/move", {"src_dir": src_dir, "dst_dir": dst_dir, "names": names})
    return f"成功将 [{', '.join(names)}] 从 [{src_dir}] 移动至 [{dst_dir}]"


def tool_fs_recursive_move(src_dir: str, dst_dir: str) -> str:
    """聚合递归移动（将整个目录树完整合并移动到目标目录）"""
    check_write_permission("递归聚合移动")
    check_path_allowed(src_dir)
    check_path_allowed(dst_dir)
    api_request("fs/recursive_move", {"src_dir": src_dir, "dst_dir": dst_dir})
    return f"成功递归聚合移动 [{src_dir}] 到 [{dst_dir}]"


def tool_fs_copy(src_dir: str, dst_dir: str, names: List[str]) -> str:
    """复制指定文件列表到目标文件夹"""
    check_write_permission("复制文件")
    check_path_allowed(src_dir)
    check_path_allowed(dst_dir)
    api_request("fs/copy", {"src_dir": src_dir, "dst_dir": dst_dir, "names": names})
    return f"成功将 [{', '.join(names)}] 从 [{src_dir}] 复制至 [{dst_dir}]"


def tool_fs_remove(dir_path: str, names: List[str], confirm: bool = False) -> str:
    """删除指定目录下的文件或子目录"""
    check_write_permission("删除文件/目录")
    check_path_allowed(dir_path)

    if OPENLIST_CONFIRM_REMOVE and not confirm:
        raise PermissionError(
            f"安全防误删拦截：当前环境要求确认删除，请在调用参数中传入 confirm=true 以确认删除 [{dir_path}] 下的: {', '.join(names)}"
        )

    api_request("fs/remove", {"dir": dir_path, "names": names})
    return f"成功删除 [{dir_path}] 下的: {', '.join(names)}"


def tool_fs_remove_empty_directory(src_dir: str) -> str:
    """递归清理空文件夹"""
    check_write_permission("清理空文件夹")
    check_path_allowed(src_dir)
    api_request("fs/remove_empty_directory", {"src_dir": src_dir})
    return f"成功清理 [{src_dir}] 路径下的所有空文件夹。"


def tool_fs_create_share(paths: List[str], password: str = "", expires_hours: int = 0) -> str:
    """为指定文件或目录创建分享直达链接"""
    check_write_permission("创建分享链接")
    for p in paths:
        check_path_allowed(p)

    payload = {"files": paths}
    if password:
        payload["pwd"] = password
    if expires_hours > 0:
        import time
        payload["expires"] = int(time.time()) + (expires_hours * 3600)

    data = api_request("share/create", payload)
    share_id = data.get("id", "未知")
    share_url = f"{OPENLIST_URL}/s/{share_id}"
    lines = [
        f"成功创建分享链接！",
        f"分享 ID: {share_id}",
        f"访问链接: {share_url}",
        f"包含文件/目录: {', '.join(paths)}",
    ]
    if password:
        lines.append(f"提取密码: {password}")
    if expires_hours > 0:
        lines.append(f"有效期: {expires_hours} 小时")
    return "\n".join(lines)


def tool_fs_list_shares() -> str:
    """列出当前已创建的所有分享链接"""
    data = api_request("share/list", method="GET") or {}
    items = data.get("content") or []
    if not items:
        return "当前未创建任何分享链接。"

    lines = [f"当前有效分享列表（共 {len(items)} 个）："]
    for s in items:
        status = "🔴 已禁用" if s.get("disabled") else "🟢 正常"
        pwd_info = "受密码保护 [***]" if s.get("pwd") else "公开无密"
        lines.append(
            f"  - [{s.get('id')}] {status} | 路径: {', '.join(s.get('files', []))} | {pwd_info} | 访问量: {s.get('accessed', 0)}"
        )
    return "\n".join(lines)


def tool_fs_delete_share(share_id: str) -> str:
    """删除指定的分享链接"""
    check_write_permission("删除分享链接")
    api_request(f"share/delete?id={urllib.parse.quote(share_id)}", method="POST")
    return f"成功删除分享链接 [{share_id}]。"


def tool_fs_add_offline_download(urls: List[str], path: str, tool: str = "aria2", delete_policy: str = "delete_on_upload_succeed") -> str:
    """添加离线下载任务"""
    check_write_permission("添加离线下载")
    check_path_allowed(path)
    payload = {
        "urls": urls,
        "path": path,
        "tool": tool,
        "delete_policy": delete_policy
    }
    data = api_request("fs/add_offline_download", payload)
    tasks = data.get("tasks") or []
    lines = [f"已成功提交 {len(urls)} 个离线下载任务到 [{path}]："]
    for t in tasks:
        lines.append(f"  任务ID: {t.get('id', '未知')}, 名称: {t.get('name', '未命名')}, 状态: {t.get('status', '进行中')}")
    return "\n".join(lines)


def tool_fs_list_offline_tasks() -> str:
    """查询后台正在进行中及已完成的离线下载任务"""
    undone = api_request("admin/task/offline_download/undone", method="GET") or []
    done = api_request("admin/task/offline_download/done", method="GET") or []

    lines = []
    lines.append(f"离线下载任务状态（进行中: {len(undone)}，已完成: {len(done)}）：")
    if undone:
        lines.append("【进行中任务】:")
        for t in undone:
            lines.append(f"  - [{t.get('name')}] 进度: {t.get('progress', 0)}%, 状态: {t.get('status')}")
    else:
        lines.append("【进行中任务】: 无")

    if done:
        lines.append("【最近已完成任务】:")
        for t in done[:5]:
            lines.append(f"  - [{t.get('name')}] 状态: {t.get('status', '成功')}")
    return "\n".join(lines)


def tool_fs_storage_status() -> str:
    """查询所有已挂载云盘存储驱动的健康状态与运行配置"""
    data = api_request("admin/storage/list", method="GET") or {}
    items = data.get("content") or []
    if not items:
        return "当前未挂载任何存储驱动。"

    lines = [f"已挂载的存储驱动状态清单（共 {len(items)} 个）："]
    for s in items:
        status_tag = "🟢 正常" if s.get("status") == "work" else f"🔴 {s.get('status', '异常')}"
        lines.append(f"  {status_tag:<8} 挂载路径: {s.get('mount_path'):<15} 驱动类型: {s.get('driver')}")
    return "\n".join(lines)


# ==========================================
# MCP 标准协议声明 (Tools Schema)
# ==========================================

TOOLS = [
    {
        "name": "fsList",
        "description": "列出指定网盘路径下的文件和子目录列表。同时支持别名 openlist.fs.list, list_files。支持根目录 '/' 或具体挂载网盘。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "网盘路径，如 '/' 表示根目录", "default": "/"},
                "password": {"type": "string", "description": "受保护路径密码", "default": ""},
                "page": {"type": "integer", "description": "分页页码", "default": 1},
                "per_page": {"type": "integer", "description": "每页条目数，0 为全部", "default": 0},
                "refresh": {"type": "boolean", "description": "强制刷新服务端缓存", "default": False}
            },
            "required": ["path"]
        }
    },
    {
        "name": "fsGet",
        "description": "获取某个文件或目录的元数据详细信息，包含高速直接下载直链 (raw_url)。同时支持别名 openlist.fs.get, get_file_info。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件完整挂载路径，如 '/mount_point/doc.pdf'"},
                "password": {"type": "string", "description": "受保护路径密码", "default": ""}
            },
            "required": ["path"]
        }
    },
    {
        "name": "fsLink",
        "description": "对应 OpenList 官方 openlist.fs.link 接口。获取可用直链、代理直链、推荐并发下载数及分块大小参数。支持别名 get_download_url。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件挂载路径"},
                "password": {"type": "string", "description": "受保护路径密码", "default": ""},
                "type": {"type": "string", "description": "传递给驱动的可选链接类型", "default": ""}
            },
            "required": ["path"]
        }
    },
    {
        "name": "fsDirs",
        "description": "轻量化获取指定路径下的所有子目录，不包含普通文件，适合快速构建和探索整个目录树。支持别名 list_dirs。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目标目录路径", "default": "/"},
                "password": {"type": "string", "description": "受保护路径密码", "default": ""},
                "force_root": {"type": "boolean", "description": "是否强制获取根目录", "default": False}
            }
        }
    },
    {
        "name": "fsSearch",
        "description": "跨网盘全局搜索文件或目录（需要 OpenList 服务端开启搜索索引）。支持别名 search_files。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "string", "description": "搜索关键词"},
                "parent": {"type": "string", "description": "搜索的父目录，默认 '/'", "default": "/"},
                "scope": {"type": "integer", "description": "范围：0-全部，1-文件夹，2-文件", "default": 0},
                "page": {"type": "integer", "description": "页码", "default": 1},
                "per_page": {"type": "integer", "description": "每页数量", "default": 50},
                "password": {"type": "string", "description": "受保护目录密码", "default": ""}
            },
            "required": ["keywords"]
        }
    },
    {
        "name": "fsRead",
        "description": "直接读取云盘中文本文档或代码内容（带 Token 防爆安全长度截断保护）。支持别名 read_file。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文本文件完整路径"},
                "max_chars": {"type": "integer", "description": "最大读取字符数", "default": 20000},
                "password": {"type": "string", "description": "受保护路径密码", "default": ""}
            },
            "required": ["path"]
        }
    },
    {
        "name": "fsPutText",
        "description": "直接将纯文本内容写入或覆盖更新到云盘指定路径。支持别名 write_file, put_file。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "写入的目标完整路径"},
                "content": {"type": "string", "description": "要保存的纯文本内容"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "fsUploadLocalFile",
        "description": "将智能体所在主机的本地文件直接上传到云盘目标路径。支持别名 upload_local_file。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "local_path": {"type": "string", "description": "本地文件完整绝对路径"},
                "dst_path": {"type": "string", "description": "云盘目标保存完整路径（包含文件名）"}
            },
            "required": ["local_path", "dst_path"]
        }
    },
    {
        "name": "fsMkdir",
        "description": "在指定云盘路径下新建文件夹。支持别名 create_folder。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "新文件夹完整路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "fsRename",
        "description": "重命名单个文件或文件夹。支持别名 rename。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "当前完整路径"},
                "name": {"type": "string", "description": "新文件名（不含路径）"}
            },
            "required": ["path", "name"]
        }
    },
    {
        "name": "fsBatchRename",
        "description": "批量重命名同一个目录下的多个文件对照表。支持别名 batch_rename。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_dir": {"type": "string", "description": "源文件所在目录路径"},
                "rename_objects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "src_name": {"type": "string", "description": "原文件名"},
                            "new_name": {"type": "string", "description": "新文件名"}
                        },
                        "required": ["src_name", "new_name"]
                    },
                    "description": "重命名对照列表"
                }
            },
            "required": ["src_dir", "rename_objects"]
        }
    },
    {
        "name": "fsRegexRename",
        "description": "使用正则表达式批量重命名文件（如批量清洗番剧命名或去除广告标记）。支持别名 regex_rename。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_dir": {"type": "string", "description": "操作的目标目录"},
                "src_name_regex": {"type": "string", "description": "匹配原文件名的正则表达式"},
                "new_name_regex": {"type": "string", "description": "替换后的文件名规则"}
            },
            "required": ["src_dir", "src_name_regex", "new_name_regex"]
        }
    },
    {
        "name": "fsMove",
        "description": "将指定文件列表从一个目录移动到另一个目录。支持别名 move。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_dir": {"type": "string", "description": "源目录路径"},
                "dst_dir": {"type": "string", "description": "目标目录路径"},
                "names": {"type": "array", "items": {"type": "string"}, "description": "要移动的文件/目录名称列表"}
            },
            "required": ["src_dir", "dst_dir", "names"]
        }
    },
    {
        "name": "fsRecursiveMove",
        "description": "聚合移动：将源目录及其所有子内容递归移动合并到目标目录。支持别名 recursive_move。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_dir": {"type": "string", "description": "源目录"},
                "dst_dir": {"type": "string", "description": "目标目录"}
            },
            "required": ["src_dir", "dst_dir"]
        }
    },
    {
        "name": "fsCopy",
        "description": "复制文件列表到目标目录。支持别名 copy。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_dir": {"type": "string", "description": "源目录路径"},
                "dst_dir": {"type": "string", "description": "目标目录路径"},
                "names": {"type": "array", "items": {"type": "string"}, "description": "要复制的文件/目录名称列表"}
            },
            "required": ["src_dir", "dst_dir", "names"]
        }
    },
    {
        "name": "fsRemove",
        "description": "删除指定目录下的文件或子文件夹。支持别名 remove。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dir_path": {"type": "string", "description": "目标所在的父目录"},
                "names": {"type": "array", "items": {"type": "string"}, "description": "待删除的文件或目录名列表"},
                "confirm": {"type": "boolean", "description": "确认删除标识（开启防误删模式时必传 true）", "default": False}
            },
            "required": ["dir_path", "names"]
        }
    },
    {
        "name": "fsRemoveEmptyDirectory",
        "description": "递归删除指定目录下的所有空文件夹。支持别名 remove_empty_dirs。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_dir": {"type": "string", "description": "扫描清理空目录的根路径"}
            },
            "required": ["src_dir"]
        }
    },
    {
        "name": "fsCreateShare",
        "description": "为指定的一个或多个云盘文件/目录创建对外分享链接。支持别名 create_share。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}, "description": "分享的文件或文件夹路径列表"},
                "password": {"type": "string", "description": "可选提取密码", "default": ""},
                "expires_hours": {"type": "integer", "description": "有效时长（小时，0为永久）", "default": 0}
            },
            "required": ["paths"]
        }
    },
    {
        "name": "fsListShares",
        "description": "查询当前所有已创建的有效分享链接列表。支持别名 list_shares。",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fsDeleteShare",
        "description": "删除指定的分享链接。支持别名 delete_share。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "share_id": {"type": "string", "description": "待删除的分享ID"}
            },
            "required": ["share_id"]
        }
    },
    {
        "name": "fsAddOfflineDownload",
        "description": "向 OpenList 提交离线下载任务（支持 HTTP/HTTPS/磁力链）。支持别名 add_offline_download。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "下载链接列表"},
                "path": {"type": "string", "description": "保存的云盘目录路径"},
                "tool": {"type": "string", "description": "可选 'aria2', 'SimpleHttp', 'qBittorrent'", "default": "aria2"},
                "delete_policy": {"type": "string", "description": "删除策略", "default": "delete_on_upload_succeed"}
            },
            "required": ["urls", "path"]
        }
    },
    {
        "name": "fsListOfflineTasks",
        "description": "查询 OpenList 当前正在进行的离线下载进度及已完成的任务列表。支持别名 list_offline_tasks。",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fsStorageStatus",
        "description": "查询 OpenList 当前所有已挂载存储驱动的连接健康状态与运行配置。支持别名 storage_status。",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


# ==========================================
# JSON-RPC 2.0 协议分发处理（含全别名路由）
# ==========================================

def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "openlist-mcp-server",
                    "version": "1.3.0"
                }
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        }
    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            # 路由到各个工具（全面支持官方规范 openlist.fs.* 及主流平替别名）
            if tool_name in ["fsList", "openlist.fs.list", "list_files"]:
                text = tool_fs_list(
                    path=args.get("path", "/"),
                    password=args.get("password", ""),
                    page=args.get("page", 1),
                    per_page=args.get("per_page", 0),
                    refresh=args.get("refresh", False)
                )
            elif tool_name in ["fsGet", "openlist.fs.get", "get_file_info"]:
                text = tool_fs_get(path=args.get("path"), password=args.get("password", ""))
            elif tool_name in ["fsLink", "openlist.fs.link", "get_download_url"]:
                text = tool_fs_link(path=args.get("path"), password=args.get("password", ""), link_type=args.get("type", ""))
            elif tool_name in ["fsDirs", "list_dirs"]:
                text = tool_fs_dirs(
                    path=args.get("path", "/"),
                    password=args.get("password", ""),
                    force_root=args.get("force_root", False)
                )
            elif tool_name in ["fsSearch", "search_files"]:
                text = tool_fs_search(
                    keywords=args.get("keywords", ""),
                    parent=args.get("parent", "/"),
                    scope=args.get("scope", 0),
                    page=args.get("page", 1),
                    per_page=args.get("per_page", 50),
                    password=args.get("password", "")
                )
            elif tool_name in ["fsRead", "read_file"]:
                text = tool_fs_read(
                    path=args.get("path"),
                    max_chars=args.get("max_chars", 20000),
                    password=args.get("password", "")
                )
            elif tool_name in ["fsPutText", "write_file", "put_file"]:
                text = tool_fs_put_text(path=args.get("path"), content=args.get("content", ""))
            elif tool_name in ["fsUploadLocalFile", "upload_local_file", "openlist.fs.upload_local_file"]:
                text = tool_fs_upload_local_file(local_path=args.get("local_path"), dst_path=args.get("dst_path"))
            elif tool_name in ["fsMkdir", "create_folder"]:
                text = tool_fs_mkdir(path=args.get("path"))
            elif tool_name in ["fsRename", "rename"]:
                text = tool_fs_rename(path=args.get("path"), name=args.get("name"))
            elif tool_name in ["fsBatchRename", "batch_rename"]:
                text = tool_fs_batch_rename(src_dir=args.get("src_dir"), rename_objects=args.get("rename_objects", []))
            elif tool_name in ["fsRegexRename", "regex_rename"]:
                text = tool_fs_regex_rename(
                    src_dir=args.get("src_dir"),
                    src_name_regex=args.get("src_name_regex"),
                    new_name_regex=args.get("new_name_regex")
                )
            elif tool_name in ["fsMove", "move"]:
                text = tool_fs_move(src_dir=args.get("src_dir"), dst_dir=args.get("dst_dir"), names=args.get("names", []))
            elif tool_name in ["fsRecursiveMove", "recursive_move"]:
                text = tool_fs_recursive_move(src_dir=args.get("src_dir"), dst_dir=args.get("dst_dir"))
            elif tool_name in ["fsCopy", "copy"]:
                text = tool_fs_copy(src_dir=args.get("src_dir"), dst_dir=args.get("dst_dir"), names=args.get("names", []))
            elif tool_name in ["fsRemove", "remove"]:
                d = args.get("dir") or args.get("dir_path")
                text = tool_fs_remove(dir_path=d, names=args.get("names", []), confirm=args.get("confirm", False))
            elif tool_name in ["fsRemoveEmptyDirectory", "remove_empty_dirs"]:
                text = tool_fs_remove_empty_directory(src_dir=args.get("src_dir"))
            elif tool_name in ["fsCreateShare", "create_share", "openlist.share.create"]:
                text = tool_fs_create_share(
                    paths=args.get("paths", []),
                    password=args.get("password", ""),
                    expires_hours=args.get("expires_hours", 0)
                )
            elif tool_name in ["fsListShares", "list_shares", "openlist.share.list"]:
                text = tool_fs_list_shares()
            elif tool_name in ["fsDeleteShare", "delete_share", "openlist.share.delete"]:
                text = tool_fs_delete_share(share_id=args.get("share_id") or args.get("id"))
            elif tool_name in ["fsAddOfflineDownload", "add_offline_download"]:
                text = tool_fs_add_offline_download(
                    urls=args.get("urls", []),
                    path=args.get("path"),
                    tool=args.get("tool", "aria2"),
                    delete_policy=args.get("delete_policy", "delete_on_upload_succeed")
                )
            elif tool_name in ["fsListOfflineTasks", "list_offline_tasks"]:
                text = tool_fs_list_offline_tasks()
            elif tool_name in ["fsStorageStatus", "storage_status"]:
                text = tool_fs_storage_status()
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"未找到对应工具: {tool_name}"}
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"调用失败: {e}"}],
                    "isError": True
                }
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"不支持的协议方法: {method}"}
    }


def main():
    """主事件循环 (stdio JSON-RPC)"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            req = json.loads(line)
            res = handle_request(req)
            if res is not None:
                sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"Error handling request: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
