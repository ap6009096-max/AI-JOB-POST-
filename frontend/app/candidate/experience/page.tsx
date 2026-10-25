"use client";

import { CollectionPage } from "@/components/candidate/collection-page";
import { candidateExperienceApi } from "@/lib/api";

export default function CandidateExperiencePage() {
  return (
    <CollectionPage
      title="Experience"
      description="Roles you have held. Add at least one to raise completion."
      addLabel="Add experience"
      select={(graph) => graph.experience}
      summarize={(item) => (
        <div>
          <p className="font-medium">
            {item.title} at {item.company_name}
          </p>
          <p className="text-zinc-500">
            {[item.start_date, item.end_date].filter(Boolean).join(" – ") || "Dates not set"}
          </p>
        </div>
      )}
      fields={[
        { key: "title", label: "Title", required: true },
        { key: "company_name", label: "Company", required: true },
        { key: "start_date", label: "Start date", kind: "date" },
        { key: "end_date", label: "End date", kind: "date" },
        { key: "description", label: "Description", kind: "textarea" },
      ]}
      api={candidateExperienceApi}
    />
  );
}
