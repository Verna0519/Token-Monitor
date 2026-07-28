export const meta = {
  name: 'emit-coordinate',
  description: "Derive the person's capability COORDINATE (one 0-3 level per axis, or null when the evidence cannot place the axis) from locally-extracted signals — one agent per axis, each grounded in that axis's own rung rubric. Output feeds scripts/emit_coordinate.py; evidence and rationales stay on this machine.",
  phases: [
    { title: 'Assess', detail: 'one agent per axis judges the current level from local evidence + the axis rubric' },
  ],
}

// The 8 capability axes — must mirror config/personal-domains.yaml domains (and the dept map's axes.yaml).
const AXES = ['DESIGN', 'FRAMEWORK-SELECTION', 'CODING', 'TUNING', 'CONTEXT-ENGINEERING', 'EVAL', 'ADVISORY', 'CONTINUITY']

// args may arrive as a real object OR a JSON string — normalize. Paths default to repo-relative
// (run from the repo root); absolute overrides are runtime data for cross-cwd testing only.
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const rubricPath = A.rubric_path || 'config/personal-domains.yaml'
const signalsPath = A.signals_path || 'raw-sessions/capability-signals.json'

const LEVEL = {
  type: 'object',
  additionalProperties: false,
  required: ['axis', 'level', 'basis', 'rationale'],
  properties: {
    axis: { type: 'string' },
    level: {
      type: ['integer', 'null'],
      minimum: 0,
      maximum: 3,
      description: 'the 0-3 level the evidence DEMONSTRATES, or null when the evidence cannot place this axis',
    },
    basis: { type: 'string', description: 'evidence-strength summary: how many sessions/signals, at which tiers (intended/structural/actual)' },
    rationale: { type: 'string', description: 'two to four sentences grounding the level in the rubric observable_markers vs the observed evidence' },
  },
}

const results = await parallel(AXES.map(axis => () =>
  agent(
    'You are placing ONE axis of a person\'s capability COORDINATE on a learning map. This is neutral ' +
    'capability-positioning for growth coaching: a level is a POSITION on the axis, not a grade — no ranking, ' +
    'no absolute score. Everything you read and write stays on this person\'s own machine.\n\n' +
    'AXIS = ' + axis + '.\n\n' +
    'STEP 1 — read the rubric: open ' + rubricPath + ' and find domains.' + axis + '. Read its axis ' +
    'description and the full rung_rubric (levels 0,1,2,3: name, definition, observable_markers). Ground ' +
    'yourself in what each level looks like when actually OBSERVED.\n\n' +
    'STEP 2 — read the evidence: open ' + signalsPath + ' (a JSON array, one object per extracted session). ' +
    'For each session look ONLY at domain_signals.' + axis + ' (fields: present, signal_tier, evidence_refs). ' +
    'Ignore every other domain and ignore bias_flags (a separate channel).\n\n' +
    'STEP 3 — judge the CURRENT level this evidence DEMONSTRATES:\n' +
    '- Pick the highest rubric level whose definition/markers the observed behavior actually demonstrates. ' +
    'Be conservative: demonstrated, not aspired-to.\n' +
    '- Weigh signal_tier as evidence strength: actual (observed doing it) > structural (set up mechanisms ' +
    'for it) > intended (stated/planned it). Behavior supported ONLY by intended-tier evidence usually ' +
    'places one level below the described behavior, or null if nothing is demonstrated yet.\n' +
    '- level = null when the axis CANNOT be placed: present=false across all sessions, or evidence too thin ' +
    'to distinguish levels. NEVER map absence of evidence to level 0 — level 0 is a real, observed ' +
    'low-maturity behavior pattern, not "no data".\n' +
    '- level = 0 ONLY if the evidence actually shows the level-0 pattern.\n\n' +
    'Return axis (= "' + axis + '"), level (int 0-3 or null), basis, and a rationale grounded in the markers.\n\n' +
    'Scope guard (strict): read ONLY the two files named above. Do not open any other file, directory, or ' +
    'repository. Neutral vocabulary only (coordinate, axis, level, evidence, position).',
    { label: 'assess:' + axis, phase: 'Assess', effort: 'medium', schema: LEVEL }
  )
))

// Fail loudly on partial assessment: a dropped axis agent must not masquerade as an unplaced axis.
const got = results.filter(Boolean)
const returned = got.map(r => r.axis)
const missing = AXES.filter(a => !returned.includes(a))
const unknown = returned.filter(a => !AXES.includes(a))
const dup = returned.filter((a, i) => returned.indexOf(a) !== i)
if (missing.length || unknown.length || dup.length) {
  log('FAIL emit-coordinate axis coverage — missing: [' + missing.join(', ') + '] unknown: [' + unknown.join(', ') + '] duplicate: [' + dup.join(', ') + ']')
  throw new Error('emit-coordinate: per-axis results do not cover the axes exactly — re-run; do not hand-assemble a partial coordinate')
}
const placed = got.filter(r => r.level !== null).length
log('assessed 8 axes: ' + placed + ' placed, ' + (8 - placed) + ' unplaced (null)')
return { format: 'coordinate-assessment', results: got }
