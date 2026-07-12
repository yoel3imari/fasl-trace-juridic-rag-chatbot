let mockLatency = 300;

export function setMockLatency(ms: number): void {
  mockLatency = ms;
}

export function delay(overrideMs?: number): Promise<void> {
  const ms = overrideMs ?? mockLatency;
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const USER_ID = '00000000-0000-0000-0000-000000000001';

export function generateId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function now(): string {
  return new Date().toISOString();
}

export function paginate<T>(items: T[], skip = 0, limit = 10): T[] {
  return items.slice(skip, skip + limit);
}
