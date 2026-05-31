import numpy as np
from scipy.optimize import minimize


class GARCHModel:
    """
    Fits a GARCH(1,1) model to estimate and forecast conditional volatility clustering.
    Formula:
      sigma_t^2 = omega + alpha * r_{t-1}^2 + beta * sigma_{t-1}^2
    """

    def __init__(self):
        # Initial parameters
        self.omega = 1e-6
        self.alpha = 0.05
        self.beta = 0.90

    def fit(self, returns: np.ndarray):
        """Fit GARCH(1,1) parameters using Maximum Likelihood Estimation."""
        if len(returns) < 30:
            return

        # Demean returns
        r = returns - np.mean(returns)
        initial_params = [self.omega, self.alpha, self.beta]
        
        # Constraints: omega > 0, alpha >= 0, beta >= 0, alpha + beta < 1
        bounds = ((1e-12, None), (0.0, 0.999), (0.0, 0.999))

        def constraint(params):
            return 0.999 - (params[1] + params[2])

        cons = {"type": "ineq", "fun": constraint}

        def log_likelihood(params):
            omega, alpha, beta = params
            variance = np.zeros_like(r)
            variance[0] = np.var(r)
            
            for t in range(1, len(r)):
                variance[t] = omega + alpha * (r[t - 1] ** 2) + beta * variance[t - 1]
                
            # Log likelihood of normal distribution
            ll = -0.5 * np.sum(np.log(2.0 * np.pi * variance) + (r ** 2) / variance)
            return -ll  # Return negative for minimization

        try:
            res = minimize(
                log_likelihood,
                initial_params,
                bounds=bounds,
                constraints=cons,
                method="SLSQP"
            )
            if res.success:
                self.omega, self.alpha, self.beta = res.x
        except Exception:
            # Fall back to typical parameters if MLE fails to converge
            self.omega, self.alpha, self.beta = 1e-6, 0.05, 0.90

    def calculate_volatility(self, returns: np.ndarray) -> np.ndarray:
        """Filter return series through GARCH recursion to compute conditional volatilities."""
        if len(returns) == 0:
            return np.array([])
            
        r = returns - np.mean(returns)
        variance = np.zeros_like(r)
        variance[0] = np.var(r) if len(r) > 1 else 1e-4
        
        for t in range(1, len(r)):
            variance[t] = self.omega + self.alpha * (r[t - 1] ** 2) + self.beta * variance[t - 1]
            
        return np.sqrt(variance)
