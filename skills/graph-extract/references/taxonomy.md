# Entity & relationship taxonomy (aegis ontology)

Use these controlled vocabularies for node `type` and edge `relation`. Reusing the canonical terms
keeps facts attaching to existing entities instead of forking near-duplicates.

## Entity `type` values

**Infrastructure:** `LXCContainer`, `ProxmoxNode`, `BareMetalHost`, `SystemdService`,
`WebApplication`, `DatabaseService`, `ZFSDataset`, `ReverseProxyRoute`, `NetworkSegment`

**Agents & org:** `Rig`, `CrewMember`, `Polecat`, `Person`, `FamilyMember`, `GoogleAccount`

**Tools & artifacts:** `CLI`, `MCPServer`, `Plugin`, `Skill`, `Formula`, `GitRepo`, `GitCommit`,
`ConfigFile`, `Script`, `CronJob`, `AnsibleRole`, `DockerImage`

**Knowledge & governance:** `Directive`, `Observation`, `DecisionRecord`, `DesignDoc`, `Bead`

**Media & domain:** `MediaLibrary`, `Movie`, `TVSeries`, `ThemePark`

> If the right type genuinely doesn't exist, pick the closest and note the gap — Quipu has a schema
> proposal flow (`quipu_propose_schema_change`) for adding new classes deliberately, rather than
> inventing ad-hoc types inline.

## Edge `relation` values

**Topology / deployment:** `runs_on`, `deployed_on`, `routes_to`, `connects_to`, `depends_on`,
`backs_up`, `monitors`

**Ownership / org:** `managed_by`, `owns`, `member_of`, `reports_to`, `manages`, `applies_to`

**Provenance / derivation:** `derived_from`, `was_derived_from`, `authored_by`, `committed_to`,
`modifies`, `implements`, `configured_in`, `triggered_by`

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
