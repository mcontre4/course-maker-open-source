export type Profile = Readonly<{
  name: string;
  email: string;
  picture: string | null;
}>;

export const defaultProfile: Profile = {
  name: "Learner",
  email: "",
  picture: null,
};

export interface ProfileStore {
  load(): Profile;
  save(profile: Profile): void;
}
