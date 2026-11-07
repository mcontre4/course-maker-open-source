/**
 * Course creation is hidden for now: everything is a lesson. The course code
 * stays in place; set VITE_COURSE_CREATION=true (the unit and e2e test setups
 * do) to bring the course entry points back.
 */
export const COURSE_CREATION_ENABLED =
  import.meta.env.VITE_COURSE_CREATION === "true";
