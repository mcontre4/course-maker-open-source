# Drafts and workspace

Course and standalone lesson details can be saved without requesting an AI outline.
`Save as draft` stays on the details step, switches to a permanent edit URL on the
first save, and becomes disabled until the details change. Continuing to the
syllabus or outline saves changed details before starting generation. Typing alone
does not save content. Failed saves keep the form values available for retry.

The workspace at `/workspace` includes both courses and standalone lessons, grouped
into Drafts and Finished. Status, content type, and text search combine, and filters
are preserved in the URL. Continue opens details for a draft without an outline,
or the existing studio once its outline exists. The studio restores saved work
and conversation without starting another generation on revisit.

Finished uses the product's existing milestones: an approved course syllabus
(`ready`), or completed lesson animation source (`animation_ready`). The stage
label makes that milestone explicit. It does not indicate a rendered video or
publication; the application has no publishing service or published state yet.

## Backend

Course draft creation and updates reuse the existing POST and PUT course use
cases. Lesson detail updates use `PUT /api/v1/lessons/{id}` with
`{title, description, minutes, expectedRevision}`. A single-execute application
service checks ownership and revision under the operation's row lock, invokes
the domain behavior, and commits through the unit-of-work port. Stale updates
return 409; other owners receive 404. Details with an existing generated outline
are refined in the studio instead, preserving the outline and media invariants.
The aggregate payload already persists the brief, so no migration is required.
Existing lesson browser-cookie ownership rules still apply.

## Verification — October 29, 2026

- Backend: all 416 unit and integration tests passed; inner-layer unit coverage
  was 97.28%. Ruff, mypy, Tach, and the hexagonal boundary checker passed.
- Frontend: production build, architecture checks, and the UI suite passed.
  Regression coverage includes explicit saves without generation, same-ID
  resaves, restore after remount, combined workspace filters, failed-save retry,
  and a course update body that excludes the URL identifier.
- Browser: saved and resaved a one-minute rainbow lesson, reloaded its details,
  continued with Fast mode, and restored its generated three-beat outline.
  Saved and resaved a one-hour pencil-shading course, reopened it from the
  workspace, continued with Fast mode, restored the four-lesson syllabus, and
  approved it. Confirmed the workspace then showed the lesson in Drafts and
  the course in Finished, with the Finished filter excluding the draft.
- Both live runs persisted `openai/gpt-6-luna` as the model. Verification used an
  isolated migrated local MySQL database and the existing configured providers.
  Media rendering and publication were outside this draft-persistence change.
