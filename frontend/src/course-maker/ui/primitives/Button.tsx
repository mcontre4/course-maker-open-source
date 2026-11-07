import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary";
};

export function Button({
  children,
  variant = "primary",
  type = "button",
  className = "",
  ...props
}: Props) {
  return (
    <button
      {...props}
      className={`btn btn-${variant} ${className}`.trim()}
      type={type}
    >
      {children}
    </button>
  );
}
