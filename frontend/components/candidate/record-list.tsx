"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

export function RecordList<T>({
  items,
  getKey,
  renderSummary,
  onAdd,
  onEdit,
  onDelete,
  addLabel = "Add",
}: {
  items: T[];
  getKey: (item: T) => string;
  renderSummary: (item: T) => ReactNode;
  onAdd: () => void;
  onEdit: (item: T) => void;
  onDelete: (item: T) => void;
  addLabel?: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button type="button" onClick={onAdd}>
          {addLabel}
        </Button>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500">Nothing saved yet. Add your first entry.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <li
              key={getKey(item)}
              className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800 dark:bg-zinc-950"
            >
              <div className="text-sm">{renderSummary(item)}</div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => onEdit(item)}>
                  Edit
                </Button>
                <Button type="button" variant="destructive" size="sm" onClick={() => onDelete(item)}>
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
