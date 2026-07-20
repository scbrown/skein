# Entity & relationship taxonomy (aegis ontology)

Use these controlled vocabularies for node `type` and edge `relation`. Reusing the canonical terms
keeps facts attaching to existing entities instead of forking near-duplicates.

## Entity `type` values

**Infrastructure:** `LXCContainer`, `ProxmoxNode`, `BareMetalHost`, `SystemdService`,
`WebApplication`, `DatabaseService`, `ZFSDataset`, `ReverseProxyRoute`, `NetworkSegment`

**Agents & org:** `Rig`, `CrewMember`, `Polecat`, `Person`, `FamilyMember`, `GoogleAccount`

**Tools & artifacts:** `CLI`, `MCPServer`, `Plugin`, `Skill`, `Formula`, `GitRepo`, `GitCommit`,
`ConfigFile`, `Script`, `CronJob`, `AnsibleRole`, `DockerImage`

**Declared (IaC) — see "Declared vs observed" below:** `AnsibleGroup`, `TerraformResource`

**Knowledge & governance:** `Directive`, `Observation`, `DecisionRecord`, `DesignDoc`, `Bead`

**Media & domain:** `MediaLibrary`, `Movie`, `TVSeries`, `ThemePark`

> **If the right type genuinely doesn't exist: STOP and ask a human. Do not pick the closest.**
> (Corrected 2026-07-19, aegis-7kx4 — this note used to say "pick the closest and note the gap",
> which is wrong in the one case it governs. "Closest" for 30 terraform resources is `ConfigFile`,
> and that answer is not a near-miss — it silently files declared infrastructure as observed
> config, which is the exact merge the layer rule below exists to prevent. A noted gap in a
> description field is not a type; nothing queries it.)
>
> The escalate path is cheap and it works: an IaC ingest stopped at this gate, cost one
> round-trip, and got two correct types ruled in rather than two plausible wrong ones ingested.
> Quipu's schema proposal flow (`quipu_propose_schema_change`) is how the new class lands.

## Declared vs observed (the layer rule)

IaC says what infrastructure is **supposed** to be; the graph holds what it **is**. Two layers,
related by edges, **never merged**:

```
ct-243              member_of    games_api_servers      # observed host in a declared group
proxmox_lxc.quipu   provisions   ct-243                 # declared resource -> the thing it creates
```

`proxmox_lxc.quipu` and `ct-243` are NOT the same entity however similar the names look. The
entire value of ingesting IaC is that declared and observed can then **disagree** — merge them
and you have a graph that cannot represent drift, which is the only reason to ingest IaC at all.

Name an `AnsibleGroup` by its literal inventory group name and a `TerraformResource` by
`{resourceType}.{resourceName}` (the address terraform itself uses). Both carry `src=file:line`:
a declared node whose provenance you cannot cite is a claim, not a fact.

## Edge `relation` values

**Topology / deployment:** `runs_on`, `deployed_on`, `routes_to`, `connects_to`, `depends_on`,
`backs_up`, `monitors`

**Ownership / org:** `managed_by`, `owns`, `member_of`, `reports_to`, `manages`, `applies_to`

**Provenance / derivation:** `derived_from`, `was_derived_from`, `authored_by`, `committed_to`,
`modifies`, `implements`, `configured_in`, `triggered_by`

**Declared -> observed:** `provisions` (a declared IaC artifact creates a running thing —
never a substitute for merging the two nodes)

> Edge direction is `source <relation> target` (e.g. `${SEARCH_URL} runs_on tagi`;
> `mol-ontology-ingest authored_by obsidian`). Pick the direction that reads as a true sentence.

## Worked example (a closed incident bead → episode)

Source: a P0 about a stale service binary on a host.

```json
{
  "nodes": [
    {"name": "${SEARCH_URL}", "type": "WebApplication", "description": "bobbin FTS search, HTTP :3000"},
    {"name": "tagi", "type": "ProxmoxNode", "description": "Proxmox host running ${SEARCH_URL}"},
    {"name": "deploy.yml", "type": "Script", "description": "Forgejo deploy workflow for bobbin"}
  ],
  "edges": [
    {"source": "${SEARCH_URL}", "target": "tagi", "relation": "runs_on"},
    {"source": "deploy.yml", "target": "tagi", "relation": "deployed_on"}
  ]
}
```
