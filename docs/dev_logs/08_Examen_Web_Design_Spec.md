# Examen Web — Design Spec

## Date: 11 June 2026 (Session 26 — rewritten around lean no-storage core)
## Supersedes: 08_Examen_Web_Design_Spec.md (10 June 2026), 08_Examen_Design_Spec.md (24 March 2026, desktop)

---

## 1. The core, in one line

> **Sequencing note (Session 26):** a **desktop** Examen is now the chosen *first* build — same analysis + report model, on the existing Python/Qt stack, no hosting/privacy/tax/operational burden, ~5–8 days vs ~10–15 for web. This web spec remains the definitive design for the *web* version, which becomes a **future layer on the same `shared/` engine** if public reach justifies it. The desktop build reuses everything below except the web front-end, hosting, and deployment. See `24_Phase_Plan.md` → "Examen — desktop first".

A web tool where a user pastes an invertebrate species list, resolves any name ambiguities through a matching wizard, and downloads a conservation/assemblage assessment report (Excel, PDF, Word). **Nothing is stored.** Every report is stamped with the date and the Codex version it was computed against.

This replaces the public Pantheon website for the thing most people actually use it for: paste a list, get the analysis, take the output away.

---

## 2. The decisive simplification — no storage

The hardest part of every earlier version of this spec was storing user data: accounts, privacy, GDPR, custody of confidential commercial species lists. **That entire problem is deleted by not storing anything.**

This is not a compromise — it is how Pantheon itself handles privacy. Pantheon's documented advice for keeping a list private is to paste it and *not save it*; saved lists become public to all Pantheon users. We adopt the discard path as the *only* path:

- The pasted list is held in memory for the duration of the request, used to compute the report, and discarded.
- It is never written to disk, never logged, never associated with a user.
- There are no user accounts, because there is nothing to log into.

**Reproducibility without storage.** The user's saved record *is the downloaded document*. Because every report carries the date and Codex version, it is a frozen, reproducible assessment held by the user — not by us. A figure queried in 2029 is defensible because the document says exactly which Codex produced it. This satisfies the "frozen assessment" requirement entirely on the client side.

**Private commercial history** (deep-frozen, re-runnable, linked site series) is *not* a web feature. It belongs to the desktop suite, where confidential survey data stays on the user's own machine. The web tool and the desktop tool share the same `shared/` analysis engine; they differ only in whether anything persists.

---

## 3. What the user does

1. **Paste** a species list — scientific names, one per line, **or** TVK codes (TVK paste skips matching, for large lists; Pantheon supports this and it is worth copying).
2. **Resolve** names through the matching wizard (§4) — greens confirmed, ambiguous names offer suggestions to click, unmatched names are flagged and excluded.
3. **Analyse** — the confirmed list runs through the `shared/` engine against current Codex + Pantheon ecology.
4. **Download** the report in Excel, PDF, and/or Word.

No login, no save, no account. Optionally, a **Donate** button (§6).

---

## 4. Species matching wizard — the main new build

This is the one substantial piece of net-new web work. Everything else is reuse.

Pantheon's model is the reference: paste names, each is checked against UKSI, matches turn green, non-unique matches show dictionary suggestions to pick from, no-match names get a red flag and are excluded from analysis.

| Layer | Source |
|---|---|
| Matching logic (name → TVK against UKSI, preferred-name resolution, fuzzy suggestions) | **Reused** from `shared/` / Observatum's existing import-wizard and bulk-resolution logic |
| Interface (paste box → per-name status list → click-to-resolve → confirmed list) | **Net-new web front-end** — Observatum's version is desktop Qt and does not transfer |

Behaviour:
- Accept names **or** TVKs; a TVK line is taken as already-resolved.
- Per-name status: confirmed (green), ambiguous (suggestions offered), unmatched (flagged, excluded).
- User clicks to resolve ambiguous names; unmatched names are reported so the user can correct spelling and re-paste.
- Aggregate/`s.l.`/`s.s.` handling consistent with how Codex/UKSI treat them.

This is what makes Examen Web "an application to build" rather than "a form on a script." It deserves its own build phase.

---

## 5. The report

Same analytical content the retired desktop Examen produced, rendered for download. Content is identical across all three formats; only the rendering differs.

