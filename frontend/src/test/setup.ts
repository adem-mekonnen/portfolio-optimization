import '@testing-library/jest-dom';

// Silence recharts' ResizeObserver warnings in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
