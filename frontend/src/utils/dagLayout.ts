import type { Milestone } from "../types";

const LAYER_HEIGHT = 220;
const NODE_SPACING = 250;
const NODE_WIDTH = 192;

export interface Position {
  x: number;
  y: number;
}

/**
 * Computes x/y positions for milestones using a layered DAG layout.
 * Each milestone is placed on a layer determined by the longest path from
 * any root. Within each layer, nodes are spread horizontally and centered.
 */
export function computeDagLayout(milestones: Milestone[]): Map<string, Position> {
  if (milestones.length === 0) return new Map();

  const idToMilestone = new Map(milestones.map((m) => [m.id, m]));

  // Assign layers: layer = max(layer of predecessors) + 1, roots = layer 0
  const layers = new Map<string, number>();

  function getLayer(id: string): number {
    if (layers.has(id)) return layers.get(id)!;
    const m = idToMilestone.get(id);
    if (!m || m.depends_on.length === 0) {
      layers.set(id, 0);
      return 0;
    }
    const layer = Math.max(...m.depends_on.map(getLayer)) + 1;
    layers.set(id, layer);
    return layer;
  }

  for (const m of milestones) {
    getLayer(m.id);
  }

  // Group milestones by layer
  const layerGroups = new Map<number, string[]>();
  for (const [id, layer] of layers) {
    if (!layerGroups.has(layer)) layerGroups.set(layer, []);
    layerGroups.get(layer)!.push(id);
  }

  // Assign positions: center each layer horizontally
  const maxLayerSize = Math.max(...Array.from(layerGroups.values()).map((g) => g.length));
  const canvasWidth = maxLayerSize * NODE_SPACING;

  const positions = new Map<string, Position>();
  for (const [layer, ids] of layerGroups) {
    const layerWidth = ids.length * NODE_SPACING - (NODE_SPACING - NODE_WIDTH);
    const startX = (canvasWidth - layerWidth) / 2;
    ids.forEach((id, i) => {
      positions.set(id, {
        x: startX + i * NODE_SPACING,
        y: layer * LAYER_HEIGHT + 40,
      });
    });
  }

  return positions;
}
