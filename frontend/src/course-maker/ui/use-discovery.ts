import { useQuery } from "@tanstack/react-query";
import { useApplication } from "./application-context";

export function useDiscovery(query?: string, enabled = true) {
  const api = useApplication().creators;
  return useQuery({
    queryKey: query ? ["public-discovery", query] : ["public-discovery"],
    enabled: !!api && enabled,
    queryFn: () => api!.discover(query),
  });
}
