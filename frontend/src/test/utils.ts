/**
 * Shared test utilities.
 *
 * Wraps @testing-library/react's render with a pre-configured userEvent
 * instance so every test gets `user` for free:
 *
 *   const { user } = render(<MyComponent />);
 *   await user.click(screen.getByRole('button'));
 */
import { render as rtlRender, type RenderOptions } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';

export * from '@testing-library/react';
export { userEvent };

export function render(ui: ReactElement, options?: RenderOptions) {
  const user = userEvent.setup();
  return { user, ...rtlRender(ui, options) };
}
