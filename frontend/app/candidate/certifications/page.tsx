"use client";

import { CollectionPage } from "@/components/candidate/collection-page";
import { candidateCertificationsApi } from "@/lib/api";

export default function CandidateCertificationsPage() {
  return (
    <CollectionPage
      title="Certifications"
      description="Licenses and certificates. Add at least one to raise completion."
      addLabel="Add certification"
      select={(graph) => graph.certifications}
      summarize={(item) => (
        <div>
          <p className="font-medium">{item.name}</p>
          <p className="text-zinc-500">{item.issuer || "Issuer not set"}</p>
        </div>
      )}
      fields={[
        { key: "name", label: "Name", required: true },
        { key: "issuer", label: "Issuer" },
        { key: "issued_on", label: "Issued on", kind: "date" },
      ]}
      api={candidateCertificationsApi}
    />
  );
}
