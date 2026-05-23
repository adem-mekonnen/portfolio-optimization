import { cn } from '@/lib/utils';

describe('cn()', () => {
  it('returns a single class unchanged', () => {
    expect(cn('foo')).toBe('foo');
  });

  it('joins multiple classes', () => {
    expect(cn('a', 'b', 'c')).toBe('a b c');
  });

  it('ignores falsy values', () => {
    expect(cn('a', false, undefined, null, 'b')).toBe('a b');
  });

  it('resolves Tailwind conflicts — last class wins', () => {
    // tailwind-merge should keep only the last conflicting utility
    expect(cn('p-2', 'p-4')).toBe('p-4');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });

  it('handles conditional object syntax from clsx', () => {
    expect(cn({ 'text-gain': true, 'text-loss': false })).toBe('text-gain');
  });

  it('returns empty string when all inputs are falsy', () => {
    expect(cn(false, undefined, null)).toBe('');
  });
});