**Content:**
- **SQI** (Species Quality Index) — overall and per biotope/habitat/SAT, with the small-sample warning (≤15 species) Pantheon uses.
- **Species appendix** — full list, taxonomically sorted, with conservation statuses across Codex tracks and SQS.
- **Key species table** — the notable species with their qualifying statuses/tiers.
- **Habitat / SAT / guild breakdowns** — assemblage composition.
- **Key species profiles** — the profile paragraphs from Codex `species_profiles` for the notable species (ecological context; the donor-differentiating content).
- **Stamp** — assessment date + Codex build version, on every output.

**Formats — build in order of value, each a shippable increment:**

| Order | Format | Role | Effort |
|---|---|---|---|
| 1 | **Excel** | data format — appendix + tables as real rows to sort/reuse | lowest; proves the pipeline |
| 2 | **PDF** | flagship printout — looks like a published report | highest; the document people attach |
| 3 | **Word** | editable — paste sections into own templates | middle |

They are three rendering paths from one set of computed results, not one job done three times.

---

## 6. Funding — donation model (retained)

There is genuine ongoing cost even with no storage: Codex needs periodic rebuilding (new JNCC spreadsheets, review imports), the software needs maintenance, and hosting is not free. A donation model funds that, honestly framed as "support the upkeep of a free tool replacing an abandoned one."

Crucially, **donations need no accounts**: a Donate button to a payment provider (Ko-fi / PayPal / Stripe payment link). No login, no donor database, no tiers. Keeps the funding model while keeping the zero-data-custody position.

---

## 7. Architecture

| Layer | Decision |
|---|---|
| Analysis engine | `shared/services/pantheon_analysis_service.py` + `CodexRepository` + `PantheonRepository` — reused unchanged where possible |
| Reference data | Read-only copies of codex.db + pantheon.db + UKSI name index on the server |
| Codex updates | Rebuilt locally, shipped to the server as a file (the file-sync model). Version from `build_log` stamped onto every report |
| Storage | **None** for user data. Only the static reference databases live server-side |
| Accounts / auth | None |

The `shared/` engine staying UI-agnostic means a desktop and a web front-end can both sit on it. Building the web tool does not burn the bridge to anything; it reuses the same core the suite already depends on.

---

## 8. Gating questions — RESOLVED (June 2026 research)

Both pre-build unknowns are now answered. Neither blocks the project.

### 8.1 Licensing — CLEAR ✅

All three data sources permit public, commercial-capable use with attribution:

- **UKSI** — **CC BY 4.0** (per the NHM/GBIF dataset, DOI 10.15468/rm6pm4, maintained by C. Raper). Permits share/adapt/redistribute for any purpose including commercial; sole condition is attribution. This was the one "could constrain the project" risk — it is resolved in our favour.
- **JNCC Conservation Designations** — Open Government Licence (free commercial use, attribution).
- **Pantheon ecology** — Open Government Licence.

**Obligation:** an attribution line on every report and an "about/data sources" page, e.g. *"Taxonomy from the UK Species Inventory (C. Raper, Natural History Museum), version [X], CC BY 4.0. Conservation designations from JNCC (OGL). Ecology from Pantheon (Natural England/CEH, OGL)."* Record which UKSI version each build used (dovetails with report version-stamping). Courtesy note to the UKSI manager (c.raper@nhm.ac.uk) before a commercial public launch is optional good practice, not a licence requirement. Data is provided "as-is" (no warranty) — attribute, don't guarantee.

### 8.2 Hosting — DECIDED: small always-on PaaS, ~£4–7/month

The app does real work in short bursts (match, analyse, render) then sits idle. Cost hinges on whether codex.db (~18 MB) + pantheon.db (~22 MB) + a UKSI name index fit comfortably in ~512 MB RAM — **measure before committing.**

| Option | Cost | Verdict |
|---|---|---|
| flauna.uk WordPress.com hosting | n/a | **Cannot host** — WordPress.com runs PHP, not a Python app. Domain still usable for an `examen.flauna.uk` subdomain pointed elsewhere. |
| Free PaaS tiers (Render/Fly/Koyeb/PythonAnywhere free) | £0 | Sleep on inactivity → 2–30s cold start while loading the databases. **Fine for development; poor for public launch** (bad first impression for someone awaiting a report). |
| **PythonAnywhere paid** | **~£4/mo** | Always-on, Python-native, easiest deploy (no containers). Best budget pick **if** the databases fit its constrained resources. |
| Small container PaaS (Render etc.) | ~£7/mo | The comfortable, no-surprises always-on option; deploys from git; headroom for document generation. |
| VPS (DigitalOcean/Hostinger) | ~£5–7/mo | Full control, full admin burden — more than wanted for a solo maintainer. |
| AWS Lambda (container) | ~£1/mo, £0 idle | Cheapest in theory, but AWS complexity + cold-start-while-loading-DBs is a poor fit here. |

