"use client";

import { CollectionPage } from "@/components/candidate/collection-page";
import { candidateSkillsApi } from "@/lib/api";

export default function CandidateSkillsPage() {
  return (
    <CollectionPage
      title="Skills"
      description="Skills recruiters can match against. Add at least one to raise completion."
      addLabel="Add skill"
      select={(graph) => graph.skills}
      summarize={(item) => (
        <p className="font-medium">
          {item.skill}
          {item.years != null ? ` · ${item.years} years` : ""}
        </p>
      )}
      fields={[
        { key: "skill", label: "Skill", required: true },
        { key: "years", label: "Years", kind: "number" },
      ]}
      api={candidateSkillsApi}
    />
  );
}
