"use client";

import { CollectionPage } from "@/components/candidate/collection-page";
import { candidateAchievementsApi } from "@/lib/api";

export default function CandidateAchievementsPage() {
  return (
    <CollectionPage
      title="Achievements"
      description="Awards, publications, and other highlights."
      addLabel="Add achievement"
      select={(graph) => graph.achievements}
      summarize={(item) => (
        <div>
          <p className="font-medium">{item.title}</p>
          {item.occurred_on ? <p className="text-zinc-500">{item.occurred_on}</p> : null}
        </div>
      )}
      fields={[
        { key: "title", label: "Title", required: true },
        { key: "description", label: "Description", kind: "textarea" },
        { key: "occurred_on", label: "Date", kind: "date" },
      ]}
      api={candidateAchievementsApi}
    />
  );
}
