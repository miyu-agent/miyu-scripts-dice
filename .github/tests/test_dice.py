# dice.py 的测试（审计 2026-11-18）。
#
# 跑法（在仓库根）：
#   python3 -I -B -m unittest discover -s .github/tests
# （不加 -t .：.github 不是合法的包名，加了 unittest 会报 Start directory is not importable。）
#
# 只用标准库；不联网（脚本本来就不联网）。HOME、XDG_*、MIYU_* 都指到临时目录。
# 放在 .github/tests/ 而不是 tests/：打包会跳过 .github，测试不会进包。

import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "dice.py"


def load():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("dice_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Sandbox(unittest.TestCase):
    """每条测试一个临时目录，环境里去掉所有 MIYU_*、XDG_*。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("MIYU_", "XDG_"))}
        env.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "cfg"),
                   XDG_CACHE_HOME=str(root / "xdg-cache"), XDG_STATE_HOME=str(root / "xdg-state"),
                   XDG_DATA_HOME=str(root / "xdg-data"))
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = root
        self.mod = load()

    def call(self, args):
        """照 main() 跑一次：stdin 喂 JSON，返回 (退出码, 输出)。"""
        out = io.StringIO()
        code = 0
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(args))), redirect_stdout(out):
            try:
                self.mod.main()
            except SystemExit as exc:
                code = exc.code or 0
        return code, out.getvalue()

    def run_script(self, stdin_text):
        """另起进程跑脚本，返回 (退出码, stdout+stderr)，用来看有没有 traceback。"""
        proc = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT)], input=stdin_text,
                              capture_output=True, text=True, timeout=10, env=dict(os.environ))
        return proc.returncode, proc.stdout + proc.stderr


class TopLevelType(Sandbox):
    # 审计 #176：main() 只接 JSONDecodeError，不查顶层是不是对象；
    # 喂 [] 或 null 直接 args.get → AttributeError，打 traceback。应像 calculator 那样友好报错、退出码 1。
    def test_non_object_args_friendly_error(self):
        for raw in ("[]", "null"):
            with self.subTest(stdin=raw):
                code, out = self.run_script(raw)
                self.assertEqual(code, 1, out)
                self.assertIn("参数要是一个 JSON 对象", out)
                self.assertNotIn("Traceback", out)


class Repeat(Sandbox):
    # 审计 #176：`args.get("repeat") or 1` 把 0 吞成 1，repeat=0 照样掷一次；应和 -1 一样报范围错。
    def test_repeat_zero_is_rejected(self):
        code, out = self.call({"dice": "1d6", "repeat": 0})
        self.assertEqual(code, 1, out)
        self.assertIn("repeat 要是 1 到 20 的整数", out)
        self.assertNotIn("→", out, "repeat=0 不该掷骰子")

    # 防改坏（现在就绿）：不写 repeat 默认掷一次；repeat=-1 报范围错。
    def test_repeat_default_and_negative(self):
        code, out = self.call({"dice": "1d6"})
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("→"), 1, out)
        code, out = self.call({"dice": "1d6", "repeat": -1})
        self.assertEqual(code, 1, out)
        self.assertIn("repeat 要是 1 到 20 的整数", out)


if __name__ == "__main__":
    unittest.main()
