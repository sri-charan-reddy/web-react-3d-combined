/**
 * Motion-trail ring buffers for the arena renderer.
 *
 * Trails are view-only history: the backend sends positions, not paths. Keeping
 * them in an owned object (rather than module-level arrays, as the vanilla
 * build did) means a terminal reconfiguration can reset them cleanly instead of
 * leaving ghost trails between old and new positions.
 */
export interface Point {
  x: number;
  y: number;
}

export class TrailStore {
  private readonly trails = new Map<string, Point[]>();

  /** Append a position, trimming the trail to `limit` points. */
  push(id: string, x: number, y: number, limit: number): readonly Point[] {
    let trail = this.trails.get(id);
    if (!trail) {
      trail = [];
      this.trails.set(id, trail);
    }
    trail.push({ x, y });
    if (trail.length > limit) trail.splice(0, trail.length - limit);
    return trail;
  }

  get(id: string): readonly Point[] {
    return this.trails.get(id) ?? [];
  }

  /** Drop every trail — call when the terminal set changes. */
  clear(): void {
    this.trails.clear();
  }

  /** Drop trails for terminals no longer present, so the map can't grow forever. */
  retain(liveIds: Iterable<string>): void {
    const keep = new Set(liveIds);
    for (const id of this.trails.keys()) {
      if (!keep.has(id)) this.trails.delete(id);
    }
  }
}

/** Trail id for the currently selected target (its identity can change). */
export const TARGET_TRAIL = '__target__';
