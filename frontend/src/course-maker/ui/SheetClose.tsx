/** Closes the menu it sits in. Only phones show it, where the menu is a bottom sheet. */
export function SheetClose({ label }: { label: string }) {
  return (
    <button
      type="button"
      className="sheet-close"
      aria-label={label}
      onClick={(event) => {
        const menu = event.currentTarget.closest("details");
        if (!menu) return;
        menu.open = false;
        menu.querySelector("summary")?.focus();
      }}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m6 6 12 12M18 6 6 18" />
      </svg>
    </button>
  );
}
