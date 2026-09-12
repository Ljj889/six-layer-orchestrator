#!/usr/bin/env python3
"""L3 输出校验脚本（框架对齐 v3.16.0）：校验子 Agent 返回的 JSON 是否符合约定 schema。

用法:
    python validate_output.py <output.json> <schema.json>

schema.json 支持的格式（简化版 JSON Schema）:
    {
      "required": ["module", "code"],
      "properties": {
        "module": {"type": "string"},
        "code": {"type": "string"},
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "checks": {"type": "array", "items": {"type": "object"}},
        "pass": {"type": "boolean"},
        "modules": {"type": "array", "items": {"type": "object"}}
      }
    }

退出码: 0 = 通过; 1 = 校验失败（字段缺失/类型错误/枚举不符）。
"""

import json
import sys
from pathlib import Path


def load(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_type(value, expected: str, path: str, errors: list) -> None:
    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    if expected not in type_map:
        return
    if not isinstance(value, type_map[expected]):
        errors.append(f"{path}: 期望 {expected}，实际 {type(value).__name__}")


def validate(data, schema, path="root", errors=None):
    if errors is None:
        errors = []
    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"{path}.{field}: 缺失必填字段")
            continue
        prop = schema.get("properties", {}).get(field, {})
        if "type" in prop:
            check_type(data[field], prop["type"], f"{path}.{field}", errors)
        if "enum" in prop and data[field] not in prop["enum"]:
            errors.append(f"{path}.{field}: 值 {data[field]!r} 不在枚举 {prop['enum']} 中")
        if "items" in prop and prop["type"] == "array" and isinstance(data[field], list):
            for i, item in enumerate(data[field]):
                validate(item, prop["items"], f"{path}.{field}[{i}]", errors)
    return errors


def _force_utf8_stdio():
    """stdio 加固（v3.16.0）：Windows 控制台默认 GBK 下非 ASCII 输出会 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    _force_utf8_stdio()
    if len(sys.argv) != 3:
        print("用法: python validate_output.py <output.json> <schema.json>")
        return 2
    try:
        data = load(Path(sys.argv[1]))
        schema = load(Path(sys.argv[2]))
    except Exception as e:
        print(f"读取/解析失败: {e}")
        return 2
    errors = validate(data, schema)
    if errors:
        print("校验失败:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("校验通过: 字段完整，类型正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