**Recommendation:** develop on a free tier; launch on PythonAnywhere paid (~£4) or a small PaaS (~£7). Domain via an `examen.flauna.uk` subdomain (£0 extra).

### 8.3 Accounts & email — DECIDED: no accounts; optional mailing list only

The earlier "accounts to trace users / email updates" idea was evaluated and **rejected**, because accounts re-import the exact burden the no-storage core deleted — storing names/emails reactivates GDPR, creates a user database to secure, and requires building/maintaining auth — all for a mere mailing list. The two underlying wants are met more cheaply:

- **Sense of usage** → privacy-friendly analytics (Plausible) or server logs. No personal data, no GDPR.
- **Update announcements** → a plain opt-in **mailing list** (one email box → Brevo/Mailchimp). Email sending is free at this scale (Brevo 9,000/mo free; AWS SES £0.10/1,000). The provider handles unsubscribe/consent. One small, standard GDPR responsibility (the list) — not a bespoke accounts system.

The assessment path itself continues to store nothing.

### 8.4 Funding & tax — NOTED (confirm with accountant)

*Not tax advice — confirm with an accountant.* Donations to support a tool you maintain are generally **taxable income connected to your activity**, not tax-free gifts (you are not a registered charity). Relevant points for a UK self-employed sole trader:

- Reported on the Self Assessment already filed — no new registration likely needed.
- The **£1,000 trading/miscellaneous income allowance** may cover small donation income — but its interaction with *existing* self-employment needs checking (separate misc income vs. part of the trade).
- **Running costs are deductible** against donation income — £120 donations − £90 hosting = £30 net in question, very possibly within the allowance.
- Keep simple records of donations received and costs paid from day one.
- Platform (Ko-fi/PayPal/Stripe) is a fee choice, not a tax choice; none withholds tax for you. VAT almost certainly out of scope (genuine donations, below threshold).

**Action:** one question to the accountant — *"I take small donations to fund a free tool I maintain alongside my ecology self-employment; separate misc income under the trading allowance, or part of my trade?"* At coffee-fund scale this is a footnote, not a blocker.

### 8.5 Total running cost

| Item | Monthly |
|---|---|
| Hosting (always-on PaaS) | ~£4–7 |
| Email (mailing list, free tier) | £0 |
| Analytics (Plausible ~£7, or logs free) | £0–7 |
| Domain (examen.flauna.uk subdomain) | £0 |
| **Realistic total** | **~£4–14/month** |

The figure the donation model must cover — modest, within "a few supporters a year."

---

## 9. Build phasing (when Phase 3a starts)

| Step | Content |
|---|---|
| 0 | Gates cleared (§8): licensing CC BY/OGL, hosting decided, accounts declined. Remaining pre-build action: measure DB memory footprint to fix the hosting tier; one tax question to accountant |
| 1 | Stack decision; server skeleton wrapping the `shared/` engine |
| 2 | Paste → matching wizard → confirmed list (the main new build) |
| 3 | Analysis run + on-screen results |
| 4 | Excel report |
| 5 | PDF report |
| 6 | Word report |
| 7 | Donate button; styling; Codex-version stamping; small-sample warnings |
| 8 | Codex file-sync deployment process |

---

## 10. What changed from the previous spec

- **Storage removed entirely.** No accounts, no saved history, no privacy/GDPR surface, no two-tier model. The printout is the frozen record.
- **Private commercial history** reassigned to the desktop suite, where confidential data belongs.
- **Donation model retained** but simplified to accountless.
- **Species matching wizard** named as the principal new build.
- **Report** specified: SQI, species appendix, key species table, habitat/SAT/guild breakdowns, key species profiles — in Excel, then PDF, then Word.
- **Open questions resolved** (was: two unknowns). Licensing clear (UKSI CC BY 4.0; JNCC + Pantheon OGL); hosting decided (~£4–7/mo always-on PaaS); accounts declined in favour of an optional mailing list; tax noted (likely within the £1,000 trading allowance, confirm with accountant). Running cost ~£4–14/mo.

The project is **cleared to build** pending only: (a) measuring the reference-DB memory footprint to fix the hosting tier, (b) a stack decision, and (c) your go-ahead.

The result is a leaner, fully-formed project: most of it reuses the proven `shared/` engine; the genuinely new work is the matching wizard's web interface and the three report renderers.
