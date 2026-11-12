"""Exercise the production commit body with real Foundation/ARC, without Metal."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]


@unittest.skipUnless(sys.platform == "darwin", "requires macOS Foundation and ARC")
class LifetimeTests(unittest.TestCase):
    def test_commit_lifetimes(self):
        source = (ROOT / "dm/gfx/nvn/nvn_mtl.m").read_text()
        start = source.index("static void res_commit(void)")
        end = source.index("// What the residency set holds", start)
        harness = (ROOT / "dm/gfx/tests/t_mem_guard_lifetime.inc").read_text()
        body = source[start:end]
        unlock = "    pthread_mutex_unlock(&g_res_mu);"
        self.assertEqual(body.count(unlock), 1)
        variants = {"production": body}
        # Deterministically remove each lifetime guarantee independently. This
        # must fail even at O0, regardless of ARC's optional early releases.
        for snapshot in ("committed", "pending"):
            variants[snapshot] = body.replace(unlock, f"    {snapshot} = nil;\n" + unlock)
        with tempfile.TemporaryDirectory() as work:
            path = pathlib.Path(work)
            for name, variant in variants.items():
                (path / "test.m").write_text(harness.replace("/* COMMIT_BODY */", variant))
                for optimization in ("-O0", "-O2"):
                    with self.subTest(variant=name, optimization=optimization):
                        subprocess.run([
                            "clang", optimization, "-Wall", "-Wextra", "-Werror", "-fobjc-arc",
                            "-I", str(ROOT / "dm/gfx/nvn"), str(path / "test.m"),
                            "-framework", "Foundation", "-o", str(path / "test"),
                        ], check=True)
                        result = subprocess.run(
                            [str(path / "test")], capture_output=True, timeout=20)
                        if name == "production":
                            self.assertEqual(result.returncode, 0, result.stderr.decode())
                        else:
                            self.assertNotEqual(result.returncode, 0)
                            # An allocation may deallocate immediately when its
                            # sole snapshot is cleared, before the unlock probe.
                            self.assertTrue(
                                f"{name}_snapshot != nil" in result.stderr.decode()
                                or "pthread_mutex_trylock(&g_res_mu) == 0"
                                in result.stderr.decode(), result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
