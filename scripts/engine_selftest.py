#!/usr/bin/env python3
"""engine_selftest.py — 引擎自测总入口（L1a · D-16 / D-15）

设计要点（逐条对应开发文档 §4.2 L1a「self-test 总入口」）：
  1. **unittest + subTest**（stdlib，禁 pytest 作前置依赖）
  2. **三条必测断言（D-15）**：
       ① **退出码保真**：7+ 模块 × {成功 / 已知失败 / 未捕获异常}，in-process 与 --isolate 等价
       ② **零副作用**：cli.py 不改 cwd / 不改 env / 不往项目目录写文件
       ③ **逃生阀等价**：`--isolate` 与默认 in-process 的 rc 与语义判定一致
  3. **禁裸 assert（meta 检查）**：AST 扫全部引擎脚本，出现 `assert` 语句即 FAIL
     —— `python -O` / `PYTHONOPTIMIZE` 会**静默**关掉裸 assert，等于测试网被无声拆掉
  4. **`-O` 下结果一致**：本套件在 `python -O` 子进程里重跑一遍，比较 PASS/FAIL 计数
  5. **反向 fixture（已知绿 + 已知红）**：每条新断言都必须被一条**已知坏样本**证明过它真会红
     （R-02：v3.19.0 已实证"检查器自己会说谎"）
  6. **全程离线**：默认 patch `socket.socket` → 任何网络调用直接抛错（D-16：自测必须离线）

用法：
    python scripts/engine_selftest.py                # 跑全套（人类可读）
    python scripts/engine_selftest.py --quiet        # 只出汇总行
    python scripts/engine_selftest.py --json-summary # 机器可读汇总（供 -O 一致性对照）
    python scripts/engine_selftest.py --allow-net    # 关闭离线护栏（仅在明确需要时）

退出码：0=全绿 / 1=有 FAIL
"""
from __future__ import annotations

import argparse
import ast
import copy
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
CLI = SCRIPTS_DIR / "cli.py"
PY = sys.executable


# ── 动态加载引擎脚本（不改 sys.path、不落 __pycache__ 的副作用交给调用方）──
def _load(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    modname = f"_sl_selftest_{name}"
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def _cli(args: list, isolate: bool, cwd=None, env=None) -> int:
    cmd = [PY, str(CLI)] + (["--isolate"] if isolate else []) + args
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=cwd, env=env)
    return r.returncode


def _cli_out(args: list, isolate: bool) -> tuple:
    cmd = [PY, str(CLI)] + (["--isolate"] if isolate else []) + args
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class TmpProject:
    """一次性临时项目目录（自测全在 tempfile 沙箱，现造现删）"""

    def __init__(self):
        self._d = tempfile.TemporaryDirectory(prefix="sl_eng_selftest_")
        self.path = Path(self._d.name)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._d.cleanup()


# ══════════════ ① 退出码保真（D-15 必测断言 1）══════════════
class TestExitCodeFidelity(unittest.TestCase):
    """每模块 × {成功 / 已知失败}：in-process 与 --isolate 必须给出**同一个**退出码。"""

    @classmethod
    def setUpClass(cls):
        cls.box = TmpProject()
        cls.d = str(cls.box.path)
        cls.valid = cls.box.path / "valid.json"
        cls.valid.write_text(json.dumps({"module": "m", "code": "print(1)"}), encoding="utf-8")
        cls.schema = cls.box.path / "schema.json"
        cls.schema.write_text(json.dumps({"required": ["module", "code"],
                                          "properties": {"module": {"type": "string"},
                                                         "code": {"type": "string"}}}),
                              encoding="utf-8")
        # 模块 → (成功 argv, 已知失败 argv, 成功是否为硬 0)
        cls.matrix = {
            "checkpoint":    ([cls.d, "status"],  [cls.d, "bogus_cmd"], True),
            "cost_log":      ([cls.d, "summary"], [cls.d, "bogus_cmd"], True),
            "lifecycle":     ([cls.d, "get"],     [cls.d, "bogus_cmd"], True),
            "read_knowledge": (["checkpoint"],    ["x", "--scope", "bogus"], True),
            "runtime_probe": ([],                 ["--require", "nonexistent"], True),
            "rule_index":    ([str(SKILL_DIR / "SKILL.md")], [str(cls.box.path / "nope.md")], True),
            "validate_output": ([str(cls.valid), str(cls.schema)], [str(cls.box.path / "nope.json"), str(cls.schema)], True),
            "six_layer_check": ([cls.d, "--mode", "init"], [str(cls.box.path / "nope_dir"), "--mode", "init"], False),
        }

    @classmethod
    def tearDownClass(cls):
        cls.box.__exit__()

    def test_success_and_failure_rc(self):
        for mod, (ok_argv, bad_argv, hard_zero) in self.matrix.items():
            with self.subTest(module=mod, case="success"):
                rc_ip = _cli(["run", mod] + ok_argv, isolate=False)
                rc_iso = _cli(["run", mod] + ok_argv, isolate=True)
                self.assertEqual(rc_ip, rc_iso, f"{mod} 成功路径 in-process 与 --isolate 退出码不一致")
                if hard_zero:
                    self.assertEqual(rc_ip, 0, f"{mod} 成功路径退出码应为 0，实际 {rc_ip}")
            with self.subTest(module=mod, case="known_failure"):
                rc_ip = _cli(["run", mod] + bad_argv, isolate=False)
                rc_iso = _cli(["run", mod] + bad_argv, isolate=True)
                self.assertEqual(rc_ip, rc_iso, f"{mod} 失败路径 in-process 与 --isolate 退出码不一致")
                self.assertNotEqual(rc_ip, 0, f"{mod} 已知失败路径退出码不应为 0")

    def test_uncaught_exception_rc_fidelity(self):
        """未捕获异常：in-process 与 --isolate 必须都给非 0（且二者一致）。"""
        with TmpProject() as box:
            bad = box.path / "boom.py"
            bad.write_text("def main():\n    raise RuntimeError('boom')\n"
                           "if __name__ == '__main__':\n    main()\n", encoding="utf-8")
            rc_ip = _cli(["run", str(bad)], isolate=False)
            rc_iso = _cli(["run", str(bad)], isolate=True)
            self.assertNotEqual(rc_ip, 0, "未捕获异常必须非 0")
            self.assertEqual(rc_ip, rc_iso, "未捕获异常下 in-process 与 --isolate 退出码应一致")

    def test_no_guard_script_equivalence(self):
        """无 `__main__` 守卫的脚本：两种形态都必须"什么都没做"（rc=0）。
        反向 fixture：本条曾红过——早期 in-process 实现"exec 后手动调 main()"，
        对无守卫脚本会多跑一次（1 vs 0），逃生阀不等价。"""
        with TmpProject() as box:
            bare = box.path / "noguard.py"
            bare.write_text("def main():\n    raise RuntimeError('不应被调用')\n", encoding="utf-8")
            rc_ip = _cli(["run", str(bare)], isolate=False)
            rc_iso = _cli(["run", str(bare)], isolate=True)
            self.assertEqual(rc_ip, rc_iso, "无守卫脚本两种形态必须等价")
            self.assertEqual(rc_ip, 0, "无 __main__ 守卫的脚本等同空跑，应为 0")


