"use client";

import { CollectionPage } from "@/components/candidate/collection-page";
import { candidateEducationApi } from "@/lib/api";

export default function CandidateEducationPage() {
  return (
    <CollectionPage
      title="Education"
      description="Schools and degrees. Add at least one to raise completion."
      addLabel="Add education"
      select={(graph) => graph.education}
      summarize={(item) => (
        <div>
          <p className="font-medium">{item.school}</p>
          <p className="text-zinc-500">
            {[item.degree, item.field_of_study].filter(Boolean).join(" · ") || "No degree listed"}
          </p>
        </div>
      )}
      fields={[
        { key: "school", label: "School", required: true },
        { key: "degree", label: "Degree" },
        { key: "field_of_study", label: "Field of study" },
        { key: "start_date", label: "Start date", kind: "date" },
        { key: "end_date", label: "End date", kind: "date" },
      ]}
      api={candidateEducationApi}
    />
  );
}
