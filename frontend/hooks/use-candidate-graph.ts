"use client";

import { useCallback, useEffect, useState } from "react";

import { getCandidateGraph } from "@/lib/api";
import type { CandidateProfileGraph } from "@/lib/types";

export function useCandidateGraph() {
  const [data, setData] = useState<CandidateProfileGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getCandidateGraph());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}