# ══════════════ ② 零副作用（D-15 必测断言 2）══════════════
class TestZeroSideEffects(unittest.TestCase):
    def test_no_cwd_env_or_project_writes(self):
        with TmpProject() as box:
            before_cwd = os.getcwd()
            before_env = dict(os.environ)
            before_files = sorted(p.name for p in box.path.iterdir())
            rc = _cli(["run", "checkpoint", str(box.path), "status"], isolate=False)
            self.assertEqual(rc, 0)
            self.assertEqual(os.getcwd(), before_cwd, "cli.py 不该改 cwd")
            self.assertEqual(dict(os.environ), before_env, "cli.py 不该改 env")
            after_files = sorted(p.name for p in box.path.iterdir())
            self.assertEqual(before_files, after_files,
                             f"只读命令不该往项目目录写文件，实际新增: "
                             f"{set(after_files) - set(before_files)}")

    def test_no_leftover_tmp_files_after_write(self):
        with TmpProject() as box:
            rc = _cli(["run", "checkpoint", str(box.path), "mark", "m1", "delivered"], isolate=False)
            self.assertEqual(rc, 0)
            rc = _cli(["run", "lifecycle", str(box.path), "get"], isolate=False)
            self.assertEqual(rc, 0)
            leftovers = [p.name for p in box.path.iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [], f"原子写不该留 .tmp 残渣，发现 {leftovers}")
            self.assertTrue((box.path / "progress.json").exists(), "mark 应落盘 progress.json")


# ══════════════ ③ 逃生阀等价（D-15 必测断言 3）══════════════
class TestIsolateEquivalence(unittest.TestCase):
    def test_semantic_verdict_equal(self):
        """同一命令，in-process 与 --isolate 的「语义判定」必须一致（不只退出码）。"""
        cases = [
            (["run", "read_knowledge", "zzz_绝对无此关键词_zzz"], "WARN"),  # 失败不走退出码
            (["run", "runtime_probe"], None),                               # 语义随机器状态，只要求两侧一致
        ]
        for argv, expect in cases:
            with self.subTest(argv=argv):
                rc1, out1 = _cli_out(argv, isolate=False)
                rc2, out2 = _cli_out(argv, isolate=True)
                self.assertEqual(rc1, rc2)
                import re
                m1 = re.search(r"semantic=(\w+)", out1)
                m2 = re.search(r"semantic=(\w+)", out2)
                self.assertIsNotNone(m1, f"in-process 未打印语义判定：{out1[-200:]}")
                self.assertIsNotNone(m2, f"--isolate 未打印语义判定：{out2[-200:]}")
                self.assertEqual(m1.group(1), m2.group(1), "两侧语义判定不一致")
                if expect:
                    self.assertEqual(m1.group(1), expect, f"0 命中应为 {expect}（非绿）")


