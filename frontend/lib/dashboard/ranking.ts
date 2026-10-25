export const RANK_VIEW_LIMITS = [10, 20, 100] as const;

export type RankViewLimit = (typeof RANK_VIEW_LIMITS)[number];

export function sliceStoredRanking<T>(results: T[] | null | undefined, viewLimit: RankViewLimit): T[] {
  return (results ?? []).slice(0, viewLimit);
}
