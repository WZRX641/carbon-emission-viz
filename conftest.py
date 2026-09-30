"""pytest 根配置：把项目根目录加入 sys.path，使 `src`、`tests` 可导入。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
