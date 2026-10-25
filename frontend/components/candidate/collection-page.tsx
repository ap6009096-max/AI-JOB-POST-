"use client";

import type { FormEvent, ReactNode } from "react";
import { useState } from "react";

import { RecordList } from "@/components/candidate/record-list";
import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { SectionForm } from "@/components/candidate/section-form";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import type { CandidateProfileGraph } from "@/lib/types";

export type CollectionField = {
  key: string;
  label: string;
  kind?: "text" | "textarea" | "date" | "number";
  required?: boolean;
};

function emptyFromFields(fields: CollectionField[]): Record<string, string> {
  return Object.fromEntries(fields.map((field) => [field.key, ""]));
}

function valuesFromItem(fields: CollectionField[], item: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    fields.map((field) => {
      const value = item[field.key];
      return [field.key, value == null ? "" : String(value)];
    }),
  );
}

function bodyFromValues(fields: CollectionField[], values: Record<string, string>): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const field of fields) {
    const raw = values[field.key] ?? "";
    if (field.kind === "number") {
      body[field.key] = raw.trim() === "" ? null : Number(raw);
    } else if (field.kind === "date") {
      body[field.key] = raw.trim() === "" ? null : raw;
    } else {
      body[field.key] = raw;
    }
  }
  return body;
}

export function CollectionPage<T extends { id: string }>({
  title,
  description,
  select,
  fields,
  summarize,
  api,
  addLabel,
}: {
  title: string;
  description: string;
  select: (graph: CandidateProfileGraph) => T[];
  fields: CollectionField[];
  summarize: (item: T) => ReactNode;
  api: {
    create: (body: unknown) => Promise<unknown>;
    update: (id: string, body: unknown) => Promise<unknown>;
    remove: (id: string) => Promise<void>;
  };
  addLabel?: string;
}) {
  const { data, error, loading, reload } = useCandidateGraph();
  const [editing, setEditing] = useState<T | "new" | null>(null);
  const [values, setValues] = useState<Record<string, string>>(() => emptyFromFields(fields));
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function startAdd() {
    setFormError(null);
    setValues(emptyFromFields(fields));
    setEditing("new");
  }

  function startEdit(item: T) {
    setFormError(null);
    setValues(valuesFromItem(fields, item as unknown as Record<string, unknown>));
    setEditing(item);
  }

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      const body = bodyFromValues(fields, values);
      if (editing === "new") {
        await api.create(body);
      } else if (editing) {
        await api.update(editing.id, body);
      }
      setEditing(null);
      await reload();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  async function onDelete(item: T) {
    if (!window.confirm("Delete this entry?")) {
      return;
    }
    setFormError(null);
    try {
      await api.remove(item.id);
      if (editing !== "new" && editing?.id === item.id) {
        setEditing(null);
      }
      await reload();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Delete failed");
    }
  }

  return (
    <>
      <CandidateHeading title={title}>{description}</CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <div className="flex flex-col gap-6">
            {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
            {editing ? (
              <SectionForm onSave={onSave} onCancel={() => setEditing(null)} pending={pending}>
                <FieldGroup>
                  {fields.map((field) => (
                    <Field key={field.key}>
                      <FieldLabel>{field.label}</FieldLabel>
                      {field.kind === "textarea" ? (
                        <Textarea
                          required={field.required}
                          value={values[field.key] ?? ""}
                          onChange={(event) =>
                            setValues((current) => ({ ...current, [field.key]: event.target.value }))
                          }
                        />
                      ) : (
                        <Input
                          type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"}
                          required={field.required}
                          value={values[field.key] ?? ""}
                          onChange={(event) =>
                            setValues((current) => ({ ...current, [field.key]: event.target.value }))
                          }
                        />
                      )}
                    </Field>
                  ))}
                </FieldGroup>
              </SectionForm>
            ) : (
              <RecordList
                items={select(data)}
                getKey={(item) => item.id}
                renderSummary={summarize}
                onAdd={startAdd}
                onEdit={startEdit}
                onDelete={onDelete}
                addLabel={addLabel}
              />
            )}
          </div>
        ) : null}
      </GraphGate>
    </>
  );
}
