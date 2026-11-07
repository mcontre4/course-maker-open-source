import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useApplication } from "./application-context";
import { Avatar } from "./profile-context";
import type { Creator } from "../application/creators";
import { useAuthentication } from "./authentication";

export function CreatorAttribution({ creator }: { creator: Creator }) {
  return (
    <Link
      aria-label={"Created by " + creator.name}
      className="creator-link"
      to={"/creators/" + creator.id}
    >
      <Avatar name={creator.name} picture={creator.picture} />
      <span>
        <span className="muted small">Created by</span>
        <strong>{creator.name}</strong>
      </span>
    </Link>
  );
}
export function CreatorLink({ id }: { id?: string | null }) {
  const api = useApplication().creators;
  const query = useQuery({
    queryKey: ["creator", id],
    enabled: !!api && !!id,
    queryFn: () => api!.page(id!),
    retry: false,
  });
  if (!id || !api) return null;
  return (
    <CreatorAttribution
      creator={query.data?.creator ?? { id, name: "Creator", picture: null }}
    />
  );
}
export function useOwnCreator() {
  const api = useApplication().creators;
  const auth = useAuthentication();
  return useQuery({
    queryKey: ["own-creator"],
    enabled: !!api && (!auth || !!auth.session?.user),
    queryFn: () => api!.own(),
  });
}
