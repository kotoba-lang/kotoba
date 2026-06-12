"""Pure tests for wellbecoming Pydantic v2 ZeebeJobInput migration (ADR-2605080200)."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# _TrustWeightInput
# ---------------------------------------------------------------------------

class TestTrustWeightInput:
    def test_defaults(self):
        from kotodama.primitives.wellbecoming_trust import (
            _TrustWeightInput, _BC_EPSILON, _WEIGHT_K, _MIN_SCORED_EVENTS,
        )
        inp = _TrustWeightInput()
        assert inp.bc_epsilon == _BC_EPSILON
        assert inp.weight_k == _WEIGHT_K
        assert inp.min_scored_events == _MIN_SCORED_EVENTS

    def test_from_job_uses_variables(self):
        from kotodama.primitives.wellbecoming_trust import _TrustWeightInput
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = {"bc_epsilon": 0.5, "weight_k": 3.0, "min_scored_events": 5}
        inp = _TrustWeightInput.from_job(job)
        assert inp.bc_epsilon == 0.5
        assert inp.weight_k == 3.0
        assert inp.min_scored_events == 5

    def test_from_job_none_variables_uses_defaults(self):
        from kotodama.primitives.wellbecoming_trust import (
            _TrustWeightInput, _BC_EPSILON, _WEIGHT_K, _MIN_SCORED_EVENTS,
        )
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = None
        inp = _TrustWeightInput.from_job(job)
        assert inp.bc_epsilon == _BC_EPSILON
        assert inp.weight_k == _WEIGHT_K
        assert inp.min_scored_events == _MIN_SCORED_EVENTS

    def test_register_function_exists(self):
        from kotodama.primitives.wellbecoming_trust import register
        import inspect
        assert inspect.isfunction(register)


# ---------------------------------------------------------------------------
# _NoiseInput
# ---------------------------------------------------------------------------

class TestNoiseInput:
    def test_defaults(self):
        from kotodama.primitives.wellbecoming_noise import (
            _NoiseInput, _SIGMA, _OU_THETA, _DT_SEC, _MIN_SCORED_EVENTS,
        )
        inp = _NoiseInput()
        assert inp.sigma == _SIGMA
        assert inp.ou_theta == _OU_THETA
        assert inp.dt_sec == _DT_SEC
        assert inp.min_scored_events == _MIN_SCORED_EVENTS

    def test_from_job_uses_variables(self):
        from kotodama.primitives.wellbecoming_noise import _NoiseInput
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = {"sigma": 0.05, "ou_theta": 0.2, "dt_sec": 1800.0, "min_scored_events": 10}
        inp = _NoiseInput.from_job(job)
        assert inp.sigma == 0.05
        assert inp.ou_theta == 0.2
        assert inp.dt_sec == 1800.0
        assert inp.min_scored_events == 10

    def test_from_job_partial_override(self):
        from kotodama.primitives.wellbecoming_noise import _NoiseInput, _SIGMA, _OU_THETA
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = {"dt_sec": 7200.0}
        inp = _NoiseInput.from_job(job)
        assert inp.sigma == _SIGMA
        assert inp.ou_theta == _OU_THETA
        assert inp.dt_sec == 7200.0

    def test_register_function_exists(self):
        from kotodama.primitives.wellbecoming_noise import register
        import inspect
        assert inspect.isfunction(register)


# ---------------------------------------------------------------------------
# _RestoringInput
# ---------------------------------------------------------------------------

class TestRestoringInput:
    def test_defaults(self):
        from kotodama.primitives.wellbecoming_restoring import (
            _RestoringInput, _GAMMA_LR, _MIN_SCORED_EVENTS,
        )
        inp = _RestoringInput()
        assert inp.gamma_lr == _GAMMA_LR
        assert inp.min_scored_events == _MIN_SCORED_EVENTS

    def test_from_job_uses_variables(self):
        from kotodama.primitives.wellbecoming_restoring import _RestoringInput
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = {"gamma_lr": 0.1, "min_scored_events": 7}
        inp = _RestoringInput.from_job(job)
        assert inp.gamma_lr == 0.1
        assert inp.min_scored_events == 7

    def test_from_job_empty_variables(self):
        from kotodama.primitives.wellbecoming_restoring import (
            _RestoringInput, _GAMMA_LR, _MIN_SCORED_EVENTS,
        )
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = {}
        inp = _RestoringInput.from_job(job)
        assert inp.gamma_lr == _GAMMA_LR
        assert inp.min_scored_events == _MIN_SCORED_EVENTS

    def test_register_function_exists(self):
        from kotodama.primitives.wellbecoming_restoring import register
        import inspect
        assert inspect.isfunction(register)


# ---------------------------------------------------------------------------
# _InfluenceInput
# ---------------------------------------------------------------------------

class TestInfluenceInput:
    def test_defaults(self):
        from kotodama.primitives.wellbecoming_influence import (
            _InfluenceInput, _LAMBDA_LR, _MIN_SCORED_EVENTS,
        )
        inp = _InfluenceInput()
        assert inp.lambda_lr == _LAMBDA_LR
        assert inp.min_scored_events == _MIN_SCORED_EVENTS

    def test_from_job_uses_variables(self):
        from kotodama.primitives.wellbecoming_influence import _InfluenceInput
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = {"lambda_lr": 0.2, "min_scored_events": 4}
        inp = _InfluenceInput.from_job(job)
        assert inp.lambda_lr == 0.2
        assert inp.min_scored_events == 4

    def test_from_job_none_variables(self):
        from kotodama.primitives.wellbecoming_influence import (
            _InfluenceInput, _LAMBDA_LR, _MIN_SCORED_EVENTS,
        )
        from unittest.mock import MagicMock
        job = MagicMock()
        job.variables = None
        inp = _InfluenceInput.from_job(job)
        assert inp.lambda_lr == _LAMBDA_LR
        assert inp.min_scored_events == _MIN_SCORED_EVENTS

    def test_register_function_exists(self):
        from kotodama.primitives.wellbecoming_influence import register
        import inspect
        assert inspect.isfunction(register)


# ---------------------------------------------------------------------------
# ZeebeJobInput base contract
# ---------------------------------------------------------------------------

class TestZeebeJobInputBase:
    def test_from_job_is_classmethod(self):
        from kotodama.primitives.pydantic_job import ZeebeJobInput
        import inspect
        assert isinstance(inspect.getattr_static(ZeebeJobInput, "from_job"), classmethod)

    def test_all_four_are_subclasses(self):
        from kotodama.primitives.pydantic_job import ZeebeJobInput
        from kotodama.primitives.wellbecoming_trust import _TrustWeightInput
        from kotodama.primitives.wellbecoming_noise import _NoiseInput
        from kotodama.primitives.wellbecoming_restoring import _RestoringInput
        from kotodama.primitives.wellbecoming_influence import _InfluenceInput
        for cls in (_TrustWeightInput, _NoiseInput, _RestoringInput, _InfluenceInput):
            assert issubclass(cls, ZeebeJobInput), f"{cls.__name__} must subclass ZeebeJobInput"
