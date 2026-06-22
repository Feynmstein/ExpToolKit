"""IO 子包 — 实验数据的统一读写接口。

提供实验三元组（CSV + INI + JSON）的读取和结构化：

- :func:`load_experiment` — 主入口，加载完整实验数据
- :func:`parse_ini_metadata` — 解析 INI 配置文件
- :func:`load_parameters` — 解析 JSON 参数快照
- :func:`load_csv_with_meta` — 读取 CSV 并附列元数据
"""

from exp_toolkit.io.readers import (
    ColumnMeta,
    Experiment,
    IniMeta,
    IQBlobs,
    ParamsSnapshot,
    QubitParams,
    load_csv_with_meta,
    load_experiment,
    load_parameters,
    parse_ini_metadata,
)

__all__ = [
    "ColumnMeta",
    "Experiment",
    "IniMeta",
    "IQBlobs",
    "ParamsSnapshot",
    "QubitParams",
    "load_csv_with_meta",
    "load_experiment",
    "load_parameters",
    "parse_ini_metadata",
]
