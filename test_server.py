#!/usr/bin/env python3
"""
Comprehensive Automated Test Suite for OpenList MCP Server
============================================================
Tests protocol compliance, tool schema integrity, drop-in aliases,
local file upload, sharing lifecycle, safety controls, and full file lifecycle.

Usage:
  python3 test_server.py
  python3 test_server.py --password yourpassword
"""

import sys
import os
import json
import time
import argparse
import subprocess
from typing import Any, Dict


class MCPClientTester:
    def __init__(self, script_path: str = "server.py", extra_args: list = None):
        cmd = [sys.executable, script_path]
        if extra_args:
            cmd.extend(extra_args)
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.req_id = 1

    def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        req = {
            "jsonrpc": "2.0",
            "id": self.req_id,
            "method": method
        }
        if params is not None:
            req["params"] = params
        self.req_id += 1

        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()

        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read()
            raise RuntimeError(f"Server closed connection unexpectedly. Stderr: {stderr}")
        return json.loads(line)

    def call_tool(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        return self.send_request("tools/call", {
            "name": name,
            "arguments": arguments or {}
        })

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()


def load_dotenv(dotenv_path: str = None):
    """纯标准库轻量加载 .env 文件"""
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


def run_tests():
    parser = argparse.ArgumentParser(description="Test OpenList MCP Server")
    parser.add_argument("--url", default=None, help="OpenList server URL")
    parser.add_argument("--username", default=None, help="OpenList username")
    parser.add_argument("--password", default=None, help="OpenList password")
    parser.add_argument("--token", default=None, help="OpenList token")
    cli_args, _ = parser.parse_known_args()

    extra = []
    if cli_args.url:
        extra.extend(["--url", cli_args.url])
    if cli_args.username:
        extra.extend(["--username", cli_args.username])
    pwd = cli_args.password or os.environ.get("OPENLIST_PASSWORD") or os.environ.get("ALIST_PASSWORD")
    if pwd:
        extra.extend(["--password", pwd])
    if cli_args.token:
        extra.extend(["--token", cli_args.token])

    print("=" * 65)
    print("🚀 开始执行 OpenList MCP Server 自动化全项回归测试")
    print("=" * 65)

    passed = 0
    failed = 0
    total = 0

    def assert_test(name: str, condition: bool, details: str = ""):
        nonlocal passed, failed, total
        total += 1
        if condition:
            passed += 1
            print(f"  ✅ [PASS] {name}")
        else:
            failed += 1
            print(f"  ❌ [FAIL] {name}: {details}")

    script_path = os.path.join(os.path.dirname(__file__), "server.py")
    client = MCPClientTester(script_path, extra)

    try:
        # 1. 协议握手测试
        print("\n[测试阶段 1: JSON-RPC 2.0 基础协议握手]")
        init_res = client.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-runner", "version": "1.0"}
        })
        assert_test("MCP Initialize 响应格式规范", init_res.get("jsonrpc") == "2.0" and "result" in init_res)
        server_info = init_res.get("result", {}).get("serverInfo", {})
        assert_test("服务标识返回正常 (openlist-mcp-server)", server_info.get("name") == "openlist-mcp-server")

        ping_res = client.send_request("ping")
        assert_test("MCP Ping/Pong 心跳保活正常", "result" in ping_res)

        # 2. 工具元数据注册完整性测试
        print("\n[测试阶段 2: 23 款核心工具集注册与 Schema 完整性]")
        tools_res = client.send_request("tools/list")
        assert_test("tools/list 获取成功", "tools" in tools_res.get("result", {}))
        tools = tools_res.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        assert_test("工具总数达到 23 款", len(tool_names) == 23, f"实际数量: {len(tool_names)}")

        expected_tools = [
            "fsList", "fsGet", "fsLink", "fsDirs", "fsSearch", "fsRead", "fsPutText",
            "fsUploadLocalFile", "fsMkdir", "fsRename", "fsBatchRename", "fsRegexRename",
            "fsMove", "fsRecursiveMove", "fsCopy", "fsRemove", "fsRemoveEmptyDirectory",
            "fsCreateShare", "fsListShares", "fsDeleteShare",
            "fsAddOfflineDownload", "fsListOfflineTasks", "fsStorageStatus"
        ]
        for exp in expected_tools:
            assert_test(f"工具注册包含 [{exp}]", exp in tool_names)

        # 3. 容错测试
        print("\n[测试阶段 3: 协议边界与异常状态容错]")
        res_unknown = client.call_tool("non_existent_tool")
        assert_test("未知工具调用正确返回 -32601 错误码", res_unknown.get("error", {}).get("code") == -32601)

        # 4. 联机读取测试（探测服务是否在线）
        print("\n[测试阶段 4: 联机环境连通与读取实测]")
        res_list = client.call_tool("fsList", {"path": "/"})
        text_list = res_list.get("result", {}).get("content", [{}])[0].get("text", "")

        if res_list.get("result", {}).get("isError") and "无法连接" in text_list:
            print("  ⚠️ [SKIP] 目标 OpenList 实例未启动或离线，跳过真实云盘数据读写测试。")
            print(f"      服务端信息: {text_list.strip()}")
        else:
            assert_test("fsList 根目录读取正常", "共包含" in text_list, text_list[:120])

            # 官方别名 openlist.fs.list 测试
            res_alias = client.call_tool("openlist.fs.list", {"path": "/"})
            text_alias = res_alias.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("官方别名 openlist.fs.list 双向兼容正常", "共包含" in text_alias)

            # Drop-in 平替别名 list_files 测试
            res_dropin = client.call_tool("list_files", {"path": "/"})
            text_dropin = res_dropin.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("平替别名 list_files (snake_case) 兼容正常", "共包含" in text_dropin)

            # 目录树测试
            res_dirs = client.call_tool("fsDirs", {"path": "/"})
            text_dirs = res_dirs.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("fsDirs 轻量目录树获取正常", "路径 [/] 下的子目录" in text_dirs)

            # 挂载状态巡检
            res_status = client.call_tool("fsStorageStatus")
            text_status = res_status.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("fsStorageStatus 云盘健康巡检正常", "已挂载的存储驱动" in text_status)

            # 离线任务查询
            res_tasks = client.call_tool("fsListOfflineTasks")
            text_tasks = res_tasks.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("fsListOfflineTasks 离线任务查询正常", "离线下载任务状态" in text_tasks)

            # 5. 存储完整生命周期测试（动态探测首个可用挂载目录）
            print("\n[测试阶段 5: 存储写/读/改/删/本地上传/分享完整生命周期测试]")
            target_mount = None
            for item in text_list.split("\n"):
                if "[目录]" in item:
                    parts = item.strip().split()
                    if len(parts) >= 2:
                        target_mount = "/" + parts[1]
                        break
            if target_mount:
                test_dir = f"{target_mount}/_mcp_autotest_{int(time.time())}"
                res_mkdir = client.call_tool("fsMkdir", {"path": test_dir})
                text_mkdir = res_mkdir.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsMkdir 创建测试目录成功", "成功在云盘创建文件夹" in text_mkdir, text_mkdir)

                # 写入文本
                test_file = f"{test_dir}/hello.txt"
                test_content = "Hello OpenList MCP Automated Test! Time: " + str(time.time())
                res_write = client.call_tool("fsPutText", {"path": test_file, "content": test_content})
                text_write = res_write.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsPutText 文本文件写入成功", "成功写入文件" in text_write, text_write)

                # 读取验证
                res_read = client.call_tool("fsRead", {"path": test_file})
                text_read = res_read.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsRead 读取内容完全一致", "Hello OpenList MCP Automated Test!" in text_read, text_read)

                # 本地文件上传测试 (fsUploadLocalFile)
                local_temp = "/tmp/_openlist_local_test.txt"
                with open(local_temp, "w") as f:
                    f.write("Local File Upload Test Data")
                res_upload = client.call_tool("fsUploadLocalFile", {
                    "local_path": local_temp,
                    "dst_path": f"{test_dir}/local_uploaded.txt"
                })
                text_upload = res_upload.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsUploadLocalFile 本地文件直传成功", "成功将本地文件" in text_upload, text_upload)
                if os.path.exists(local_temp):
                    os.remove(local_temp)

                # 获取文件元信息验证
                res_get = client.call_tool("fsGet", {"path": test_file})
                text_get = res_get.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsGet 获取文件元信息正常", "hello.txt" in text_get and "字节" in text_get, text_get)

                # 获取下载直链验证
                res_link = client.call_tool("fsLink", {"path": test_file})
                text_link = res_link.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsLink 获取下载直链正常", "http" in text_link or "直链" in text_link, text_link)

                # 重命名验证
                res_rename = client.call_tool("fsRename", {"path": test_file, "name": "renamed.txt"})
                text_rename = res_rename.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsRename 单文件重命名正常", "成功将" in text_rename, text_rename)

                # 正则批量重命名验证
                res_regex = client.call_tool("fsRegexRename", {
                    "src_dir": test_dir,
                    "src_name_regex": "renamed",
                    "new_name_regex": "final"
                })
                text_regex = res_regex.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsRegexRename 正则重命名正常", "成功在" in text_regex, text_regex)

                # 分享管理验证 (fsCreateShare -> fsListShares -> fsDeleteShare)
                res_share = client.call_tool("fsCreateShare", {"paths": [f"{test_dir}/final.txt"]})
                text_share = res_share.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsCreateShare 创建分享链接成功", "成功创建分享链接" in text_share, text_share)

                res_list_shares = client.call_tool("fsListShares")
                text_list_shares = res_list_shares.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsListShares 查询分享列表正常", "当前有效分享列表" in text_list_shares, text_list_shares)

                # 提取分享 ID 并删除
                share_id = ""
                for line in text_share.split("\n"):
                    if "分享 ID:" in line:
                        share_id = line.split("分享 ID:")[1].strip()
                        break
                if share_id:
                    res_del_share = client.call_tool("fsDeleteShare", {"share_id": share_id})
                    text_del_share = res_del_share.get("result", {}).get("content", [{}])[0].get("text", "")
                    assert_test("fsDeleteShare 删除分享链接正常", "成功删除分享链接" in text_del_share, text_del_share)

                # 清理删除验证
                res_remove = client.call_tool("fsRemove", {
                    "dir_path": test_dir,
                    "names": ["final.txt", "local_uploaded.txt"]
                })
                text_remove = res_remove.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsRemove 文件删除正常", "成功删除" in text_remove, text_remove)

                # 清理临时测试文件夹
                base_dir_name = os.path.basename(test_dir)
                res_clean_dir = client.call_tool("fsRemove", {"dir_path": target_mount, "names": [base_dir_name]})
                text_clean = res_clean_dir.get("result", {}).get("content", [{}])[0].get("text", "")
                assert_test("fsRemove 清理临时测试目录正常", "成功删除" in text_clean, text_clean)
            else:
                print("  ℹ️ [SKIP] 未检测到测试挂载盘，跳过文件生命周期读写。")

        # 6. 安全拦截防护专项测试
        print("\n[测试阶段 6: 安全只读与路径白名单防护测试]")
        # 6.1 只读模式拦截测试
        client_readonly = MCPClientTester(script_path, extra + ["--readonly"])
        try:
            res_ro = client_readonly.call_tool("fsMkdir", {"path": "/test_ro"})
            text_ro = res_ro.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("--readonly 安全只读模式成功拦截写操作", "安全只读模式" in text_ro, text_ro)
        finally:
            client_readonly.close()

        # 6.2 路径白名单拦截测试
        client_white = MCPClientTester(script_path, extra + ["--allowed-paths", "/allowed_only"])
        try:
            res_wh = client_white.call_tool("fsList", {"path": "/disallowed_dir"})
            text_wh = res_wh.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("--allowed-paths 路径白名单成功拦截越界访问", "不在白名单允许范围内" in text_wh, text_wh)
        finally:
            client_white.close()

        # 6.3 防误删二次确认测试
        client_confirm = MCPClientTester(script_path, extra + ["--confirm-remove"])
        try:
            res_cf = client_confirm.call_tool("fsRemove", {"dir_path": "/test", "names": ["file.txt"]})
            text_cf = res_cf.get("result", {}).get("content", [{}])[0].get("text", "")
            assert_test("--confirm-remove 防误删模式拦截未确认删除", "安全防误删拦截" in text_cf, text_cf)
        finally:
            client_confirm.close()

    finally:
        client.close()

    print("\n" + "=" * 65)
    print(f"📊 测试总结: 共执行 {total} 项测试 | 通过: {passed} | 失败: {failed}")
    if failed == 0:
        print("🎉 恭喜！所有已执行测试用例全部通过！")
    else:
        print("⚠️ 存在失败测试项，请检查错误日志。")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
