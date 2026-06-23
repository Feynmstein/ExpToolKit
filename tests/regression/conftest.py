"""回归测试 pytest 配置。

提供 skip_if_no_data fixture：当真实数据未同步时自动跳过测试。
"""

from __future__ import annotations

from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


def _has_data(exp_id: str) -> bool:
    """检查指定实验编号的数据目录是否存在且包含 CSV 文件。"""
    exp_dir = DATA_DIR / exp_id
    if not exp_dir.is_dir():
        return False
    return any(exp_dir.glob("*.csv"))


def require_data(exp_id: str) -> Path:
    """返回实验数据目录，若不存在则自动 skip。

    Usage:
        exp_dir = require_data("00747")
        csv_path = next(exp_dir.glob("*.csv"))
    """
    exp_dir = DATA_DIR / exp_id
    if not _has_data(exp_id):
        pytest.skip(
            f"真实数据 {exp_id} 未同步到 tests/regression/data/。"
            f"从实验电脑同步数据后重试。"
        )
    return exp_dir


@pytest.fixture
def data_dir() -> Path:
    """回归测试数据根目录。"""
    return DATA_DIR
