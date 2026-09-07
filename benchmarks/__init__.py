"""
PRISM Benchmarking and Evaluation Package.
Provides synthetic problem domains, metric collectors, and benchmark drivers.
"""

from prism.benchmarks.domains.transitive_chain import (
    generate_chain,
    generate_with_distractors,
    generate_metta_content,
    write_metta_file,
)
from prism.benchmarks.utils.metrics import (
    MetricsCollector,
    parse_selected_log,
    is_step_on_proof_path,
)

__all__ = [
    "generate_chain",
    "generate_with_distractors",
    "generate_metta_content",
    "write_metta_file",
    "MetricsCollector",
    "parse_selected_log",
    "is_step_on_proof_path",
]
