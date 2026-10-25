"use client";

import { CollectionPage } from "@/components/candidate/collection-page";
import { candidateProjectsApi } from "@/lib/api";

export default function CandidateProjectsPage() {
  return (
    <CollectionPage
      title="Projects"
      description="Work you want to highlight. Add at least one to raise completion."
      addLabel="Add project"
      select={(graph) => graph.projects}
      summarize={(item) => (
        <div>
          <p className="font-medium">{item.name}</p>
          {item.url ? <p className="text-zinc-500">{item.url}</p> : null}
        </div>
      )}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "description", label: "Description", kind: "textarea" },
        { key: "url", label: "URL" },
      ]}
      api={candidateProjectsApi}
    />
  );
}
