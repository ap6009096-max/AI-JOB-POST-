"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard/shell";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { addCompanyMember, getMe, listCompanyMembers } from "@/lib/api";
import type { MeResponse } from "@/lib/api";
import type { CompanyMember } from "@/lib/types";

export default function CompanySettingsPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [members, setMembers] = useState<CompanyMember[]>([]);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const canInvite = me?.role === "company_admin" || me?.role === "platform_admin";

  async function load() {
    const [nextMe, nextMembers] = await Promise.all([getMe(), listCompanyMembers()]);
    setMe(nextMe);
    setMembers(nextMembers);
  }

  useEffect(() => {
    load().catch((caught: Error) => setError(caught.message));
  }, []);

  async function onInvite(event: FormEvent) {
    event.preventDefault();
    if (!canInvite) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await addCompanyMember(email.trim());
      setEmail("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Invite failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <DashboardShell eyebrow="Settings" title="Settings">
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Team members for your company. Recruiters can view; company admins can invite.
      </p>
      {me ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Signed in as {me.full_name || me.email} · {me.role}
        </p>
      ) : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <ul className="flex max-w-2xl flex-col gap-2">
        {members.map((member) => (
          <li
            key={`${member.company_id}-${member.user_id}`}
            className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm dark:border-zinc-800 dark:bg-zinc-950"
          >
            <span>{member.email}</span>
            <span className="text-zinc-500">{member.role}</span>
          </li>
        ))}
      </ul>
      {canInvite ? (
        <form className="flex max-w-2xl flex-col gap-3" onSubmit={onInvite}>
          <FieldGroup>
            <Field>
              <FieldLabel>Invite recruiter by email</FieldLabel>
              <Input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </Field>
          </FieldGroup>
          <Button type="submit" disabled={pending || !email.trim()} className="w-fit">
            {pending ? "Inviting…" : "Add member"}
          </Button>
        </form>
      ) : null}
    </DashboardShell>
  );
}
