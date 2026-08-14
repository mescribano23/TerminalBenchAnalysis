"""Terminal-Bench 2.0 to 2.1 longitudinal analyses.

The longitudinal pipeline builds a unified trajectory dataset and then produces
the retained longitudinal figures. Summary tables are recomputed from the
trajectory dataset and raw trajectories only when they support the current RQ3
analysis.

Execution order:

    python -m scripts.analysis.longitudinal.00_build_longitudinal_dataset
    python -m scripts.analysis.longitudinal.01_plot_instruction_change_robustness
    python -m scripts.analysis.longitudinal.02_analyze_longitudinal_changes
    python -m scripts.analysis.longitudinal.03_analyze_performance_effort_over_time
    python -m scripts.analysis.longitudinal.04_analyze_token_accounting

Retained data outputs:

    data/processed_live/longitudinal/trajectory_longitudinal.csv
    data/processed_live/longitudinal/longitudinal_data_audit.json
    data/processed_live/longitudinal/token_accounting/token_accounting_comparisons.csv
    data/processed_live/longitudinal/token_accounting/token_vs_logged_text_monthly.csv
"""
