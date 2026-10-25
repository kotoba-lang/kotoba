import { describe, it, expect, beforeEach } from 'vitest';
import { createDmnViewer } from '../../src/viewer.js';

describe('dmn viewer', () => {
  let container: HTMLElement;
  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('creates and destroys', async () => {
    const viewer = await createDmnViewer({ container });
    expect(typeof viewer.importXML).toBe('function');
    viewer.destroy();
  });
});

