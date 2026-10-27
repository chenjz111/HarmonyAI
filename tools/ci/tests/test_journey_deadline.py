"""A stalled pipe reader must not defeat the integration time budget."""
from pathlib import Path
import subprocess
import sys
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_journey


class JourneyDeadlineTests(unittest.TestCase):
    def test_stalled_reader_is_killed_while_parent_is_writing(self):
        deadline=getattr(run_journey,'child_deadline',None)
        self.assertTrue(callable(deadline),'independent child watchdog required')
        child=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(30)'],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        started=time.monotonic()
        try:
            with deadline([child],0.3) as expired:
                with self.assertRaises((BrokenPipeError,OSError)):
                    child.stdin.write(b'x'*(8*1024*1024));child.stdin.flush()
                self.assertTrue(expired.is_set())
            self.assertNotEqual(child.wait(timeout=3),0)
            self.assertLess(time.monotonic()-started,5)
        finally:
            if child.poll() is None:child.kill()
            child.wait(timeout=3)
            child.stdin.close()


if __name__=='__main__':unittest.main()
