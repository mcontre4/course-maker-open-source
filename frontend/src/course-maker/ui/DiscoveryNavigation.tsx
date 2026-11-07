import { useEffect, useId, useRef, useState } from "react";
import { flushSync } from "react-dom";
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { useContentSearch } from "./use-content-search";
import { searchResultsUrl } from "./course-search";
import { courseTopics, subtopicPath, topicPath } from "./course-catalog";
import { Thumbnail } from "./components";
import { COURSE_CREATION_ENABLED } from "./feature-flags";
import { SheetClose } from "./SheetClose";

export function ExploreNavigation() {
  const disclosure = useRef<HTMLDetailsElement>(null);
  const { pathname, key } = useLocation();
  useEffect(() => {
    if (disclosure.current) disclosure.current.open = false;
  }, [key]);
  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        disclosure.current &&
        !disclosure.current.contains(event.target)
      ) {
        disclosure.current.open = false;
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);
  return (
    <details
      className="explore-navigation"
      ref={disclosure}
      onKeyDown={(event) => {
        if (event.key === "Escape" && disclosure.current) {
          disclosure.current.open = false;
          disclosure.current.querySelector("summary")?.focus();
        }
      }}
      onBlur={(event) => {
        // Safari touch blurs the summary without focusing the tapped link.
        // Keep it visible until click; outside pointers are handled above.
        if (
          event.relatedTarget &&
          !event.currentTarget.contains(event.relatedTarget)
        )
          event.currentTarget.open = false;
      }}
    >
      <summary
        tabIndex={0}
        data-current={pathname.startsWith("/explore") || undefined}
      >
        <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="8.5" />
          <path d="m15.5 8.5-2 5-5 2 2-5z" />
        </svg>
        Explore
        <span className="chevron" aria-hidden="true" />
      </summary>
      <div
        className="explore-panel"
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a") && disclosure.current)
            disclosure.current.open = false;
        }}
      >
        <SheetClose label="Close Explore menu" />
        <div className="explore-heading">
          <strong>
            {COURSE_CREATION_ENABLED
              ? "Browse courses by topic"
              : "Browse lessons by topic"}
          </strong>
          <p className="muted small">
            {COURSE_CREATION_ENABLED
              ? "Pick a subject to see published courses about it."
              : "Pick a subject to see published lessons about it."}
          </p>
          <Link to="/explore">
            {COURSE_CREATION_ENABLED
              ? "View all courses →"
              : "View all lessons →"}
          </Link>
        </div>
        <div className="explore-topics">
          {courseTopics.map((topic) => (
            <div key={topic.title}>
              <Link className="explore-topic-title" to={topicPath(topic)}>
                <span
                  className="explore-topic-badge"
                  data-tone={topic.color}
                  aria-hidden="true"
                >
                  {topic.symbol}
                </span>
                {topic.title}
              </Link>
              <div className="explore-subtopics">
                {topic.subtopics.map((subtopic) => (
                  <Link key={subtopic} to={subtopicPath(topic, subtopic)}>
                    {subtopic}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}

export function CourseSearch() {
  const [params] = useSearchParams();
  const location = useLocation();
  return (
    <SearchInput key={location.key} initialValue={params.get("q") ?? ""} />
  );
}

function SearchInput({ initialValue }: { initialValue: string }) {
  const navigate = useNavigate();
  const [value, setValue] = useState(initialValue);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<string | null>(null);
  // Phones search on a full screen of its own; wider screens never leave this false.
  const [expanded, setExpanded] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const search = useContentSearch(value);
  const suggestions = search.matches.slice(0, 5);
  const activeIndex = suggestions.findIndex(
    (suggestion) => suggestion.id === active,
  );
  const visible = open && Boolean(value.trim());
  const openFullScreen = () => {
    // iOS only raises the keyboard for a focus made during the tap itself.
    flushSync(() => {
      setExpanded(true);
      setOpen(true);
    });
    input.current?.focus();
  };
  const closeFullScreen = () => {
    flushSync(() => {
      setExpanded(false);
      setOpen(false);
      setActive(null);
    });
    form.current?.querySelector<HTMLElement>(".course-search-open")?.focus();
  };
  const activeId = suggestions[activeIndex]
    ? `${listId}-${suggestions[activeIndex].id}`
    : undefined;
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !form.current?.contains(event.target)
      ) {
        setOpen(false);
        setActive(null);
      }
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);
  useEffect(() => {
    if (visible && activeId) {
      document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" });
    }
  }, [activeId, visible]);
  return (
    <form
      ref={form}
      className="course-search"
      role="search"
      data-expanded={expanded}
      onBlur={(event) => {
        // Safari touch blurs the field without focusing the tapped suggestion,
        // and dismissing the keyboard must leave the suggestions readable.
        if (
          event.relatedTarget &&
          !event.currentTarget.contains(event.relatedTarget)
        ) {
          setOpen(false);
          setActive(null);
        }
      }}
      onSubmit={(event) => {
        event.preventDefault();
        setOpen(false);
        navigate(searchResultsUrl(value));
      }}
    >
      <button
        type="button"
        className="course-search-open"
        aria-label="Open search"
        onClick={openFullScreen}
      >
        <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m16 16 5 5" />
        </svg>
        <span aria-hidden="true">Search</span>
      </button>
      <input
        ref={input}
        type="search"
        role="combobox"
        enterKeyHint="search"
        name="q"
        aria-label={
          COURSE_CREATION_ENABLED
            ? "Search courses and lessons"
            : "Search lessons"
        }
        aria-autocomplete="list"
        aria-expanded={visible}
        aria-controls={visible ? listId : undefined}
        aria-activedescendant={visible ? activeId : undefined}
        autoComplete="off"
        placeholder={
          COURSE_CREATION_ENABLED
            ? "Search courses or lessons"
            : "Search lessons"
        }
        maxLength={200}
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          setOpen(true);
          setActive(null);
        }}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.nativeEvent.isComposing) {
            if (event.key === "Enter") event.preventDefault();
            return;
          }
          if (event.key === "Escape") {
            event.preventDefault();
            if (expanded) closeFullScreen();
            setOpen(false);
            setActive(null);
          } else if (
            (event.key === "ArrowDown" || event.key === "ArrowUp") &&
            suggestions.length &&
            value.trim()
          ) {
            event.preventDefault();
            setOpen(true);
            const nextIndex =
              event.key === "ArrowDown"
                ? (activeIndex + 1) % suggestions.length
                : (activeIndex <= 0 ? suggestions.length : activeIndex) - 1;
            setActive(suggestions[nextIndex].id);
          } else if (
            event.key === "Enter" &&
            visible &&
            suggestions[activeIndex]
          ) {
            event.preventDefault();
            setOpen(false);
            navigate(suggestions[activeIndex].href);
          }
        }}
      />
      <button type="submit" aria-label="Search">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          aria-hidden="true"
        >
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m16 16 5 5" />
        </svg>
      </button>
      {expanded ? (
        <button
          type="button"
          className="course-search-cancel"
          onClick={closeFullScreen}
        >
          Cancel
        </button>
      ) : null}
      {expanded && !value.trim() ? (
        <nav className="search-topics" aria-label="Browse by topic">
          <p className="muted small">Or browse a topic</p>
          {courseTopics.map((topic) => (
            <Link key={topic.slug} to={topicPath(topic)}>
              <span
                className="explore-topic-badge"
                data-tone={topic.color}
                aria-hidden="true"
              >
                {topic.symbol}
              </span>
              {topic.title}
            </Link>
          ))}
        </nav>
      ) : null}
      {visible ? (
        <div className="search-dropdown">
          <p className="search-feedback" role="status">
            {search.pending
              ? COURSE_CREATION_ENABLED
                ? "Searching courses and lessons…"
                : "Searching lessons…"
              : search.failed
                ? "Some results are unavailable. Please retry."
                : suggestions.length
                  ? COURSE_CREATION_ENABLED
                    ? "Suggested courses and lessons"
                    : "Suggested lessons"
                  : COURSE_CREATION_ENABLED
                    ? "No courses or lessons found. Try another title."
                    : "No lessons found. Try another title."}
          </p>
          {search.failed ? (
            <button
              type="button"
              className="search-retry"
              onClick={() => {
                search.retry();
              }}
            >
              Retry search
            </button>
          ) : null}
          <div
            id={listId}
            role="listbox"
            aria-label={
              COURSE_CREATION_ENABLED
                ? "Course and lesson suggestions"
                : "Lesson suggestions"
            }
          >
            {suggestions.map((suggestion) => (
              <Link
                key={suggestion.id}
                id={`${listId}-${suggestion.id}`}
                role="option"
                aria-selected={active === suggestion.id}
                tabIndex={-1}
                to={suggestion.href}
                className="search-suggestion"
                onPointerMove={() => setActive(suggestion.id)}
                onClick={() => setOpen(false)}
              >
                <span className="search-suggestion-art" aria-hidden="true">
                  <Thumbnail
                    name={suggestion.image}
                    variant={suggestion.kind}
                  />
                </span>
                <span className="search-suggestion-copy">
                  <strong>{suggestion.title}</strong>
                  <span>{suggestion.detail}</span>
                </span>
              </Link>
            ))}
          </div>
          <Link
            className="search-view-all"
            to={searchResultsUrl(value)}
            onClick={() => setOpen(false)}
          >
            View all results for “{value.trim()}” →
          </Link>
        </div>
      ) : null}
    </form>
  );
}
