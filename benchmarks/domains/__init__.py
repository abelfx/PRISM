"""
Benchmark Evaluation Domains for PRISM.
Contains domain generators for synthetic reasoning chains and multi-hop benchmarks.
"""

from prism.benchmarks.domains.transitive_chain import (
    generate_chain,
    generate_with_distractors,
    generate_metta_content,
    write_metta_file,
)

__all__ = [
    "generate_chain",
    "generate_with_distractors",
    "generate_metta_content",
    "write_metta_file",
]