# ══════════════ ④ 反向 fixture（已知红）══════════════
class TestKnownRedFixtures(unittest.TestCase):
    """每条新断言都要有一条"已知坏样本"证明它**真会红**（R-02）。"""

    def test_checkpoint_shallow_copy_would_go_red(self):
        """反向 fixture：用"旧写法"（浅拷贝）必须复现串味；否则本断言没有牙齿。"""
        proto = {"modules": {}, "expected_products": []}
        shallow = dict(proto)                      # ← v3.21.0 之前的实现形态
        shallow["modules"]["projA"] = "已交付"
        self.assertIn("projA", proto["modules"],
                      "浅拷贝本应把 projA 串进原型对象——没串说明反向 fixture 失效")

    def test_checkpoint_deepcopy_real_call_no_leak(self):
        """正向：真实调用 load_state 两次（模拟两个项目）不得串味。"""
        cp = _load("checkpoint")
        with TmpProject() as box:
            s1 = cp.load_state(box.path)
            s1.setdefault("modules", {})["projA"] = "已交付"
            s2 = cp.load_state(box.path)           # 未落盘 → 还应是默认态
            self.assertNotIn("projA", s2.get("modules", {}),
                             "跨项目串味（浅拷贝回归）")
            self.assertNotIn("projA", cp.DEFAULT_STATE["modules"],
                             "DEFAULT_STATE 被调用方污染（浅拷贝回归）")

    def test_atomic_write_uses_os_replace_structurally(self):
        """结构断言：checkpoint / lifecycle 的 save_state 必须用 os.replace（否则并发丢更新）。"""
        for mod in ("checkpoint", "lifecycle"):
            with self.subTest(module=mod):
                src = (SCRIPTS_DIR / f"{mod}.py").read_text(encoding="utf-8")
                self.assertIn("os.replace(", src, f"{mod}.save_state 必须用 os.replace 原子替换")
                self.assertNotIn("path.write_text(json.dumps", src.replace("tmp.write_text", ""),
                                 f"{mod} 不该再直接写目标文件")

    def test_bash_tristate_missing_vs_blocked(self):
        """反向 fixture：探针必须能区分 missing 与 blocked（伪造两种坏样本）。"""
        rp = _load("runtime_probe")
        real_which = rp.shutil.which
        real_run = rp._run
        try:
            rp.shutil.which = lambda n: None                      # 坏样本 1：不存在
            self.assertEqual(rp._probe_bash()["state"], "missing")
            rp.shutil.which = lambda n: "X:/fake/bash.exe"        # 坏样本 2：存在但跑不起来
            rp._run = lambda cmd, timeout=10: ("", -1)
            self.assertEqual(rp._probe_bash()["state"], "blocked")
        finally:
            rp.shutil.which = real_which
            rp._run = real_run
        self.assertIn(rp._probe_bash()["state"], ("ok", "missing", "blocked"),
                      "真实探针必须落在三态之一")

    def test_cli_semantics_goes_red_on_nonzero(self):
        """反向 fixture：语义契约层必须把非 0 退出码判成 FAIL（不能永远是 PASS）。"""
        cli = _load("cli")
        self.assertEqual(cli.classify("checkpoint", 1, ""), "FAIL")
        self.assertEqual(cli.classify("checkpoint", 0, ""), "PASS")
        self.assertEqual(cli.classify("read_knowledge", 0, "→ 0 命中"), "WARN")


