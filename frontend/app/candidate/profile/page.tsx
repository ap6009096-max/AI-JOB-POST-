"use client";

import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { GraphGate, CandidateHeading } from "@/components/candidate/heading";
import { SectionForm } from "@/components/candidate/section-form";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCandidateGraph } from "@/hooks/use-candidate-graph";
import { patchCandidatePersonal } from "@/lib/api";

export default function CandidateProfilePage() {
  const router = useRouter();
  const { data, error, loading, setData } = useCandidateGraph();
  const [givenName, setGivenName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [familyName, setFamilyName] = useState("");
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    setGivenName(data.personal.given_name);
    setMiddleName(data.personal.middle_name);
    setFamilyName(data.personal.family_name);
    setPhone(data.personal.phone);
    setCountry(data.personal.country);
    setCity(data.personal.city);
    setAddress(data.personal.address);
  }, [data]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setFormError(null);
    try {
      setData(
        await patchCandidatePersonal({
          given_name: givenName,
          middle_name: middleName,
          family_name: familyName,
          phone,
          country,
          city,
          address,
        }),
      );
      router.push("/candidate/resume");
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <CandidateHeading title="Personal information">
        Start with identity and contact details. Resume upload is next.
      </CandidateHeading>
      <GraphGate loading={loading} error={error}>
        {data ? (
          <SectionForm onSave={onSave} pending={pending} saveLabel="Save and continue">
            {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
            <FieldGroup>
              <Field>
                <FieldLabel>Given name</FieldLabel>
                <Input value={givenName} onChange={(event) => setGivenName(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Middle name</FieldLabel>
                <Input value={middleName} onChange={(event) => setMiddleName(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Family name</FieldLabel>
                <Input value={familyName} onChange={(event) => setFamilyName(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Email</FieldLabel>
                <Input value={data.personal.email || data.email} disabled />
              </Field>
              <Field>
                <FieldLabel>Phone</FieldLabel>
                <Input value={phone} onChange={(event) => setPhone(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Country</FieldLabel>
                <Input value={country} onChange={(event) => setCountry(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>City</FieldLabel>
                <Input value={city} onChange={(event) => setCity(event.target.value)} />
              </Field>
              <Field>
                <FieldLabel>Address</FieldLabel>
                <Textarea value={address} onChange={(event) => setAddress(event.target.value)} />
              </Field>
            </FieldGroup>
          </SectionForm>
        ) : null}
      </GraphGate>
    </>
  );
}
