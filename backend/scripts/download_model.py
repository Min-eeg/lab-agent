# -*- coding: utf-8 -*-
"""从 ModelScope(魔搭社区) 下载 bge-small-zh-v1.5 模型到本地。
用法: python scripts/download_model.py
下载后 kb_service.py 会优先加载本地模型, 不再联网。
"""
import os
import sys
import time
import urllib.parse
import urllib.request

REPO = "BAAI/bge-small-zh-v1.5"
API = f"https://modelscope.cn/api/v1/models/{REPO}/repo"
# sentence-transformers 加载所需的最小文件集
FILES = [
    "1_Pooling/config.json",
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "model.safetensors",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(BASE_DIR, "data", "models", "bge-small-zh-v1.5")


def download(rel_path: str) -> None:
    url = f"{API}?FilePath={urllib.parse.quote(rel_path)}"
    out = os.path.join(DEST, *rel_path.split("/"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lab-agent"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(out, "wb") as f:
                total, done = 0, 0
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if done // (1024 * 1024) > total:
                        total = done // (1024 * 1024)
                        print(f"\r  {rel_path}: {total} MB", end="", flush=True)
            print(f"\r  {rel_path}: {done} bytes  OK")
            return
        except Exception as e:
            print(f"  {rel_path} 第{attempt}次失败: {type(e).__name__} {e}")
            time.sleep(3)
    raise RuntimeError(f"下载失败: {rel_path}")


def main() -> None:
    os.makedirs(DEST, exist_ok=True)
    print(f"目标目录: {DEST}")
    for rel in FILES:
        out = os.path.join(DEST, *rel.split("/"))
        if os.path.exists(out) and os.path.getsize(out) > 0:
            print(f"  {rel}: 已存在, 跳过")
            continue
        download(rel)
    print("全部下载完成")


if __name__ == "__main__":
    sys.exit(main())