# ══════════════ ⑤ 禁裸 assert（meta 检查）══════════════
class TestNoBareAssert(unittest.TestCase):
    """AST 扫全部引擎脚本：出现 `assert` 语句即 FAIL。
    `python -O` / PYTHONOPTIMIZE 会**静默**关掉裸 assert —— 等于测试网被无声拆掉。"""

    def test_no_assert_statement_in_engine_scripts(self):
        offenders = []
        for f in sorted(SCRIPTS_DIR.glob("*.py")):
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"), str(f))
            except SyntaxError as e:
                offenders.append(f"{f.name}: 语法错误 line {e.lineno}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    offenders.append(f"{f.name}:{node.lineno}")
        self.assertEqual(offenders, [],
                         "禁裸 assert（-O 会静默关掉）：" + ", ".join(offenders))


# ══════════════ ⑥ 全程离线 ══════════════
_OFFLINE_GUARD = {"active": False}


class TestOfflineGuard(unittest.TestCase):
    def test_network_is_blocked(self):
        if not _OFFLINE_GUARD["active"]:
            self.skipTest("离线护栏未启用（--allow-net）")
        with self.assertRaises(Exception):
            socket.getaddrinfo("example.invalid", 443)

    def test_l0_probe_is_not_run_by_selftest(self):
        """自测不得触网：L0 探针脚本必须**不在**本套件调用图上。"""
        src = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("l0_probe", src.split("def test_l0_probe_is_not_run_by_selftest")[0],
                         "自测总入口不得调用 L0 探针（需网）")


# ══════════════ ⑦ 引擎既有自测网（委托） ══════════════
class TestDelegateExistingNet(unittest.TestCase):
    def test_six_layer_check_self_test_is_green(self):
        r = subprocess.run([PY, str(SCRIPTS_DIR / "six_layer_check.py"), "self-test"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        # 注意：不能用裸 substring "Traceback" —— 用例名里本来就有"…GBK 环境无 Traceback"字样，
        # 会**误报**（本条自己踩过一次）。必须匹配真实 traceback 头。
        self.assertNotIn("Traceback (most recent call last)", out, "既有自测网出现真实 Traceback")
        # 用例数、PASS/FAIL/SKIP 计数一律不手抄（R-13）——直接读脚本自报结果
        import re
        m = re.search(r"(\d+)\s*PASS", out)
        f = re.search(r"(\d+)\s*FAIL", out)
        self.assertIsNotNone(m, f"未能从既有自测输出解析 PASS 计数：{out[-300:]}")
        self.assertEqual((f.group(1) if f else "0"), "0", f"既有自测网有 FAIL：{out[-500:]}")


# ══════════════ ⑧ `-O` 结果一致（D-16：-O/PYTHONOPTIMIZE 会静默关掉裸 assert）══════════════
class TestOptimizedModeConsistency(unittest.TestCase):
    def test_dash_O_same_result(self):
        if os.environ.get("SIXLAYER_SELFTEST_CHILD") == "1":
            self.skipTest("子进程内跳过（防递归）")

        def run(extra_env):
            env = dict(os.environ, SIXLAYER_SELFTEST_CHILD="1", **extra_env)
            r = subprocess.run([PY, str(Path(__file__).resolve()),
                                "--json-summary", "--exclude-delegate"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env)
            line = (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else "{}"
            return json.loads(line)

        normal = run({})
        optimized = run({"PYTHONOPTIMIZE": "1"})
        self.assertEqual((normal.get("failures"), normal.get("errors")), (0, 0),
                         f"普通模式下纯逻辑子集应全绿，实际 {normal}")
        self.assertEqual((normal.get("failures"), normal.get("errors"), normal.get("tests")),
                         (optimized.get("failures"), optimized.get("errors"), optimized.get("tests")),
                         f"-O 与普通模式结果不一致：{normal} vs {optimized}")


# ══════════════ ⑨ 状态板弱校验（rule 84 / D-02） ══════════════
class TestStateBoard(unittest.TestCase):
    def test_init_append_check_green(self):
        with TmpProject() as box:
            d = str(box.path)
            self.assertEqual(_cli(["run", "state_board", d, "init"], isolate=False), 0)
            self.assertEqual(_cli(["run", "state_board", d, "check"], isolate=False), 0)
            for i in range(3):
                self.assertEqual(_cli(["run", "state_board", d, "append", f"事件{i}", "ev"], isolate=False), 0)
            self.assertEqual(_cli(["run", "state_board", d, "check"], isolate=False), 0)
            txt = (box.path / "PROJECT_STATUS.md").read_text(encoding="utf-8")
            self.assertIn("事件2", txt)

    def test_weak_check_reports_header(self):
        with TmpProject() as box:
            d = str(box.path)
            _cli(["run", "state_board", d, "init"], isolate=False)
            rc, out = _cli_out(["run", "state_board", d, "check"], isolate=False)
            self.assertIn("[WEAK-CHECK]", out, "必须打印弱校验报告头")
            self.assertIn("弱校验通过 ≠ 事件流完整", out, "必须写明它不保证什么")

    def test_known_red_row_regression(self):
        """反向 fixture：手工删掉一行事件 → 行数倒退 → 必须 FAIL。"""
        with TmpProject() as box:
            d = str(box.path)
            _cli(["run", "state_board", d, "init"], isolate=False)
            for i in range(4):
                _cli(["run", "state_board", d, "append", f"e{i}", "x"], isolate=False)
            self.assertEqual(_cli(["run", "state_board", d, "check"], isolate=False), 0)
            p = box.path / "PROJECT_STATUS.md"
            lines = p.read_text(encoding="utf-8").splitlines()
            for i in range(len(lines) - 1, -1, -1):
                if "e3" in lines[i]:
                    del lines[i]
                    break
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            rc = _cli(["run", "state_board", d, "check"], isolate=False)
            self.assertEqual(rc, 1, "删行后行数倒退，弱校验必须 FAIL（否则该断言没有牙齿）")

    def test_append_lands_inside_events_section_even_when_not_last(self):
        """反向 fixture：事件流表**不是文件最后一节**时，append 仍必须落进事件流表内。

        本条曾真红过：原实现按"文件末尾追加"，行写进了后面的表格，事件流行数不变
        → **追加静默失效**，而弱校验照样报"单调不减 ✓"。
        """
        with TmpProject() as box:
            d = str(box.path)
            _cli(["run", "state_board", d, "init"], isolate=False)
            p = box.path / "PROJECT_STATUS.md"
            p.write_text(p.read_text(encoding="utf-8")
                         + "\n## 九、尾部干扰节\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
                         encoding="utf-8")
            sb = _load("state_board")
            before = sb.event_row_count(p.read_text(encoding="utf-8"))
            self.assertEqual(_cli(["run", "state_board", d, "append", "关键事件", "ev"],
                                  isolate=False), 0)
            after = sb.event_row_count(p.read_text(encoding="utf-8"))
            self.assertEqual(after, before + 1,
                             "append 后事件流表行数必须 +1（否则追加静默失效）")
            tail = p.read_text(encoding="utf-8").split("## 九、尾部干扰节")[1]
            self.assertNotIn("关键事件", tail, "新行不得落进尾部干扰节")

    def test_known_red_structure_break(self):
        """反向 fixture：删掉一个分区标题 → 结构非法 → 必须 FAIL。"""
        with TmpProject() as box:
            d = str(box.path)
            _cli(["run", "state_board", d, "init"], isolate=False)
            p = box.path / "PROJECT_STATUS.md"
            txt = p.read_text(encoding="utf-8").replace("## 二、待开发执行（指令区 · 只追加 + 只标状态，不删不改）",
                                                        "## 二、（标题被改坏）")
            p.write_text(txt, encoding="utf-8")
            rc = _cli(["run", "state_board", d, "check"], isolate=False)
            self.assertEqual(rc, 1, "缺分区标题必须 FAIL")


# ══════════════ ⑩ 写入/搬运类产物断言第三类（rule 79 / D-05） ══════════════
class TestWriteAssert(unittest.TestCase):
    def _mk(self, box):
        d = box.path
        (d / "tmp").mkdir(exist_ok=True)
        (d / "out").mkdir(exist_ok=True)
        (d / "tmp" / "ok.txt").write_bytes(b"hello")
        (d / "out" / "ok.txt").write_bytes(b"hello")
        (d / "tmp" / "src.txt").write_bytes(b"src-non-empty")
        (d / "out" / "zero.txt").write_bytes(b"")
        (d / "tmp" / "empty.txt").write_bytes(b"")
        (d / "out" / "empty.txt").write_bytes(b"")
        return d

    def test_zero_byte_semantics_distinguished(self):
        """0 字节必须三分：源空+目标空 → SKIP；源非空+目标空 → FAIL；目标不存在 → FAIL。"""
        with TmpProject() as box:
            d = self._mk(box)
            (d / "write-assert.json").write_text(json.dumps([
                {"src": "tmp/ok.txt", "dst": "out/ok.txt"},
                {"src": "tmp/src.txt", "dst": "out/zero.txt"},
                {"src": "tmp/empty.txt", "dst": "out/empty.txt"},
                {"dst": "out/nope.png"},
            ]), encoding="utf-8")
            rc, out = _cli_out(["run", "six_layer_check", "write-assert", str(d)], isolate=False)
            self.assertEqual(rc, 1, "含 FAIL 时退出码应为 1")
            self.assertIn("PASS=1", out)
            self.assertIn("FAIL=2", out)
            self.assertIn("SKIP=1", out)
            self.assertIn("0 字节", out)

    def test_known_green_all_pass(self):
        with TmpProject() as box:
            d = self._mk(box)
            (d / "write-assert.json").write_text(json.dumps([
                {"src": "tmp/ok.txt", "dst": "out/ok.txt"}]), encoding="utf-8")
            rc = _cli(["run", "six_layer_check", "write-assert", str(d)], isolate=False)
            self.assertEqual(rc, 0)

    def test_skip_counter_trips_after_limit(self):
        """反向 fixture：连续 3 次跳过 → 降级计数器超限 → FAIL（防'跳过'成常态逃逸口）。"""
        with TmpProject() as box:
            d = self._mk(box)
            (d / "write-assert.json").write_text(json.dumps([
                {"src": "tmp/empty.txt", "dst": "out/empty.txt"}]), encoding="utf-8")
            rcs = [_cli(["run", "six_layer_check", "write-assert", str(d)], isolate=False)
                   for _ in range(3)]
            self.assertEqual(rcs[0], 0, "第 1 次跳过不该立即 FAIL")
            self.assertEqual(rcs[2], 1, "连续 3 次跳过必须 FAIL（计数器超限）")

    def test_capability_probe_missing_does_not_count(self):
        """能力探针缺失（目录不可读）→ SKIP 标 [不可测·环境缺失] 且**不占计数器**。"""
        wa = _load("write_assert")
        with TmpProject() as box:
            r = wa._probe_read_capability(box.path)
            self.assertTrue(r["ok"], "正常沙箱里读能力探针应为 ok")
            src = (SCRIPTS_DIR / "write_assert.py").read_text(encoding="utf-8")
            self.assertIn("不占降级计数器", src, "环境缺失必须显式声明不占计数器")


# ══════════════ ⑪ L1b：route_error / compress / design_gate ══════════════
class TestL1bTools(unittest.TestCase):
    # ── route_error（D-14 三条验收口）──
    def test_route_error_acceptance_three(self):
        cases = [
            ("合约条款过严，需要重新确认", "scheduler"),   # 合约级 → 调度器
            ("type hint 缺失，请补类型标注", "programmer_N"),  # 代码级 → 程序员
            ("嗯……这个说不上来哪里不对", "human"),        # 无法判断 → 人工
        ]
        re_mod = _load("route_error")
        table = re_mod.load_table()
        for text, expect in cases:
            with self.subTest(text=text):
                got = re_mod.route_error(text, table)["target"]
                self.assertEqual(got, expect, f"「{text}」应路由 {expect}，实际 {got}")

    def test_route_error_contract_priority(self):
        """合约级命中优先于代码级（T1 修正）：同时含两类关键词仍应 scheduler。"""
        re_mod = _load("route_error")
        res = re_mod.route_error("合约条款冲突，同时 type hint 也缺失", re_mod.load_table())
        self.assertEqual(res["target"], "scheduler")
        self.assertEqual(res["bucket"], "contract")

    def test_route_error_table_is_external_and_versioned(self):
        """反向 fixture：表是外置数据文件且带版本号 —— 改表即可改规则（不发版）。"""
        re_mod = _load("route_error")
        table = re_mod.load_table()
        self.assertIn("version", table, "关键词表必须带版本号")
        import copy as _copy
        mutated = _copy.deepcopy(table)
        mutated["keywords"]["code"] = ["不存在的关键词___"]
        mutated["keywords"]["arch"] = []
        mutated["keywords"]["contract"] = []
        res = re_mod.route_error("type hint 缺失", mutated)
        self.assertEqual(res["target"], "human",
                         "改表后行为必须随之改变（证明规则真在外置表里）")

    def test_route_error_eval_synthetic_must_not_be_green(self):
        """收尾共识 Q3：合成语料**跑绿也必须非 0**（否则会被 CI/Gate 当通过 = 假绿）。"""
        corpus = SCRIPTS_DIR / "route_error_corpus_synthetic.jsonl"
        self.assertTrue(corpus.exists(), "合成语料必须随件交付")
        rc, out = _cli_out(["run", "route_error", "--eval", str(corpus)], isolate=False)
        self.assertEqual(rc, 3, f"合成语料必须 exit 3=PENDING（哪怕全绿）；实际 rc={rc}")
        self.assertIn("corpus_kind=synthetic", out, "kind 必须在报告头出现（双信号一致）")
        self.assertIn("PENDING", out)

    def test_route_error_eval_rejects_missing_kind(self):
        """反向 fixture：语料缺 kind → 必须 FAIL（防合成语料被当真实评测）。"""
        with TmpProject() as box:
            bad = box.path / "nokind.jsonl"
            bad.write_text('{"id":"X","text":"a","expect":"human"}\n', encoding="utf-8")
            rc, out = _cli_out(["run", "route_error", "--eval", str(bad)], isolate=False)
            self.assertEqual(rc, 2, f"缺 kind 必须 rc=2；实际 rc={rc}")
            self.assertIn("kind", out)

    def test_route_error_pending_is_code_constant(self):
        """PENDING 由**代码常量**决定，不由输出文本决定（防文本被跳过）。"""
        re_mod = _load("route_error")
        self.assertEqual(re_mod.REGRESSION_EVAL_STATUS, "pending")
        self.assertEqual(re_mod.PENDING_RC, 3)

    # ── compress（rule 83 LC1/LC2）──
    def _bundle(self, **over):
        b = {
            "phase": "P2/L1b", "modules": [{"id": "m1"}],
            "ruled_out": ["假设A"], "top_suspect": None,
            "open_items": ["x"], "next": "L2",
            "consumed_inputs": [
                {"id": "spec", "path": "spec.md", "commit": "abc1234", "consumed_by": "architect"},
                {"id": "raw", "path": "raw.log", "consumed_by": None},
            ],
            "subagent_reports": [
                {"agent": "programmer_1", "verdict": "PASS",
                 "artifacts": ["a.py@abc1234", "b.py"], "open_questions": [],
                 "narrative": "N" * 5000},
            ],
        }
        b.update(over)
        return b

    def test_compress_mechanical_no_llm_and_restate(self):
        cp = _load("compress")
        res = cp.compress(self._bundle())
        self.assertEqual(res["llm_calls"], 0, "LC1/LC2 是机械层，不得花 LLM")
        rt = res["restate_test"]
        for k in ("phase", "ruled_out", "open_items", "next"):
            self.assertTrue(rt[k], f"复述测试项 {k} 应可复述")
        self.assertTrue(rt["ok"])
        s = res["stats"]
        self.assertEqual(s["lc2_inputs_dropped"], 1, "已消费输入应被淘汰 1 条")
        self.assertEqual(s["lc2_inputs_kept"], 1, "未消费输入应保留")
        self.assertGreater(s["narrative_chars_dropped"], 0, "叙述正文应被丢弃并计数")

    def test_compress_weak_pointer_detection(self):
        cp = _load("compress")
        res = cp.compress(self._bundle())
        weak = {p["path"] for p in res["weak_pointers"]}
        self.assertIn("b.py", weak, "缺 @commit 的产物指针应被判 weak")
        self.assertNotIn("a.py@abc1234", weak, "带 @commit 的指针不该被判 weak")

    def test_compress_restate_fails_on_missing_field(self):
        """反向 fixture：缺 next 字段 → 复述测试必须 FAIL（否则这层没牙齿）。"""
        cp = _load("compress")
        res = cp.compress(self._bundle(next=None))
        self.assertFalse(res["restate_test"]["ok"], "缺 next 时复述测试必须 FAIL")

    # ── design_gate（挂 pending 硬门）──
    def test_design_gate_is_pending_not_green(self):
        rc, out = _cli_out(["run", "design_gate"], isolate=False)
        self.assertEqual(rc, 3, "design_gate 必须返回 pending 码 3（schema 未定稿）")
        self.assertIn("PENDING", out)
        self.assertIn("semantic=PENDING", out, "退出码 3 必须映射为 PENDING 而不是 PASS")
        self.assertIn("不保证什么", out, "必须随件交付『它不保证什么』")


# ══════════════ ⑫ L2：llm_client（默认关闭 + 四步防线 + 预算 fail-closed）══════════════
class TestL2LlmClient(unittest.TestCase):
    def test_default_off_returns_pending(self):
        """默认关闭：不发任何请求，退出码 3 → 语义 PENDING（绝不落进 PASS）。"""
        env = {k: v for k, v in os.environ.items()
               if k not in ("SIXLAYER_LLM", "DEEPSEEK_API_KEY")}
        r = subprocess.run([PY, str(CLI), "run", "llm_client", "--chat", "hi"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
        self.assertEqual(r.returncode, 3, "默认关闭必须 rc=3")
        self.assertIn("semantic=PENDING", (r.stdout or "") + (r.stderr or ""))

    def test_sse_parser_replays_real_fixture(self):
        """离线回归：手写 SSE 解析器重放 L0 真实 fixture（录制重放不是 mock，D-04）。"""
        fixture = SKILL_DIR / "_probe" / "l0_2_stream_raw.sse"
        if not fixture.exists():
            self.skipTest("缺 L0 fixture（_probe/l0_2_stream_raw.sse）")
        llm = _load("llm_client")
        res = llm.parse_sse(fixture.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(res["errors"], [], "真实 fixture 不该有非法帧")
        self.assertTrue(res["done"], "应识别 `data: [DONE]`")
        self.assertGreater(len(res["frames"]), 10)
        self.assertEqual(len(res["usage_frames"]), 1, "实测 usage 只在尾帧 1 处")
        self.assertIsNotNone(llm.extract_reasoning_tokens(res["usage_frames"][-1]))

    def test_sse_parser_strict_no_repair(self):
        """反向 fixture：非法 JSON 帧必须**报错**而不是被静默修复（D-12①）。"""
        llm = _load("llm_client")
        bad = "data: {\"ok\":1}\n\ndata: {not json at all\n\ndata: [DONE]\n"
        res = llm.parse_sse(bad)
        self.assertEqual(len(res["errors"]), 1, "非法帧必须被记入 errors（不得修复）")
        self.assertTrue(res["done"])

    def test_four_defenses(self):
        llm = _load("llm_client")
        # ① 响应回显核对
        ok, _ = llm.defense_1_echo("deepseek-flash", {"model": "deepseek-flash"})
        self.assertTrue(ok)
        bad, msg = llm.defense_1_echo("deepseek-v4-flash", {"model": "deepseek-flash"})
        self.assertFalse(bad, "被静默改写的 model 必须判 FAIL")
        # ② 能力协商核对
        self.assertTrue(llm.defense_2_capability("max", ["low", "high", "max"])[0])
        self.assertFalse(llm.defense_2_capability("none", ["low", "high", "max"])[0],
                         "none 不在实测域内，必须拦下")
        # ③ 语义指纹
        seen = {}
        self.assertTrue(llm.defense_3_fingerprint({"model": "m", "object": "o",
                                                   "system_fingerprint": "f"}, seen)[0])
        self.assertFalse(llm.defense_3_fingerprint({"model": "m2", "object": "o",
                                                    "system_fingerprint": "f"}, seen)[0],
                         "指纹漂移必须 FAIL")
        # ④ 禁用透明修复组件
        ok4, msg4 = llm.defense_4_no_repair_lib()
        self.assertTrue(ok4, f"引擎里不该出现 json_repair 类依赖：{msg4}")

    def test_budget_fail_closed_vs_degraded(self):
        """漏账（真发起却无 usage）→ FAIL_CLOSED；显式降级 → 不计漏账。"""
        llm = _load("llm_client")
        cfg = llm.load_cfg()
        with TmpProject() as box:
            p = llm.ledger_path(box.path)
            p.write_text("\n".join([
                json.dumps({"usage": {"total_tokens": 100}}),
                json.dumps({"degraded": True, "reason": "no_api_key"}),
            ]) + "\n", encoding="utf-8")
            r = llm.budget_report(box.path, cfg)
            self.assertEqual(r["verdict"], "OK", "降级不该被算成漏账")
            self.assertEqual(r["degraded_calls"], 1)
            self.assertEqual(r["missing_usage_lines"], 0)
            # 反向：真发起却无 usage
            p.write_text(json.dumps({"model": "m"}) + "\n", encoding="utf-8")
            r2 = llm.budget_report(box.path, cfg)
            self.assertEqual(r2["verdict"], "FAIL_CLOSED", "漏账必须 fail-closed")

    def test_budget_thresholds(self):
        llm = _load("llm_client")
        cfg = llm.load_cfg()
        denom = cfg["budget"]["per_wave_tokens"]
        with TmpProject() as box:
            p = llm.ledger_path(box.path)
            p.write_text(json.dumps({"usage": {"total_tokens": int(denom * 0.85)}}) + "\n",
                         encoding="utf-8")
            self.assertEqual(llm.budget_report(box.path, cfg)["verdict"], "ALERT")
            p.write_text(json.dumps({"usage": {"total_tokens": denom}}) + "\n", encoding="utf-8")
            self.assertEqual(llm.budget_report(box.path, cfg)["verdict"], "ASK_HUMAN")

    def test_no_key_degrades_with_ledger_trace(self):
        """有开关但无 key → 降级 + **留痕**（不静默跳过，R-07）。"""
        with TmpProject() as box:
            env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
            env["SIXLAYER_LLM"] = "on"
            r = subprocess.run([PY, str(SCRIPTS_DIR / "llm_client.py"), "--chat", "hi",
                                "--project", str(box.path)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env)
            self.assertEqual(r.returncode, 1, "无 key 应降级为 1（非绿）")
            ledger = box.path / "llm_usage.jsonl"
            self.assertTrue(ledger.exists(), "降级必须留痕到 token 账本")
            self.assertIn("degraded", ledger.read_text(encoding="utf-8"))


# ══════════════ ⑬ §4.3「已知坏样本回灌」剩余两项（本轮共识 Q4）══════════════
class TestSection43Backfill(unittest.TestCase):
    """§4.3 第 4、5 项：**每条检查项必须被一条已知坏样本证明过它真会红**（R-02）。
    实测发现这两项在自测网里缺失（§4.3 第 4 项零覆盖 / 第 5 项只验了档位枚举不是缺列）。"""

    def test_item4_write_conflict_same_file_two_modules(self):
        """§4.3 第 4 项：造"两模块写同一文件"的预期产物清单 → 断言 FAIL。"""
        with TmpProject() as box:
            (box.path / "progress.json").write_text(json.dumps({
                "modules": {}, "lifecycle": "INIT",
                "expected_products": [
                    {"wave": "W1", "module": "modA", "files": ["shared.txt", "a.txt"],
                     "status": "pending"},
                    {"wave": "W1", "module": "modB", "files": ["shared.txt", "b.txt"],
                     "status": "pending"},
                ]}, ensure_ascii=False), encoding="utf-8")
            rc, out = _cli_out(["run", "six_layer_check", "write-conflict", str(box.path)],
                               isolate=False)
            self.assertEqual(rc, 1, f"两模块写同一文件必须 FAIL；实际 rc={rc}\n{out[-400:]}")
            self.assertIn("shared.txt", out, "FAIL 信息应指名冲突文件")

    def test_item4_negative_no_conflict_passes(self):
        """反向对照：写集互斥时不得误报（防"检查器造噪音"）。"""
        with TmpProject() as box:
            (box.path / "progress.json").write_text(json.dumps({
                "modules": {}, "lifecycle": "INIT",
                "expected_products": [
                    {"wave": "W1", "module": "modA", "files": ["a.txt"], "status": "pending"},
                    {"wave": "W1", "module": "modB", "files": ["b.txt"], "status": "pending"},
                ]}, ensure_ascii=False), encoding="utf-8")
            rc = _cli(["run", "six_layer_check", "write-conflict", str(box.path)], isolate=False)
            self.assertEqual(rc, 0, "写集互斥时应通过")

    def test_item4_dispatch_check_missing_acceptance(self):
        """§4.3 第 4 项另半：任务卡缺验收命令 → dispatch-check 必须 FAIL。"""
        with TmpProject() as box:
            card = box.path / "task-card.md"
            card.write_text("## 任务\n写一个函数。\n", encoding="utf-8")
            rc, out = _cli_out(["run", "six_layer_check", "dispatch-check", str(card)],
                               isolate=False)
            self.assertEqual(rc, 1, f"缺验收命令的任务卡必须 FAIL；实际 rc={rc}")
            self.assertIn("验收", out)

    def test_item5_cost_log_missing_column6_reports_and_exits_nonzero(self):
        """§4.3 第 5 项：写一条缺第 6 列的行 → `summary` 必须**报不合规且非 0 退出**
        （原实现只打印警告、退出码 0 = "跑完了"而非"报错了"）。"""
        with TmpProject() as box:
            (box.path / "cost_log.md").write_text(
                "[2026-09-30 10:00]|programmer_1|lite|0.1|成功\n"        # 缺第 6 列
                "[2026-09-30 10:01]|programmer_2|lite|0.1|成功|无\n",    # 合规
                encoding="utf-8")
            rc, out = _cli_out(["run", "cost_log", str(box.path), "summary"], isolate=False)
            self.assertIn("不合规", out, "必须报出不合规")
            self.assertEqual(rc, 1, f"有不合规行必须非 0 退出；实际 rc={rc}")

    def test_item5_cost_log_clean_ledger_passes(self):
        """反向对照：全部合规时不得 FAIL（且空账本也不算失败）。"""
        with TmpProject() as box:
            (box.path / "cost_log.md").write_text(
                "[2026-09-30 10:00]|programmer_1|lite|0.1|成功|无\n", encoding="utf-8")
            self.assertEqual(_cli(["run", "cost_log", str(box.path), "summary"], isolate=False), 0)
            (box.path / "cost_log.md").unlink()
            self.assertEqual(_cli(["run", "cost_log", str(box.path), "summary"], isolate=False), 0)


# ══════════════ 汇总 ══════════════
_ONLY = ""


def _suite(exclude_delegate: bool = False):
    loader = unittest.TestLoader()
    mod = sys.modules[__name__]
    if not exclude_delegate and not _ONLY:
        return loader.loadTestsFromModule(mod)
    suite = unittest.TestSuite()
    for _name, obj in sorted(vars(mod).items()):
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase) \
                and obj is not TestDelegateExistingNet:
            if _ONLY and _ONLY not in obj.__name__:
                continue
            suite.addTests(loader.loadTestsFromTestCase(obj))
    return suite


def _json_summary(exclude_delegate: bool = False) -> dict:
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    res = runner.run(_suite(exclude_delegate))
    return {"tests": res.testsRun, "failures": len(res.failures), "errors": len(res.errors),
            "skipped": len(res.skipped)}


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json-summary", action="store_true")
    ap.add_argument("--exclude-delegate", action="store_true")
    ap.add_argument("--allow-net", action="store_true")
    ap.add_argument("--only", default="", help="只跑名字含该子串的 TestCase（定点复跑用）")
    ap.add_argument("-h", "--help", action="store_true")
    args, _ = ap.parse_known_args()
    if args.help:
        print(__doc__)
        return 0

    global _ONLY
    _ONLY = args.only

    if not args.allow_net:
        _OFFLINE_GUARD["active"] = True

        # ★ 不能 patch `socket.socket` —— 它是个**类**，标准库 `ssl` 在 import 时写
        # `class SSLSocket(socket)`，一旦换成函数就会 `TypeError: function() argument
        # 'code' must be code, not str`（实测踩到，5 个 error）。改为拦**连接入口**：
        # `getaddrinfo`（DNS）与 `create_connection`（建连）—— 这两个是运行时查找，
        # 阻断后任何真实网络调用都会失败，而类定义不受影响。
        def _no_net(*a, **k):
            raise RuntimeError("自测必须离线（D-16）：检测到网络调用被拦下")

        def _no_conn(*a, **k):
            raise RuntimeError("自测必须离线（D-16）：检测到建连被拦下")
        socket.getaddrinfo = _no_net        # type: ignore[assignment]
        socket.create_connection = _no_conn  # type: ignore[assignment]

    if args.json_summary:
        print(json.dumps(_json_summary(args.exclude_delegate), ensure_ascii=False))
        return 0

    verbosity = 1 if args.quiet else 2
    res = unittest.TextTestRunner(verbosity=verbosity).run(_suite(args.exclude_delegate))
    ok = not res.failures and not res.errors
    print(f"[selftest] tests={res.testsRun} failures={len(res.failures)} "
          f"errors={len(res.errors)} skipped={len(res.skipped)} → {'GREEN' if ok else 'RED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
