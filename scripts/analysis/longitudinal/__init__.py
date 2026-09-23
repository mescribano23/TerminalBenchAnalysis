"""Terminal-Bench longitudinal analyses.

The pipeline first builds the TB2.0/TB2.1 matched longitudinal dataset, then
adds descriptive analyses for TB3.0/TB4.0 task pools.

Execution order:

    python -m scripts.analysis.longitudinal.00_build_dataset
    python -m scripts.analysis.longitudinal.01_analyze_instruction_change_robustness
    python -m scripts.analysis.longitudinal.02_analyze_pass_rate_changes
    python -m scripts.analysis.longitudinal.03_analyze_effort_changes
    python -m scripts.analysis.longitudinal.04_analyze_token_accounting
    python -m scripts.analysis.longitudinal.05_analyze_performance_over_versions
    python -m scripts.analysis.longitudinal.06_label_tb2_task_categories_with_llm
    python -m scripts.analysis.longitudinal.07_analyze_task_composition_over_versions
    python -m scripts.analysis.longitudinal.08_label_task_difficulty_with_llm
    python -m scripts.analysis.longitudinal.09_analyze_difficulty_over_versions

Retained data outputs:

    data/processed_live/longitudinal/trajectory_longitudinal.csv
    data/processed_live/longitudinal/longitudinal_data_audit.json
    data/processed_live/longitudinal/token_accounting/token_accounting_comparisons.csv
    data/processed_live/longitudinal/token_accounting/token_vs_logged_text_monthly.csv
    data/processed_live/longitudinal/task_composition/version_task_composition_summary.csv
    data/processed_live/longitudinal/difficulty_over_versions/pass_rate_by_difficulty_over_versions.csv
"""
