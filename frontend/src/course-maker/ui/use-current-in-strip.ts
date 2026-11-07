import { useEffect, useRef } from "react";

/**
 * On a phone these strips scroll sideways, and the current choice must stay in
 * them. `current` is the choice's identity, so the strip only moves when it changes.
 */
export function useCurrentInStrip(
  ariaCurrent: "page" | "step",
  current: string | undefined,
) {
  const strip = useRef<HTMLElement>(null);
  useEffect(() => {
    const nav = strip.current;
    const selected = nav?.querySelector(`[aria-current="${ariaCurrent}"]`);
    if (nav && selected)
      nav.scrollLeft +=
        selected.getBoundingClientRect().left -
        nav.getBoundingClientRect().left -
        16;
  }, [ariaCurrent, current]);
  return strip;
}
