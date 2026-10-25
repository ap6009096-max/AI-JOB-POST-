import { describe, expect, it } from "vitest";

import { sliceStoredRanking } from "../../frontend/lib/dashboard/ranking";

describe("sliceStoredRanking", () => {
  const rows = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

  it("slices a stored run to Top 10 without changing the source list", () => {
    expect(sliceStoredRanking(rows, 10)).toEqual(rows.slice(0, 10));
    expect(rows).toHaveLength(12);
  });

  it("returns the full stored list when it is shorter than the view limit", () => {
    expect(sliceStoredRanking(rows, 20)).toEqual(rows);
    expect(sliceStoredRanking(rows, 100)).toEqual(rows);
  });

  it("treats a missing run as empty", () => {
    expect(sliceStoredRanking(null, 10)).toEqual([]);
    expect(sliceStoredRanking(undefined, 100)).toEqual([]);
  });
});
