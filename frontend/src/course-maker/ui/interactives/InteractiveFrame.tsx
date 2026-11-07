/** No network, forms or same-origin access: generated pages can only draw and respond. */
const policy =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'";

export function InteractiveFrame({
  html,
  title,
  className,
  decorative = false,
}: {
  html: string;
  title: string;
  className?: string;
  /** For miniature previews: not focusable and hidden from assistive technology. */
  decorative?: boolean;
}) {
  return (
    <iframe
      title={title}
      srcDoc={`<!doctype html><meta http-equiv="Content-Security-Policy" content="${policy}">${html}`}
      sandbox="allow-scripts"
      referrerPolicy="no-referrer"
      className={className}
      loading={decorative ? "lazy" : undefined}
      tabIndex={decorative ? -1 : undefined}
      aria-hidden={decorative ? true : undefined}
    />
  );
}
