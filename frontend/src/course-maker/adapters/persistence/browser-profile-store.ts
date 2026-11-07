import { z } from "zod";
import {
  defaultProfile,
  type Profile,
  type ProfileStore,
} from "../../application/profile";
import type { KeyValueStorage } from "./browser-course-repository";

const profileSchema = z.object({
  version: z.literal(1),
  name: z.string().trim().min(1).max(80),
  email: z.union([z.literal(""), z.email().max(254)]),
  picture: z
    .string()
    .max(1400000)
    .regex(/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/)
    .nullable(),
});

export class BrowserProfileStore implements ProfileStore {
  constructor(private readonly storage: KeyValueStorage) {}

  load(): Profile {
    try {
      const raw = this.storage.getItem("course-maker:profile:v1");
      const result = profileSchema.safeParse(raw ? JSON.parse(raw) : null);
      return result.success
        ? {
            name: result.data.name,
            email: result.data.email,
            picture: result.data.picture,
          }
        : defaultProfile;
    } catch {
      return defaultProfile;
    }
  }

  save(profile: Profile): void {
    const data = profileSchema.parse({ ...profile, version: 1 });
    this.storage.setItem("course-maker:profile:v1", JSON.stringify(data));
  }
}
