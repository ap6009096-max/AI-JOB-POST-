"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  cloneParseDraft,
  emptyAchievement,
  emptyCertification,
  emptyEducation,
  emptyExperience,
  emptyProject,
  emptySkill,
  emptyTechnology,
  parseDraftToPayload,
  type ResumeParseDraft,
} from "@/lib/candidate/resume-parse-draft";
import type { CandidateResumeParseResult } from "@/lib/types";

function replaceAt<T>(items: T[], index: number, patch: Partial<T>): T[] {
  return items.map((item, current) => (current === index ? { ...item, ...patch } : item));
}

function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_, current) => current !== index);
}

function DraftSection({
  title,
  addLabel,
  onAdd,
  children,
}: {
  title: string;
  addLabel: string;
  onAdd: () => void;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          {addLabel}
        </Button>
      </div>
      {children}
    </section>
  );
}

function RowCard({
  onDelete,
  children,
}: {
  onDelete: () => void;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
      {children}
      <Button type="button" variant="ghost" size="sm" className="self-start" onClick={onDelete}>
        Delete
      </Button>
    </div>
  );
}

export function ResumeParseReview({
  parseResult,
  parseKey,
  pending,
  error,
  onApprove,
}: {
  parseResult: CandidateResumeParseResult;
  parseKey: string;
  pending: boolean;
  error: string | null;
  onApprove: (draft: CandidateResumeParseResult) => Promise<void>;
}) {
  const [draft, setDraft] = useState<ResumeParseDraft>(() => cloneParseDraft(parseResult));
  const lastKey = useRef(parseKey);

  useEffect(() => {
    if (lastKey.current === parseKey) {
      return;
    }
    lastKey.current = parseKey;
    setDraft(cloneParseDraft(parseResult));
  }, [parseKey, parseResult]);

  function patch(fields: Partial<ResumeParseDraft>) {
    setDraft((current) => ({ ...current, ...fields }));
  }

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(event) => {
        event.preventDefault();
        void onApprove(parseDraftToPayload(draft));
      }}
    >
      <div>
        <h2 className="text-lg font-medium">Review extracted profile</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Edit, delete, or add anything the model got wrong. Nothing is saved to your profile until you
          approve.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
        <h3 className="text-sm font-medium">Personal information</h3>
        <FieldGroup>
          <Field>
            <FieldLabel>Given name</FieldLabel>
            <Input value={draft.given_name} onChange={(event) => patch({ given_name: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel>Middle name</FieldLabel>
            <Input value={draft.middle_name} onChange={(event) => patch({ middle_name: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel>Family name</FieldLabel>
            <Input value={draft.family_name} onChange={(event) => patch({ family_name: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel>Email (from resume, not saved)</FieldLabel>
            <Input value={draft.email} disabled readOnly />
          </Field>
          <Field>
            <FieldLabel>Phone</FieldLabel>
            <Input value={draft.phone} onChange={(event) => patch({ phone: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel>Country</FieldLabel>
            <Input value={draft.country} onChange={(event) => patch({ country: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel>City</FieldLabel>
            <Input value={draft.city} onChange={(event) => patch({ city: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel>Address</FieldLabel>
            <Input value={draft.address} onChange={(event) => patch({ address: event.target.value })} />
          </Field>
        </FieldGroup>
      </section>

      <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
        <h3 className="text-sm font-medium">Professional summary</h3>
        <FieldGroup>
          <Field>
            <FieldLabel>Current role</FieldLabel>
            <Input
              value={draft.current_role}
              onChange={(event) => patch({ current_role: event.target.value })}
            />
          </Field>
          <Field>
            <FieldLabel>Professional summary</FieldLabel>
            <Textarea value={draft.summary} onChange={(event) => patch({ summary: event.target.value })} />
          </Field>
        </FieldGroup>
      </section>

      <DraftSection
        title="Experience"
        addLabel="Add experience"
        onAdd={() => patch({ experience: [...draft.experience, emptyExperience()] })}
      >
        {draft.experience.length === 0 ? (
          <p className="text-sm text-zinc-500">No experience extracted. Add a role if you want one saved.</p>
        ) : (
          draft.experience.map((item, index) => (
            <RowCard
              key={`experience-${index}`}
              onDelete={() => patch({ experience: removeAt(draft.experience, index) })}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel>Title</FieldLabel>
                  <Input
                    value={item.title}
                    onChange={(event) =>
                      patch({ experience: replaceAt(draft.experience, index, { title: event.target.value }) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Company</FieldLabel>
                  <Input
                    value={item.company_name}
                    onChange={(event) =>
                      patch({
                        experience: replaceAt(draft.experience, index, { company_name: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Start date</FieldLabel>
                  <Input
                    value={item.start_date}
                    onChange={(event) =>
                      patch({
                        experience: replaceAt(draft.experience, index, { start_date: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>End date</FieldLabel>
                  <Input
                    value={item.end_date}
                    onChange={(event) =>
                      patch({
                        experience: replaceAt(draft.experience, index, { end_date: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Description</FieldLabel>
                  <Textarea
                    value={item.description}
                    onChange={(event) =>
                      patch({
                        experience: replaceAt(draft.experience, index, { description: event.target.value }),
                      })
                    }
                  />
                </Field>
              </FieldGroup>
            </RowCard>
          ))
        )}
      </DraftSection>

      <DraftSection
        title="Education"
        addLabel="Add education"
        onAdd={() => patch({ education: [...draft.education, emptyEducation()] })}
      >
        {draft.education.length === 0 ? (
          <p className="text-sm text-zinc-500">No education extracted.</p>
        ) : (
          draft.education.map((item, index) => (
            <RowCard
              key={`education-${index}`}
              onDelete={() => patch({ education: removeAt(draft.education, index) })}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel>School</FieldLabel>
                  <Input
                    value={item.school}
                    onChange={(event) =>
                      patch({ education: replaceAt(draft.education, index, { school: event.target.value }) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Degree</FieldLabel>
                  <Input
                    value={item.degree}
                    onChange={(event) =>
                      patch({ education: replaceAt(draft.education, index, { degree: event.target.value }) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Field of study</FieldLabel>
                  <Input
                    value={item.field_of_study}
                    onChange={(event) =>
                      patch({
                        education: replaceAt(draft.education, index, { field_of_study: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Start date</FieldLabel>
                  <Input
                    value={item.start_date}
                    onChange={(event) =>
                      patch({
                        education: replaceAt(draft.education, index, { start_date: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>End date</FieldLabel>
                  <Input
                    value={item.end_date}
                    onChange={(event) =>
                      patch({
                        education: replaceAt(draft.education, index, { end_date: event.target.value }),
                      })
                    }
                  />
                </Field>
              </FieldGroup>
            </RowCard>
          ))
        )}
      </DraftSection>

      <DraftSection
        title="Skills"
        addLabel="Add skill"
        onAdd={() => patch({ skills: [...draft.skills, emptySkill()] })}
      >
        {draft.skills.length === 0 ? (
          <p className="text-sm text-zinc-500">No skills extracted.</p>
        ) : (
          draft.skills.map((item, index) => (
            <RowCard key={`skill-${index}`} onDelete={() => patch({ skills: removeAt(draft.skills, index) })}>
              <FieldGroup>
                <Field>
                  <FieldLabel>Skill</FieldLabel>
                  <Input
                    value={item.skill}
                    onChange={(event) =>
                      patch({ skills: replaceAt(draft.skills, index, { skill: event.target.value }) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Years</FieldLabel>
                  <Input
                    type="number"
                    min="0"
                    step="0.5"
                    value={item.years ?? ""}
                    onChange={(event) =>
                      patch({
                        skills: replaceAt(draft.skills, index, {
                          years: event.target.value === "" ? null : Number(event.target.value),
                        }),
                      })
                    }
                  />
                </Field>
              </FieldGroup>
            </RowCard>
          ))
        )}
      </DraftSection>

      <DraftSection
        title="Technologies"
        addLabel="Add technology"
        onAdd={() => patch({ technologies: [...draft.technologies, emptyTechnology()] })}
      >
        {draft.technologies.length === 0 ? (
          <p className="text-sm text-zinc-500">No technologies extracted.</p>
        ) : (
          draft.technologies.map((item, index) => (
            <RowCard
              key={`technology-${index}`}
              onDelete={() => patch({ technologies: removeAt(draft.technologies, index) })}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel>Name</FieldLabel>
                  <Input
                    value={item.name}
                    onChange={(event) =>
                      patch({
                        technologies: replaceAt(draft.technologies, index, { name: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Years</FieldLabel>
                  <Input
                    type="number"
                    min="0"
                    step="0.5"
                    value={item.years ?? ""}
                    onChange={(event) =>
                      patch({
                        technologies: replaceAt(draft.technologies, index, {
                          years: event.target.value === "" ? null : Number(event.target.value),
                        }),
                      })
                    }
                  />
                </Field>
              </FieldGroup>
            </RowCard>
          ))
        )}
      </DraftSection>

      <DraftSection
        title="Projects"
        addLabel="Add project"
        onAdd={() => patch({ projects: [...draft.projects, emptyProject()] })}
      >
        {draft.projects.length === 0 ? (
          <p className="text-sm text-zinc-500">No projects extracted.</p>
        ) : (
          draft.projects.map((item, index) => (
            <RowCard
              key={`project-${index}`}
              onDelete={() => patch({ projects: removeAt(draft.projects, index) })}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel>Name</FieldLabel>
                  <Input
                    value={item.name}
                    onChange={(event) =>
                      patch({ projects: replaceAt(draft.projects, index, { name: event.target.value }) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>URL</FieldLabel>
                  <Input
                    value={item.url}
                    onChange={(event) =>
                      patch({ projects: replaceAt(draft.projects, index, { url: event.target.value }) })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Description</FieldLabel>
                  <Textarea
                    value={item.description}
                    onChange={(event) =>
                      patch({
                        projects: replaceAt(draft.projects, index, { description: event.target.value }),
                      })
                    }
                  />
                </Field>
              </FieldGroup>
            </RowCard>
          ))
        )}
      </DraftSection>

      <DraftSection
        title="Certifications"
        addLabel="Add certification"
        onAdd={() => patch({ certifications: [...draft.certifications, emptyCertification()] })}
      >
        {draft.certifications.length === 0 ? (
          <p className="text-sm text-zinc-500">No certifications extracted.</p>
        ) : (
          draft.certifications.map((item, index) => (
            <RowCard
              key={`certification-${index}`}
              onDelete={() => patch({ certifications: removeAt(draft.certifications, index) })}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel>Name</FieldLabel>
                  <Input
                    value={item.name}
                    onChange={(event) =>
                      patch({
                        certifications: replaceAt(draft.certifications, index, { name: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Issuer</FieldLabel>
                  <Input
                    value={item.issuer}
                    onChange={(event) =>
                      patch({
                        certifications: replaceAt(draft.certifications, index, {
                          issuer: event.target.value,
                        }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Issued on</FieldLabel>
                  <Input
                    value={item.issued_on}
                    onChange={(event) =>
                      patch({
                        certifications: replaceAt(draft.certifications, index, {
                          issued_on: event.target.value,
                        }),
                      })
                    }
                  />
                </Field>
              </FieldGroup>
            </RowCard>
          ))
        )}
      </DraftSection>

      <DraftSection
        title="Achievements"
        addLabel="Add achievement"
        onAdd={() => patch({ achievements: [...draft.achievements, emptyAchievement()] })}
      >
        {draft.achievements.length === 0 ? (
          <p className="text-sm text-zinc-500">No achievements extracted.</p>
        ) : (
          draft.achievements.map((item, index) => (
            <RowCard
              key={`achievement-${index}`}
              onDelete={() => patch({ achievements: removeAt(draft.achievements, index) })}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel>Title</FieldLabel>
                  <Input
                    value={item.title}
                    onChange={(event) =>
                      patch({
                        achievements: replaceAt(draft.achievements, index, { title: event.target.value }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Description</FieldLabel>
                  <Textarea
                    value={item.description}
                    onChange={(event) =>
                      patch({
                        achievements: replaceAt(draft.achievements, index, {
                          description: event.target.value,
                        }),
                      })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>Date</FieldLabel>
                  <Input
                    value={item.occurred_on}
                    onChange={(event) =>
                      patch({
                        achievements: replaceAt(draft.achievements, index, {
                          occurred_on: event.target.value,
                        }),
                      })
                    }
                  />
                </Field>
              </FieldGroup>
            </RowCard>
          ))
        )}
      </DraftSection>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : "Approve and save"}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={pending}
          onClick={() => setDraft(cloneParseDraft(parseResult))}
        >
          Reset to extracted
        </Button>
      </div>
    </form>
  );
}
