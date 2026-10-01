# Discovery: finding and grounding sources

Before writing a single word of a plan, you need real identifiers and real
column names. Never invent them — Builder will fail or hallucinate a broken
workbook if the plan references something that doesn't exist.

## Which tool to reach for

| Situation | Tool |
|---|---|
| User names a specific thing ("the FUN.BIKES schema", "Plugs Example Data Model", "our sales workbook") | `search` with that term |
| User hasn't named a source at all ("build me a dashboard") | `list_documents({ collection: "recommendations" })` first — these are admin-curated, safe defaults |
| User references something they looked at recently ("that data model I had open earlier") | `list_documents({ collection: "recents" })` |
| You have a candidate's `inodeId`/`elementId` and need columns, types, or metrics | `describe` |
| You have two+ equally-named candidates | `search` again with `entityTypes` narrowed, then surface both to the user by name — never guess |

`search` and `describe` are the only sources of truth for identifiers. `list_documents`
is for browsing when there's no query term yet — don't use it as a substitute for
`search` once the user has named something specific.

## The describe step is not optional

`search` results give you enough to identify *which* table or data-model element
the user means, but not always the exact column names, types, or available metrics.
Before an element goes into a plan's Build Outline, you should have called `describe`
on it at least once in this conversation. This is what lets you write:

> A bar chart of `Revenue` by `Region`, using the `revenue` metric on the
> `Transactions` data-model element

...instead of vaguely gesturing at "sales by region."

For `datamodel-element` results, `search` returns both `inodeId` (the parent data
model) and `elementId`. You need both to call `describe(type: "datamodel-element",
dataModelId: inodeId, elementId: elementId)` — and you need both again if you list
that element in the plan's `sources` array (`{ kind: "datamodel-element", inodeId,
nodeId: elementId }`).

## Handling ambiguity

If `search` returns multiple plausible matches (two folders named "Sandbox," three
data models with "sales" in the name), do not pick one silently. Surface the
candidates by name — "I found two data models that might fit: **Sales Ops** and
**Sales Command Center** — which one?" — and wait for the user to choose. This is
cheaper than building the wrong plan and having Builder construct the wrong
workbook.

If the user gives you a Sigma URL (a `/b/<id>` link, or a folder URL with a
`urlId`), that's a direct identifier lookup, not a search term — but if you don't
have a URL-resolution tool available, fall back to asking the user for the name
instead of guessing from the slug.
