import { describe, it, expect, beforeEach } from 'vitest';
import { createFormPlayground } from '../../src/playground.js';

describe('form playground', () => {
  let container: HTMLElement;
  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('creates and destroys', async () => {
    const schema = { components: [] } as any;
    const pg = await createFormPlayground({ container, schema, data: {} });
    expect(typeof pg.destroy).toBe('function');
    pg.destroy();
  });
});

