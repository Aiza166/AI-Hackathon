import os, sys
REAL = r"C:\Users\aizag\Desktop\ai hackathon\team-repo\backend\tests\conftest.py"
sys.path.insert(0, os.path.dirname(os.path.dirname(REAL)))
_me = __file__
src = open(REAL, encoding="utf-8").read().replace("os.path.dirname(__file__)", repr(os.path.dirname(REAL)))
exec(compile(src, REAL, "exec"), globals())
