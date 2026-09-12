"""
Benchmark Evaluation Domains for PRISM.
Contains domain generators for synthetic reasoning chains and multi-hop benchmarks.
"""

from prism.benchmarks.domains.multipath_dag import (
    classify_diamond_solution,
    generate_diamond,
    generate_diamond_metta_content,
    generate_diamond_with_distractors,
    write_diamond_metta_file,
)
from prism.benchmarks.domains.transitive_chain import (
    generate_chain,
    generate_metta_content,
    generate_with_distractors,
    write_metta_file,
)
from prism.benchmarks.domains.tree_dag import (
    generate_tree_conjunction,
    generate_tree_metta_content,
    generate_tree_with_distractors,
    verify_tree_conjunction_solution,
    write_tree_metta_file,
)

__all__ = [
    "generate_chain",
    "generate_with_distractors",
    "generate_metta_content",
    "write_metta_file",
    "generate_diamond",
    "generate_diamond_with_distractors",
    "generate_diamond_metta_content",
    "write_diamond_metta_file",
    "classify_diamond_solution",
    "generate_tree_conjunction",
    "generate_tree_with_distractors",
    "generate_tree_metta_content",
    "write_tree_metta_file",
    "verify_tree_conjunction_solution",
]
