"use client";

import type { FormEvent, ReactNode } from "react";

import { Button } from "@/components/ui/button";

export function SectionForm({
  onSave,
  onCancel,
  pending,
  children,
  saveLabel = "Save",
}: {
  onSave: (event: FormEvent) => void | Promise<void>;
  onCancel?: () => void;
  pending?: boolean;
  children: ReactNode;
  saveLabel?: string;
}) {
  return (
    <form className="flex flex-col gap-4" onSubmit={onSave}>
      {children}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : saveLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}
