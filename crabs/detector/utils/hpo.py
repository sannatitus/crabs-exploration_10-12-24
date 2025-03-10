"""Utils for hyperparameter optimisation with Optuna."""

from typing import Callable

import optuna


def compute_optimal_hyperparameters(
    objective_fn: Callable, config_optuna: dict, direction: str = "maximize"
) -> dict:
    """Compute hyperparameters that optimize the objective function.

    Use Optuna to optimize the objective function and return the
    hyperparameters that maximise or minimise the objective function.

    Parameters
    ----------
    objective_fn : Callable
        A function that takes `trial` as input and returns the value to
        maximise or minimise (a float).
    config_optuna : Dict
        A dictionary with the configuration parameters for Optuna.
    direction : str, optional
        Specifies whether the optimisation is to maximise or minimise
        the objective function. By default "maximize".

    Returns
    -------
    dict
        The optimal parameters computed by Optuna.

    """
    # Create an study
    study = optuna.create_study(direction=direction)

    # Optimize the objective function
    study.optimize(
        objective_fn,  #
        n_trials=config_optuna["n_trials"],
    )

    # Extract results
    best_trial = study.best_trial  # Should we log this?
    best_hyperparameters = best_trial.params

    return best_hyperparameters
