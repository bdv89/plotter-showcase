/* eslint-disable @typescript-eslint/no-explicit-any */
import { beforeEach, describe, expect, it } from 'vitest';
import { useAppStore } from './appStore';

// Reset the drawing-related slice before each test (the store is a singleton).
const reset = () =>
  useAppStore.setState({
    drawings: { shapes: [], annotations: [] },
    drawingsVisible: true,
    drawColor: '#e11d48',
  });

describe('drawings store', () => {
  beforeEach(reset);

  it('addAnnotation appends and makes the layer visible', () => {
    useAppStore.setState({ drawingsVisible: false });
    useAppStore.getState().addAnnotation({ text: 'hello' });
    const { drawings, drawingsVisible } = useAppStore.getState();
    expect(drawings.annotations).toHaveLength(1);
    expect(drawings.annotations[0]).toMatchObject({ text: 'hello' });
    expect(drawingsVisible).toBe(true);
  });

  it('clearDrawings empties shapes and annotations', () => {
    useAppStore.setState({ drawings: { shapes: [{ type: 'rect' }], annotations: [{ text: 'a' }] } });
    useAppStore.getState().clearDrawings();
    expect(useAppStore.getState().drawings).toEqual({ shapes: [], annotations: [] });
  });

  it('toggleDrawings flips visibility', () => {
    expect(useAppStore.getState().drawingsVisible).toBe(true);
    useAppStore.getState().toggleDrawings();
    expect(useAppStore.getState().drawingsVisible).toBe(false);
    useAppStore.getState().toggleDrawings();
    expect(useAppStore.getState().drawingsVisible).toBe(true);
  });

  it('setDrawColor recolors every existing shape and annotation, preserving other props', () => {
    useAppStore.setState({
      drawings: {
        shapes: [{ type: 'line', line: { width: 2, color: '#000000' } }],
        annotations: [{ text: 'a', arrowcolor: '#000000', font: { size: 16, color: '#000000' } }],
      },
    });
    useAppStore.getState().setDrawColor('#00ff00');
    const { drawColor, drawings } = useAppStore.getState();
    expect(drawColor).toBe('#00ff00');
    expect((drawings.shapes[0] as any).line.color).toBe('#00ff00');
    expect((drawings.shapes[0] as any).line.width).toBe(2); // preserved
    expect((drawings.annotations[0] as any).arrowcolor).toBe('#00ff00');
    expect((drawings.annotations[0] as any).font.color).toBe('#00ff00');
    expect((drawings.annotations[0] as any).font.size).toBe(16); // preserved
    expect((drawings.annotations[0] as any).text).toBe('a'); // preserved
  });

  it('restorePool extracts drawings from plot_style and keeps plotStyle clean', () => {
    useAppStore.getState().restorePool({
      files: [],
      styles: {},
      extracted: {},
      plot_style: {
        text_color: '#123456',
        drawings: { shapes: [{ type: 'rect' }], annotations: [{ text: 'a' }] },
      } as any,
    });
    const { drawings, plotStyle } = useAppStore.getState();
    expect(drawings.shapes).toHaveLength(1);
    expect(drawings.annotations).toHaveLength(1);
    // drawings must NOT leak into the style preset
    expect((plotStyle as any).drawings).toBeUndefined();
    // a real style field still round-trips
    expect(plotStyle.text_color).toBe('#123456');
  });

  it('restorePool with no drawings yields an empty layer', () => {
    useAppStore.setState({ drawings: { shapes: [{ type: 'rect' }], annotations: [] } });
    useAppStore.getState().restorePool({ files: [], styles: {}, extracted: {}, plot_style: {} as any });
    expect(useAppStore.getState().drawings).toEqual({ shapes: [], annotations: [] });
  });
});
