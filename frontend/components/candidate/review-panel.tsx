"use client";

import type { CandidateProfileGraph } from "@/lib/types";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
      <h2 className="text-sm font-medium tracking-wide text-zinc-500 uppercase">{title}</h2>
      <div className="mt-3 text-sm text-zinc-800 dark:text-zinc-200">{children}</div>
    </section>
  );
}

function yesNo(value: boolean | null): string {
  if (value == null) {
    return "Not set";
  }
  return value ? "Yes" : "No";
}

export function ReviewPanel({ graph }: { graph: CandidateProfileGraph }) {
  const personal = graph.personal;
  const links = graph.professional_links;
  return (
    <div className="flex flex-col gap-4">
      <Block title="Personal information">
        <p className="font-medium">{graph.full_name || "Unnamed"}</p>
        <p>
          {[personal.given_name, personal.middle_name, personal.family_name].filter(Boolean).join(" ") || "No name parts"}
        </p>
        <p>{personal.email || graph.email || "No email"}</p>
        <p>{personal.phone || "No phone"}</p>
        <p>{[personal.city, personal.country].filter(Boolean).join(", ") || graph.profile.location || "No location"}</p>
        <p className="whitespace-pre-wrap">{personal.address || "No address"}</p>
      </Block>
      <Block title="Professional information">
        <p className="font-medium">{graph.profile.headline || "No current role"}</p>
        <p className="mt-2 whitespace-pre-wrap">{graph.profile.summary || "No summary yet."}</p>
      </Block>
      <Block title="Resume">
        <p className="whitespace-pre-wrap">{graph.resume.text || "No resume text."}</p>
        {graph.resume.url ? (
          <a className="mt-2 inline-block underline" href={graph.resume.url}>
            {graph.resume.url}
          </a>
        ) : null}
      </Block>
      <Block title="Experience">
        {graph.experience.length === 0
          ? "None"
          : graph.experience.map((item) => (
              <p key={item.id}>
                {item.title} at {item.company_name}
              </p>
            ))}
      </Block>
      <Block title="Education">
        {graph.education.length === 0
          ? "None"
          : graph.education.map((item) => (
              <p key={item.id}>
                {item.school}
                {item.degree ? ` · ${item.degree}` : ""}
              </p>
            ))}
      </Block>
      <Block title="Skills">
        {graph.skills.length === 0 ? "None" : graph.skills.map((item) => item.skill).join(", ")}
      </Block>
      <Block title="Technologies">
        {graph.technologies.length === 0 ? "None" : graph.technologies.map((item) => item.name).join(", ")}
      </Block>
      <Block title="Projects">
        {graph.projects.length === 0
          ? "None"
          : graph.projects.map((item) => <p key={item.id}>{item.name}</p>)}
      </Block>
      <Block title="Certifications">
        {graph.certifications.length === 0
          ? "None"
          : graph.certifications.map((item) => <p key={item.id}>{item.name}</p>)}
      </Block>
      <Block title="Achievements">
        {graph.achievements.length === 0
          ? "None"
          : graph.achievements.map((item) => <p key={item.id}>{item.title}</p>)}
      </Block>
      <Block title="Professional Links">
        <p>LinkedIn: {links.linkedin || "None"}</p>
        <p>GitHub: {links.github || "None"}</p>
        <p>Portfolio: {links.portfolio || "None"}</p>
        <p>Website: {links.website || "None"}</p>
        {links.other.length === 0
          ? null
          : links.other.map((item) => (
              <p key={item.id}>
                {item.source}
                {item.url ? ` · ${item.url}` : ""}
              </p>
            ))}
      </Block>
      <Block title="Preferences">
        <p>Open to work: {yesNo(graph.preferences.open_to_work)}</p>
        <p>Work mode: {graph.preferences.work_mode || "Not set"}</p>
        <p>Employment type: {graph.preferences.employment_type || "Not set"}</p>
        <p>Salary: {graph.preferences.salary_expectation || "Not set"}</p>
        <p>Roles: {graph.preferences.desired_roles.join(", ") || "None"}</p>
        <p>Locations: {graph.preferences.locations.join(", ") || "None"}</p>
      </Block>
    </div>
  );
}
