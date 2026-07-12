"use client";

import { useCallback, useEffect, useState } from "react";
import { FolderKanban } from "lucide-react";
import { api } from "@/lib/data";
import type { CollectionResponse } from "@/lib/data";
import { useChatStore } from "@/store/useChatStore";

export function CollectionSelector() {
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const selectedCollectionId = useChatStore(
    (s) => s.workspace.selectedCollectionId
  );
  const setSelectedCollection = useChatStore((s) => s.setSelectedCollection);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        const res = await api.listCollections({ skip: 0, limit: 100 });
        if (!cancelled) {
          setCollections(res.collections);
        }
      } catch {} finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setSelectedCollection(e.target.value || null);
    },
    [setSelectedCollection]
  );

  return (
    <div className="flex items-center gap-2">
      <FolderKanban className="w-4 h-4 text-slate-500 shrink-0" />
      <div className="flex flex-col">
        <label
          htmlFor="collection-select"
          className="text-[10px] uppercase tracking-wider text-slate-500 leading-none mb-0.5"
        >
          Collection
        </label>
        <select
          id="collection-select"
          value={selectedCollectionId ?? ""}
          onChange={handleChange}
          disabled={loading}
          className="appearance-none bg-slate-800 border border-slate-700 rounded px-2 py-0.5 text-sm text-slate-200 leading-tight cursor-pointer focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50 disabled:opacity-50 disabled:cursor-not-allowed min-w-[160px]"
        >
          {loading ? (
            <option value="" disabled>
              Loading...
            </option>
          ) : (
            <>
              <option value="">All documents</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </>
          )}
        </select>
      </div>
    </div>
  );
}
