"""读取保真度计算 — 从 IQ 分类中心计算 assignment fidelity。

2 态：等方差 2D Gaussian 重叠积分。
3 态：pairwise 分类错误率的加权平均。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.special import erfc

from exp_toolkit.io.readers import IQBlobs

__all__ = ["ReadoutFidelity", "assignment_fidelity"]


@dataclass
class ReadoutFidelity:
    """读取保真度计算结果。

    Attributes
    ----------
    fidelity_01 : float
        |0⟩→|0⟩ 保真度 (F0)。
    fidelity_10 : float
        |1⟩→|1⟩ 保真度 (F1)。
    avg_fidelity : float
        平均读取保真度 (F0 + F1) / 2。
    snr : float
        信噪比 |c₁ - c₀| / √variance。
    """

    fidelity_01: float
    fidelity_10: float
    avg_fidelity: float
    snr: float


def assignment_fidelity(
    iq_blobs: IQBlobs,
) -> ReadoutFidelity:
    """从 IQ 分类中心计算读取保真度。

    Parameters
    ----------
    iq_blobs : IQBlobs
        IQ 分类数据，含 centers（复数列表）、variance、n_states。

    Returns
    -------
    ReadoutFidelity

    Algorithm
    ---------
    2 态（等方差 2D Gaussian 重叠积分）：
        d = |c₁ - c₀|, σ = √variance
        SNR = d / σ
        P(error) = ½·erfc(d / (2σ√2))
        fidelity = 1 - P(error)

    3 态：计算 pairwise 分类错误率，平均后得 avg_fidelity。
        同时返回 |0⟩↔|1⟩ 间的 pairwise fidelity。

    Raises
    ------
    ValueError
        若 n_states 不是 2 或 3，或 centers 数量不匹配，
        或 variance <= 0。
    """
    n_states = iq_blobs.n_states
    centers = iq_blobs.centers
    variance = iq_blobs.variance

    if n_states not in (2, 3):
        raise ValueError(
            f"n_states must be 2 or 3, got {n_states}"
        )
    if len(centers) != n_states:
        raise ValueError(
            f"Expected {n_states} centers, got {len(centers)}"
        )
    if variance <= 0:
        raise ValueError(
            f"variance must be positive, got {variance}"
        )

    sigma: float = float(variance) ** 0.5

    if n_states == 2:
        c0 = complex(centers[0])
        c1 = complex(centers[1])
        d = abs(c1 - c0)
        snr = d / sigma

        # P(error) = 0.5 * erfc(d / (2 * sigma * sqrt(2)))
        p_error = 0.5 * float(erfc(d / (2.0 * sigma * math.sqrt(2))))

        fidelity = 1.0 - p_error
        return ReadoutFidelity(
            fidelity_01=fidelity,
            fidelity_10=fidelity,
            avg_fidelity=fidelity,
            snr=snr,
        )

    # 3-state: pairwise fidelities
    pairwise_fidelities: list[float] = []
    pairwise_snrs: list[float] = []

    for i in range(n_states):
        for j in range(i + 1, n_states):
            ci = complex(centers[i])
            cj = complex(centers[j])
            d = abs(cj - ci)
            snr_ij = d / sigma
            p_error = 0.5 * float(erfc(d / (2.0 * sigma * math.sqrt(2))))
            pairwise_fidelities.append(1.0 - p_error)
            pairwise_snrs.append(snr_ij)

    # avg_fidelity: mean of pairwise fidelities
    avg_fidelity = sum(pairwise_fidelities) / len(pairwise_fidelities)

    # fidelity_01 / fidelity_10: best pairwise approximation for |0⟩↔|1⟩
    f_01 = pairwise_fidelities[0]  # pair (0,1) is first
    f_10 = f_01

    # SNR: minimum pairwise (worst-case discrimination)
    snr = min(pairwise_snrs)

    return ReadoutFidelity(
        fidelity_01=f_01,
        fidelity_10=f_10,
        avg_fidelity=avg_fidelity,
        snr=snr,
    )
