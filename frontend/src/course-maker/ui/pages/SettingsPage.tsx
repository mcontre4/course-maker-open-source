import { useOwnCreator } from "../CreatorLink";
import type { Profile } from "../../application/profile";
import { useApplication } from "../application-context";
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { z } from "zod";
import { PageHeading, QueryStatus } from "../components";
import { Avatar, useProfile } from "../profile-context";
import { useAuthentication } from "../authentication";
import { Link } from "react-router-dom";

const fields = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Enter your name.")
    .max(80, "Use 80 characters or fewer."),
  email: z.email("Enter a valid email address.").max(254),
});

export function SettingsPage() {
  const { profile } = useProfile();
  const auth = useAuthentication();
  const creators = useApplication().creators;
  const query = useOwnCreator();
  if (creators && !query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  const initial = query.data
    ? { ...profile, name: query.data.name, picture: query.data.picture }
    : profile;
  const user = auth?.session?.user;
  return (
    <SettingsForm
      key={user?.id}
      initial={user ? { ...initial, email: user.email } : initial}
    />
  );
}

function SettingsForm({ initial: profile }: { initial: Profile }) {
  const auth = useAuthentication();
  const { save } = useProfile();
  const creators = useApplication().creators;
  const cache = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [baseline, setBaseline] = useState(profile);
  const [name, setName] = useState(profile.name);
  const [email, setEmail] = useState(profile.email);
  const [picture, setPicture] = useState(profile.picture);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [reading, setReading] = useState(false);
  const readVersion = useRef(0);
  const dirty =
    name.trim() !== baseline.name ||
    email.trim() !== baseline.email ||
    picture !== baseline.picture;

  async function choosePicture(file: File | undefined) {
    if (!file) return;
    setSaved(false);
    setError("");
    const version = ++readVersion.current;
    if (
      !["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
      file.size > 1024 * 1024
    ) {
      setError("Choose a JPG, PNG, or WebP image smaller than 1 MB.");
      setReading(false);
      return;
    }
    setReading(true);
    try {
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error("Could not read image."));
        reader.readAsDataURL(file);
      });
      await new Promise<void>((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve();
        image.onerror = () => reject(new Error("Could not open image."));
        image.src = data;
      });
      if (version === readVersion.current) setPicture(data);
    } catch {
      if (version === readVersion.current)
        setError("We couldn’t open that image. Choose another file.");
    } finally {
      if (version === readVersion.current) setReading(false);
    }
  }

  return (
    <>
      <PageHeading eyebrow="YOUR ACCOUNT" title="Settings">
        Manage your profile and account details.
      </PageHeading>
      <form
        className="settings-form"
        onSubmit={async (event) => {
          event.preventDefault();
          setSaved(false);
          const parsed = fields.safeParse({ name, email: email.trim() });
          if (!parsed.success) {
            setError(parsed.error.issues[0].message);
            return;
          }
          setSaving(true);
          try {
            if (creators) {
              await creators.save({ name: parsed.data.name, picture });
              await cache.invalidateQueries({ queryKey: ["creator"] });
              await cache.invalidateQueries({ queryKey: ["own-creator"] });
            }
            save({ ...parsed.data, picture });
            setBaseline({ ...parsed.data, picture });
            setName(parsed.data.name);
            setEmail(parsed.data.email);
            setError("");
            setSaved(true);
          } catch {
            setError(
              "Your changes couldn’t be saved. Check your connection, try a smaller photo, or allow browser storage.",
            );
          } finally {
            setSaving(false);
          }
        }}
      >
        <section className="settings-section" aria-labelledby="profile-heading">
          <div>
            <h2 id="profile-heading">Profile</h2>
            <p className="muted small">
              How you appear in your learning space.
            </p>
          </div>
          <div className="settings-fields">
            <div className="picture-editor">
              <Avatar name={name} picture={picture} large />
              <div className="picture-actions">
                <input
                  id="profile-picture"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  aria-label="Upload profile picture"
                  aria-describedby="picture-help"
                  onChange={(event) => {
                    void choosePicture(event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
                {picture ? (
                  <button
                    type="button"
                    className="text-button"
                    disabled={reading}
                    onClick={() => {
                      ++readVersion.current;
                      setPicture(null);
                      setSaved(false);
                    }}
                  >
                    Remove photo
                  </button>
                ) : null}
                <p id="picture-help" className="muted small">
                  JPG, PNG, or WebP · Up to 1 MB
                </p>
              </div>
            </div>
            <label htmlFor="profile-name">
              Name
              <input
                id="profile-name"
                autoComplete="name"
                value={name}
                maxLength={80}
                required
                onChange={(event) => {
                  setName(event.target.value);
                  setSaved(false);
                }}
              />
            </label>
            <label htmlFor="profile-email">
              Email
              <input
                id="profile-email"
                type="email"
                readOnly={!!auth}
                autoComplete="email"
                value={email}
                maxLength={254}
                required
                placeholder="you@example.com"
                onChange={(event) => {
                  setEmail(event.target.value);
                  setSaved(false);
                }}
              />
            </label>
          </div>
        </section>
        <section
          className="settings-section"
          aria-labelledby="security-heading"
        >
          <div>
            <h2 id="security-heading">Password</h2>
          </div>
          <p className="muted">
            {auth ? (
              <Link to="/forgot-password">Reset your password by email</Link>
            ) : (
              "Password changes will be available when sign-in is added."
            )}
          </p>
        </section>
        <div className="settings-save">
          <p className="muted small">
            {auth
              ? "Your name and photo appear on your public creator profile. Your sign-in email is verified and cannot be edited here."
              : creators
                ? "Your name and photo appear on your public creator profile. Email stays in this browser."
                : "Your profile is saved in this browser."}
          </p>
          {error ? (
            <p role="alert" className="error-notice">
              {error}
            </p>
          ) : null}
          {saved ? (
            <p role="status" className="save-success">
              Profile saved.
            </p>
          ) : null}
          <button
            className="btn btn-primary"
            type="submit"
            disabled={!dirty || reading || saving}
          >
            {saving ? "Saving…" : reading ? "Reading photo…" : "Save changes"}
          </button>
        </div>
      </form>
    </>
  );
}
