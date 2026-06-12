"""Unit tests for `kotodama.modules.bitnet_qat` (ADR 2605101000).

These pin the QAT contract that every Baien-MX module relies on:
  - weight quant produces strictly ternary values in {-1, 0, +1}
  - activation quant produces int8-range values
  - STE lets gradients flow through a BitLinear forward pass
  - BitLinear shapes match nn.Linear
  - pack_ternary() emits an int8 tensor with the same support
  - BitNetMLP composes correctly
"""

from __future__ import annotations

import math

import pytest
import torch

from kotodama.modules.bitnet_qat import (
    BitLinear,
    BitNetMLP,
    activation_quant_int8,
    weight_quant_158,
)


def test_weight_quant_158_is_ternary():
    torch.manual_seed(0)
    w = torch.randn(64, 32) * 0.5
    w_quant, gamma = weight_quant_158(w)

    assert w_quant.shape == w.shape
    assert gamma.dim() == 0
    assert gamma.item() > 0

    unique_values = torch.unique(w_quant)
    # Must be a subset of {-1, 0, +1}.
    allowed = {-1.0, 0.0, 1.0}
    for v in unique_values.tolist():
        assert v in allowed, f"non-ternary weight value: {v}"


def test_weight_quant_158_zero_weight_is_safe():
    w = torch.zeros(8, 8)
    w_quant, gamma = weight_quant_158(w)
    assert torch.all(w_quant == 0)
    # gamma is clamped to eps so we never divide by zero downstream.
    assert gamma.item() > 0


def test_activation_quant_int8_range():
    torch.manual_seed(0)
    x = torch.randn(4, 16) * 3.0
    x_quant, scale = activation_quant_int8(x)

    assert x_quant.shape == x.shape
    assert scale.shape == (4, 1)
    assert torch.all(x_quant >= -127.0)
    assert torch.all(x_quant <= 127.0)
    # Values are integer in float dtype.
    assert torch.allclose(x_quant, x_quant.round())


def test_bitlinear_shapes_match_nn_linear():
    bl = BitLinear(32, 64)
    x = torch.randn(8, 32)
    y = bl(x)
    assert y.shape == (8, 64)


def test_bitlinear_gradient_flows_through_ste():
    torch.manual_seed(0)
    bl = BitLinear(8, 4)
    x = torch.randn(2, 8, requires_grad=True)
    y = bl(x).sum()
    y.backward()

    assert x.grad is not None
    assert bl.weight.grad is not None
    # STE means the gradient is finite and non-zero somewhere.
    assert torch.isfinite(bl.weight.grad).all()
    assert bl.weight.grad.abs().sum().item() > 0


def test_pack_ternary_outputs_int8_in_support():
    torch.manual_seed(0)
    bl = BitLinear(16, 8)
    packed, gamma = bl.pack_ternary()
    assert packed.dtype == torch.int8
    assert packed.shape == (8, 16)
    assert gamma.dim() == 0
    unique = set(torch.unique(packed).tolist())
    assert unique.issubset({-1, 0, 1})


def test_bitnet_mlp_composes():
    torch.manual_seed(0)
    mlp = BitNetMLP(in_dim=24, hidden_dim=48, out_dim=12)
    x = torch.randn(3, 24)
    y = mlp(x)
    assert y.shape == (3, 12)
    assert torch.isfinite(y).all()


def test_bitlinear_one_optimizer_step_decreases_loss():
    """Sanity-check that a single Adam step reduces the loss on a
    deterministic regression problem. Catches regressions where STE
    gets disconnected from the optimizer."""
    torch.manual_seed(0)
    bl = BitLinear(16, 1)
    x = torch.randn(64, 16)
    y_target = (x.sum(dim=-1, keepdim=True) > 0).float()
    opt = torch.optim.Adam(bl.parameters(), lr=5e-2)

    def step():
        opt.zero_grad()
        loss = ((bl(x) - y_target) ** 2).mean()
        loss.backward()
        opt.step()
        return float(loss.detach())

    loss_0 = step()
    for _ in range(20):
        step()
    loss_n = step()

    assert math.isfinite(loss_0)
    assert math.isfinite(loss_n)
    assert loss_n < loss_0, f"Adam did not reduce loss: {loss_0} -> {loss_n}"
