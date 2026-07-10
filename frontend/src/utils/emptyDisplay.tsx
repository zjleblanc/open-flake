import type { ReactNode } from 'react';
import { EmptyValue } from '../components/EmptyValue';

export function isEmptyDisplayValue(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return true;
  if (typeof value === 'object' && value !== null && 'value' in value) {
    return !(value as { value?: string }).value;
  }
  return false;
}

export function displayValue(value: unknown): ReactNode {
  if (isEmptyDisplayValue(value)) return <EmptyValue />;
  if (typeof value === 'object' && value !== null && 'value' in value) {
    return String((value as { value: string }).value);
  }
  return String(value);
}
