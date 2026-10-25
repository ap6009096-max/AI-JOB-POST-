"use client";

import { CollectionPage } from "@/components/candidate/collection-page";
import { candidateTechnologiesApi } from "@/lib/api";

export default function CandidateTechnologiesPage() {
  return (
    <CollectionPage
      title="Technologies"
      description="Tools and platforms you use. Separate from skills."
      addLabel="Add technology"
      select={(graph) => graph.technologies}
      summarize={(item) => (
        <p className="font-medium">
          {item.name}
          {item.years != null ? ` · ${item.years} years` : ""}
        </p>
      )}
      fields={[
        { key: "name", label: "Technology", required: true },
        { key: "years", label: "Years", kind: "number" },
      ]}
      api={candidateTechnologiesApi}
    />
  );
}
