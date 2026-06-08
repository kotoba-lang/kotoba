"""kotoba_murakumo — Modal-compatible Python facade for the etzhayyim Murakumo fleet.

Routes Python inference calls to the Murakumo Mac mini fleet endpoints declared
in ``50-infra/murakumo/fleet.toml``, never to commercial GPU rental.

Constitutional invariant per ADR-2605215000 (Murakumo-only) + ADR-2605262200
§2(i)(2) (train carve-out leaves inference path unchanged). See ADR-2605282000
for the package design.

R0 scope: scaffold + Modal-compat surface + 3-backend routing policy. R1 wires
live LiteLLM/Ollama dispatch. R2 wires WASM Component dispatch via kotoba-vm.
"""

from . import economy, gpu
from .app import App
from .cls import enter, exit, method
from .economy import (
    BudgetExceeded,
    InsufficientCredit,
    Tariff,
    TariffRow,
    UsageActual,
    UsageEstimate,
)
from .exceptions import (
    CharterViolation,
    FleetUnreachable,
    MurakumoCompatNotImplemented,
)
from .image import Image
from .secret import Secret
from .training import (
    BenchResult,
    DataSelectionReport,
    KotobaArtifactStore,
    MurakumoModalTrainer,
    QualityDecision,
    StoredArtifact,
    TrainConfig,
    TrainRunResult,
    TrainingExample,
    run_microbench,
    score_training_example,
    select_training_examples,
    train_step_loop,
    train_with_modal_py,
)
from .volume import Volume

__all__ = [
    "App",
    "Image",
    "Volume",
    "Secret",
    "BenchResult",
    "DataSelectionReport",
    "KotobaArtifactStore",
    "MurakumoModalTrainer",
    "QualityDecision",
    "StoredArtifact",
    "TrainConfig",
    "TrainRunResult",
    "TrainingExample",
    "run_microbench",
    "score_training_example",
    "select_training_examples",
    "train_step_loop",
    "train_with_modal_py",
    "gpu",
    "economy",
    "enter",
    "exit",
    "method",
    "Tariff",
    "TariffRow",
    "UsageEstimate",
    "UsageActual",
    "BudgetExceeded",
    "InsufficientCredit",
    "CharterViolation",
    "FleetUnreachable",
    "MurakumoCompatNotImplemented",
]

__version__ = "0.1.0"
