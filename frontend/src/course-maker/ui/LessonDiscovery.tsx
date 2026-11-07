import { useDiscovery } from "./use-discovery";
import { QueryStatus } from "./components";
import { LessonGrid } from "./explore";

export function LessonDiscovery({ limit }: { limit?: number } = {}) {
  const discovery = useDiscovery();
  if (!discovery.data && !discovery.isFetching && !discovery.error) return null;
  return (
    <section
      aria-labelledby="lesson-discovery-title"
      className="lesson-discovery explore-shelf"
    >
      <div className="explore-shelf-heading">
        <span
          className="explore-shelf-badge"
          data-tone="apricot"
          aria-hidden="true"
        >
          ✦
        </span>
        <div>
          <h2 id="lesson-discovery-title">Newest lessons</h2>
          <p className="muted">Short videos you can watch right now.</p>
        </div>
      </div>
      {((discovery.isFetching && !discovery.data) || discovery.error) && (
        <QueryStatus
          pending={discovery.isFetching && !discovery.data}
          error={discovery.error}
          retry={() => void discovery.refetch()}
        />
      )}
      {discovery.data?.lessons.length ? (
        <LessonGrid
          layout={limit ? "shelf" : "list"}
          lessons={
            limit
              ? discovery.data.lessons.slice(0, limit)
              : discovery.data.lessons
          }
        />
      ) : null}
      {discovery.data?.lessons.length === 0 && (
        <p className="discovery-empty muted">
          No public lessons yet. Lessons that creators publish show up here.
        </p>
      )}
    </section>
  );
}
