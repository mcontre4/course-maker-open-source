import { createContext, useContext, useState, type ReactNode } from "react";
import {
  defaultProfile,
  type Profile,
  type ProfileStore,
} from "../application/profile";
import { useAuthentication } from "./authentication";

const ProfileContext = createContext<{
  profile: Profile;
  save: (profile: Profile) => void;
} | null>(null);

export function ProfileProvider({
  store,
  children,
}: {
  store?: ProfileStore;
  children: ReactNode;
}) {
  const [profile, setProfile] = useState(() => store?.load() ?? defaultProfile);
  function save(next: Profile) {
    store?.save(next);
    setProfile(next);
  }
  return (
    <ProfileContext.Provider value={{ profile, save }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const context = useContext(ProfileContext);
  const auth = useAuthentication();
  if (!context) throw new Error("Profile provider is missing.");
  if (auth) {
    const user = auth.session?.user;
    return {
      profile: user
        ? {
            name: user.first_name + " " + user.last_name,
            email: user.email,
            picture: null,
          }
        : defaultProfile,
      save: (_profile: Profile) => {
        /* Authenticated profiles persist through the creator port. */
      },
    };
  }
  return context;
}

export function Avatar({
  name,
  picture,
  large = false,
}: {
  name: string;
  picture: string | null;
  large?: boolean;
}) {
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  return (
    <span className={"avatar" + (large ? " avatar-large" : "")}>
      {picture ? (
        <img src={picture} alt="Profile picture" />
      ) : (
        <span aria-hidden="true">{initials || "M"}</span>
      )}
    </span>
  );
}
