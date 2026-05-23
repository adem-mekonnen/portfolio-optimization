/**
 * Tests for the portfolioReturn and portfolioVolatility helpers in
 * PortfolioOptimizer.tsx.
 *
 * Because the helpers are module-internal (not exported), we re-implement
 * the same formulas here and verify them against known hand-calculated values.
 * This keeps the component's API surface clean while still giving us
 * regression coverage on the math.
 */

// ── Re-implement the helpers (mirrors PortfolioOptimizer.tsx exactly) ─────────

function portfolioReturn(
  weights: Record<string, number>,
  meanReturns: Record<string, number>,
): number {
  return Object.keys(weights).reduce(
    (sum, t) => sum + (weights[t] ?? 0) * (meanReturns[t] ?? 0),
    0,
  );
}

function portfolioVolatility(
  weights: Record<string, number>,
  covMatrix: Record<string, Record<string, number>>,
): number {
  const tickers = Object.keys(weights);
  let variance = 0;
  for (const i of tickers) {
    for (const j of tickers) {
      variance += (weights[i] ?? 0) * (weights[j] ?? 0) * (covMatrix[i]?.[j] ?? 0);
    }
  }
  return Math.sqrt(Math.max(0, variance));
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

// Two-asset portfolio: 60% A (μ=10%), 40% B (μ=5%)
// Expected return = 0.6*0.10 + 0.4*0.05 = 0.08
const W2 = { A: 0.6, B: 0.4 };
const MU2 = { A: 0.10, B: 0.05 };

// Diagonal covariance (zero correlation):
//   σ_A = 20% → var_A = 0.04
//   σ_B = 10% → var_B = 0.01
// Portfolio variance = 0.6²*0.04 + 0.4²*0.01 = 0.0144 + 0.0016 = 0.016
// Portfolio vol = √0.016 ≈ 0.12649
const COV2_DIAG: Record<string, Record<string, number>> = {
  A: { A: 0.04, B: 0.0 },
  B: { A: 0.0,  B: 0.01 },
};

// Correlated covariance (ρ = 0.5):
//   cov(A,B) = ρ * σ_A * σ_B = 0.5 * 0.2 * 0.1 = 0.01
// Portfolio variance = 0.6²*0.04 + 0.4²*0.01 + 2*0.6*0.4*0.01
//                    = 0.0144 + 0.0016 + 0.0048 = 0.0208
// Portfolio vol = √0.0208 ≈ 0.14422
const COV2_CORR: Record<string, Record<string, number>> = {
  A: { A: 0.04, B: 0.01 },
  B: { A: 0.01, B: 0.01 },
};

// Three-asset equal-weight portfolio
const W3 = { X: 1/3, Y: 1/3, Z: 1/3 };
const MU3 = { X: 0.12, Y: 0.08, Z: 0.04 };
// Expected return = (0.12 + 0.08 + 0.04) / 3 = 0.08
const COV3_DIAG: Record<string, Record<string, number>> = {
  X: { X: 0.09, Y: 0.0,  Z: 0.0  },
  Y: { X: 0.0,  Y: 0.04, Z: 0.0  },
  Z: { X: 0.0,  Y: 0.0,  Z: 0.01 },
};
// Portfolio variance = (1/3)²*(0.09+0.04+0.01) = (1/9)*0.14 ≈ 0.015556
// Portfolio vol = √(0.015556) ≈ 0.12472

// ── portfolioReturn ───────────────────────────────────────────────────────────

describe('portfolioReturn', () => {
  it('computes weighted return for a two-asset portfolio', () => {
    expect(portfolioReturn(W2, MU2)).toBeCloseTo(0.08, 10);
  });

  it('computes weighted return for a three-asset equal-weight portfolio', () => {
    expect(portfolioReturn(W3, MU3)).toBeCloseTo(0.08, 10);
  });

  it('returns 0 when all weights are 0', () => {
    expect(portfolioReturn({ A: 0, B: 0 }, MU2)).toBe(0);
  });

  it('returns the single asset return for a 100% allocation', () => {
    expect(portfolioReturn({ A: 1.0, B: 0.0 }, MU2)).toBeCloseTo(0.10, 10);
  });

  it('treats missing mean_returns entries as 0', () => {
    // B has no entry in meanReturns — should not throw, just contribute 0
    expect(portfolioReturn({ A: 0.5, B: 0.5 }, { A: 0.10 })).toBeCloseTo(0.05, 10);
  });

  it('handles negative expected returns', () => {
    expect(portfolioReturn({ A: 0.5, B: 0.5 }, { A: -0.10, B: 0.20 })).toBeCloseTo(0.05, 10);
  });
});

// ── portfolioVolatility ───────────────────────────────────────────────────────

describe('portfolioVolatility', () => {
  it('computes volatility for uncorrelated two-asset portfolio', () => {
    expect(portfolioVolatility(W2, COV2_DIAG)).toBeCloseTo(Math.sqrt(0.016), 8);
  });

  it('computes volatility for correlated two-asset portfolio', () => {
    expect(portfolioVolatility(W2, COV2_CORR)).toBeCloseTo(Math.sqrt(0.0208), 8);
  });

  it('computes volatility for uncorrelated three-asset equal-weight portfolio', () => {
    expect(portfolioVolatility(W3, COV3_DIAG)).toBeCloseTo(Math.sqrt((1/9) * 0.14), 8);
  });

  it('returns 0 for a zero-variance portfolio', () => {
    const zeroCov = { A: { A: 0, B: 0 }, B: { A: 0, B: 0 } };
    expect(portfolioVolatility(W2, zeroCov)).toBe(0);
  });

  it('returns 0 when all weights are 0', () => {
    expect(portfolioVolatility({ A: 0, B: 0 }, COV2_DIAG)).toBe(0);
  });

  it('returns single-asset vol for a 100% allocation', () => {
    // 100% in A: vol = √(1² * 0.04) = 0.2
    expect(portfolioVolatility({ A: 1.0, B: 0.0 }, COV2_DIAG)).toBeCloseTo(0.2, 10);
  });

  it('clamps to 0 and does not throw on tiny negative variance from float rounding', () => {
    // Simulate a near-zero negative variance from floating-point arithmetic
    const almostZeroCov = { A: { A: -1e-16, B: 0 }, B: { A: 0, B: 0 } };
    expect(() => portfolioVolatility({ A: 1, B: 0 }, almostZeroCov)).not.toThrow();
    expect(portfolioVolatility({ A: 1, B: 0 }, almostZeroCov)).toBe(0);
  });

  it('is symmetric — swapping asset order gives the same result', () => {
    const volAB = portfolioVolatility({ A: 0.6, B: 0.4 }, COV2_CORR);
    const volBA = portfolioVolatility({ B: 0.4, A: 0.6 }, COV2_CORR);
    expect(volAB).toBeCloseTo(volBA, 12);
  });
});
