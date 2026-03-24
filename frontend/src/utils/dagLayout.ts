import type { Milestone } from "../types";

export const DAG_NODE_WIDTH = 192;
export const DAG_NODE_MIN_HEIGHT = 168;
export const DAG_LAYER_GAP = 88;
export const DAG_NODE_SPACING = 250;

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
  const milestoneIds = milestones.map((m) => m.id);

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
  for (const id of milestoneIds) {
    const layer = layers.get(id)!;
    if (!layerGroups.has(layer)) layerGroups.set(layer, []);
    layerGroups.get(layer)!.push(id);
  }

  const sortedLayers = Array.from(layerGroups.keys()).sort((a, b) => a - b);

  // Order siblings by the average x-position of their parents to reduce crossings.
  const orderedGroups = new Map<number, string[]>();
  for (const layer of sortedLayers) {
    const ids = [...(layerGroups.get(layer) ?? [])];
    if (layer === 0) {
      orderedGroups.set(layer, ids);
      continue;
    }
    ids.sort((a, b) => {
      const aParents = idToMilestone.get(a)?.depends_on ?? [];
      const bParents = idToMilestone.get(b)?.depends_on ?? [];
      const aAvg = aParents.length
        ? aParents.reduce((sum, parentId) => {
            const parentIndex = orderedGroups.get(layer - 1)?.indexOf(parentId) ?? 0;
            return sum + parentIndex;
          }, 0) / aParents.length
        : Number.MAX_SAFE_INTEGER;
      const bAvg = bParents.length
        ? bParents.reduce((sum, parentId) => {
            const parentIndex = orderedGroups.get(layer - 1)?.indexOf(parentId) ?? 0;
            return sum + parentIndex;
          }, 0) / bParents.length
        : Number.MAX_SAFE_INTEGER;
      if (aAvg !== bAvg) {
        return aAvg - bAvg;
      }
      return milestoneIds.indexOf(a) - milestoneIds.indexOf(b);
    });
    orderedGroups.set(layer, ids);
  }

  // Assign positions: center each layer horizontally
  const maxLayerSize = Math.max(...Array.from(orderedGroups.values()).map((g) => g.length));
  const canvasWidth = maxLayerSize * DAG_NODE_SPACING;

  const positions = new Map<string, Position>();
  for (const layer of sortedLayers) {
    const ids = orderedGroups.get(layer) ?? [];
    const layerWidth = ids.length * DAG_NODE_SPACING - (DAG_NODE_SPACING - DAG_NODE_WIDTH);
    const startX = (canvasWidth - layerWidth) / 2;
    ids.forEach((id, i) => {
      positions.set(id, {
        x: startX + i * DAG_NODE_SPACING,
        y: layer * (DAG_NODE_MIN_HEIGHT + DAG_LAYER_GAP) + 40,
      });
    });
  }

  return positions;
}
