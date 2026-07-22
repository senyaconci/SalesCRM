"""End-to-end pipeline with checkpoints, resume, cost limits, and exports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from org_intel.config import RunConfig, Settings, merge_settings
from org_intel.contacts.contact_validator import strip_manufactured_emails
from org_intel.contacts.stakeholder_mapper import map_stakeholders
from org_intel.database import Database
from org_intel.discovery.canonical_identity import build_canonical_identity
from org_intel.discovery.department_discovery import discover_organization_map
from org_intel.discovery.document_inventory import build_document_inventory
from org_intel.discovery.financial_profile import build_financial_profile
from org_intel.discovery.source_discovery import discover_sources
from org_intel.exports.excel_exporter import export_excel_workbook
from org_intel.exports.json_exporter import export_json_bundle
from org_intel.exports.markdown_exporter import export_markdown_report
from org_intel.llm.base import LLMProvider
from org_intel.llm.router import CostLimitExceeded, LLMRouter, build_router
from org_intel.pipeline.state import RunState
from org_intel.procurement.award_search import search_awards
from org_intel.procurement.incumbent_analysis import build_incumbent_analysis
from org_intel.procurement.solicitation_search import search_solicitations
from org_intel.projects.anchor_selector import select_anchor
from org_intel.projects.candidate_detector import select_candidates
from org_intel.projects.consolidation import consolidate_many
from org_intel.projects.deduplication import dedupe_shallow, find_merge_candidates
from org_intel.projects.index_extractor import extract_project_index
from org_intel.projects.opportunity_classifier import assess_projects
from org_intel.projects.source_mapper import map_projects_to_sources
from org_intel.projects.targeted_extractor import enrich_projects
from org_intel.quality.audit import build_research_gaps
from org_intel.quality.confidence import score_project_confidence
from org_intel.quality.validation import build_validation_plan
from org_intel.refresh.incremental_refresh import compute_refresh_changes, refresh_documents
from org_intel.retrieval.cache import ContentCache
from org_intel.retrieval.html_fetcher import HtmlFetcher
from org_intel.retrieval.http_client import HttpClient
from org_intel.retrieval.robots_policy import RobotsPolicy
from org_intel.schemas.contact import StakeholderMap
from org_intel.schemas.document import DocumentInventory
from org_intel.schemas.organization import FinancialCapitalProfile, OrganizationIdentity, OrganizationRelationshipGraph
from org_intel.schemas.procurement import IncumbentVendorAnalysis
from org_intel.schemas.project import OpportunityAssessment, ProjectRecord, ProjectSourceLink, ShallowProjectIndexRecord
from org_intel.schemas.source import SourceRegistry
from org_intel.utils.ids import new_id
from org_intel.utils.io import atomic_write_json, ensure_dir, read_json
from org_intel.utils.logging import configure_logging, get_logger
from org_intel.utils.urls import normalize_url

logger = get_logger(__name__)

PHASES = [
    "canonical_identity",
    "organization_map",
    "source_discovery",
    "document_inventory",
    "anchor_selection",
    "project_index",
    "document_indexing",
    "project_source_matching",
    "project_extraction",
    "procurement_validation",
    "consolidation",
    "opportunity_assessment",
    "contacts",
    "validation_and_gaps",
    "export",
]


class PipelineOrchestrator:
    def __init__(
        self,
        settings: Settings,
        run: RunConfig,
        *,
        http: HttpClient | None = None,
        llm_provider: LLMProvider | None = None,
        run_id: str | None = None,
    ) -> None:
        self.run = run
        self.settings = merge_settings(settings, run)
        configure_logging(run.log_level or self.settings.log_level)
        self.output_dir = ensure_dir(run.output_dir)
        self.checkpoint_dir = ensure_dir(self.output_dir / "checkpoints")
        self.db_path = self.output_dir / "org_intel.db"
        self.db = Database(f"sqlite:///{self.db_path}")
        self.run_id = run_id or self._resolve_run_id()
        self.cache = ContentCache(self.db, self.settings.cache_dir)
        self.http = http or HttpClient(
            cache=self.cache,
            user_agent=self.settings.user_agent,
            timeout=self.settings.request_timeout_seconds,
            robots=RobotsPolicy(self.settings.user_agent, enabled=self.settings.respect_robots),
        )
        self.html = HtmlFetcher(self.http)
        self.router: LLMRouter = build_router(
            self.settings, self.db, self.run_id, provider=llm_provider
        )
        self.state = RunState()
        self.partial = False
        self.stop_reason: str | None = None

    def _resolve_run_id(self) -> str:
        manifest_path = self.output_dir / "run_manifest.json"
        if self.run.resume and manifest_path.exists():
            data = read_json(manifest_path)
            return data.get("run_id") or new_id("RUN")
        return new_id("RUN")

    def run_pipeline(self) -> dict[str, Any]:
        mode = self.run.mode
        logger.info("pipeline_start", run_id=self.run_id, mode=mode, org_url=self.run.org_url)

        if self.run.resume:
            self._load_checkpoints()
            self._verify_resume_compatibility()

        try:
            if mode in {"discover", "full", "refresh"}:
                self._phase_identity()
                self._phase_org_map()
                self._phase_sources()
                self._phase_documents()

            if mode == "refresh":
                self._phase_refresh()

            if mode in {"project-map", "full", "refresh", "deep-enrich"}:
                if not self.state.identity:
                    self._phase_identity()
                if not self.state.source_registry:
                    self._phase_sources()
                if not self.state.document_inventory:
                    self._phase_documents()
                self._phase_anchor()
                self._phase_project_index()

            if mode in {"full", "refresh", "deep-enrich"}:
                self._phase_document_indexing_and_mapping()
                self._phase_extraction()
                self._phase_procurement()
                self._phase_consolidation()
                self._phase_opportunities()
                self._phase_contacts()
                self._phase_validation_gaps()

            if mode == "discover":
                # still produce financial profile lightly
                if self.state.document_inventory and self.state.identity:
                    self.state.financial_profile = build_financial_profile(
                        self.state.identity,
                        self.state.document_inventory,
                        {},
                        self.html,
                    )
                self._phase_contacts_light()
                self._phase_validation_gaps()

        except CostLimitExceeded as exc:
            self.partial = True
            self.stop_reason = str(exc)
            logger.warning("cost_limit_reached", error=str(exc))
        except Exception:
            logger.exception("pipeline_failed")
            self._write_manifest(status="failed")
            raise

        artifacts = self._export()
        self._write_manifest(status="partial" if self.partial else "completed")
        logger.info("pipeline_complete", run_id=self.run_id, partial=self.partial)
        return artifacts

    # ---- phases ----

    def _phase_identity(self) -> None:
        if self._skip("canonical_identity") and self.state.identity:
            return
        if not self.run.org_url:
            raise ValueError("--org-url is required")
        identity = build_canonical_identity(
            self.run.org_url,
            self.html,
            org_name=self.run.org_name,
            org_type=self.run.org_type,
            router=self.router,
        )
        self.state.identity = identity
        self._save_phase("canonical_identity", identity)

    def _phase_org_map(self) -> None:
        if self._skip("organization_map") and self.state.org_graph:
            return
        assert self.state.identity
        graph = discover_organization_map(self.state.identity, self.html)
        self.state.org_graph = graph
        self._save_phase("organization_map", graph)

    def _phase_sources(self) -> None:
        if self._skip("source_discovery") and self.state.source_registry:
            return
        assert self.state.identity
        registry = discover_sources(
            self.state.identity,
            self.html,
            official_sources_only=self.settings.official_sources_only,
            include_third_party=self.settings.include_third_party_sources
            or not self.settings.official_sources_only,
            router=self.router,
            max_pages=min(30, self.settings.max_documents),
        )
        self.state.source_registry = registry
        self._save_phase("source_discovery", registry)

    def _phase_documents(self) -> None:
        if self._skip("document_inventory") and self.state.document_inventory:
            return
        assert self.state.identity and self.state.source_registry
        inventory = build_document_inventory(
            self.state.identity,
            self.state.source_registry,
            self.html,
            router=self.router,
            max_documents=self.settings.max_documents,
        )
        self.state.document_inventory = inventory
        self._save_phase("document_inventory", inventory)

    def _phase_anchor(self) -> None:
        if self._skip("anchor_selection") and self.state.anchor_selection:
            return
        assert self.state.document_inventory and self.state.source_registry
        self._inject_cip_search_document()
        selection = select_anchor(self.state.document_inventory, self.state.source_registry)
        payload = {
            "score": selection.score,
            "reason": selection.reason,
            "candidates": selection.candidates,
            "document": selection.document.model_dump(mode="json") if selection.document else None,
            "source": selection.source.model_dump(mode="json") if selection.source else None,
        }
        # ensure selected document is in inventory
        if selection.document:
            ids = {d.document_id for d in self.state.document_inventory.documents}
            if selection.document.document_id not in ids:
                self.state.document_inventory.documents.insert(0, selection.document)
        self.state.anchor_selection = payload
        self._save_phase("anchor_selection", payload)

    def _phase_project_index(self) -> None:
        if self._skip("project_index") and self.state.project_index:
            return
        assert self.state.identity
        doc_data = self.state.anchor_selection.get("document")
        if not doc_data:
            self.state.project_index = []
            self._save_phase("project_index", [])
            return
        from org_intel.schemas.document import DocumentRecord

        anchor = DocumentRecord.model_validate(doc_data)
        index = extract_project_index(self.state.identity.organization_id, anchor, self.http)
        index = dedupe_shallow(index)
        if self.run.mode == "deep-enrich" and self.run.project_id:
            index = [
                i
                for i in index
                if (i.project_id in self.run.project_id) or (i.record_id in self.run.project_id)
            ]
        else:
            index = select_candidates(
                index,
                include_completed=self.run.include_completed,
                min_project_value=self.run.min_project_value,
                categories=self.run.project_category or None,
            ) or index
        self.state.project_index = index
        self._save_phase("project_index", index)

    def _phase_document_indexing_and_mapping(self) -> None:
        if self._skip("project_source_matching") and self.state.project_source_map:
            # still need indexes for later phases if missing
            if self.state.page_indexes:
                return
        assert self.state.document_inventory
        links, indexes = map_projects_to_sources(
            self.state.project_index,
            self.state.document_inventory,
            self.http,
            max_documents=min(40, self.settings.max_documents),
            max_pages=self.settings.max_pages,
        )
        self.state.project_source_map = links
        self.state.page_indexes = indexes
        self._save_phase("document_indexing", {"indexed_documents": list(indexes.keys())})
        self._save_phase("project_source_matching", links)
        # financial profile after indexing
        if self.state.identity:
            self.state.financial_profile = build_financial_profile(
                self.state.identity,
                self.state.document_inventory,
                indexes,
                self.html,
            )
            self._save_phase("financial_profile", self.state.financial_profile)

    def _phase_extraction(self) -> None:
        if self._skip("project_extraction") and self.state.projects_full:
            return
        assert self.state.identity and self.state.document_inventory
        projects = enrich_projects(
            self.state.project_index,
            self.state.project_source_map,
            self.state.page_indexes,
            self.state.document_inventory,
            router=self.router,
            organization_id=self.state.identity.organization_id,
            include_completed=self.run.include_completed,
            min_project_value=self.run.min_project_value,
            project_ids=self.run.project_id or None,
            max_projects=min(250, self.settings.max_documents * 3),
        )
        projects = self._enrich_cip_detail_pages(projects)
        for p in projects:
            score_project_confidence(p)
        self.state.projects_full = projects
        self._save_phase("project_extraction", projects)

    def _inject_cip_search_document(self) -> None:
        """Ensure live CIP search portals are available as anchor candidates."""
        from org_intel.schemas.document import DocumentRecord
        from org_intel.schemas.enums import ContentRole, DocumentType

        assert self.state.document_inventory and self.state.source_registry
        existing = {d.url.rstrip("/") for d in self.state.document_inventory.documents}
        for source in self.state.source_registry.sources:
            url = (source.url or "").rstrip("/")
            if not url:
                continue
            if "project_search.php" in url or ("cipweb" in url and "display_project" not in url):
                # Normalize to the searchable CIP index endpoint when possible.
                if "project_search.php" not in url and "cipweb" in url:
                    continue
                if url in existing:
                    continue
                doc = DocumentRecord(
                    title=source.source_name or "CIP Project Search",
                    document_type=DocumentType.LIVE_REGISTRY,
                    url=source.url,
                    source_id=source.source_id,
                    publishing_entity=source.publishing_entity,
                    file_type="html",
                    likely_project_relevance=0.98,
                    likely_financial_relevance=0.7,
                    content_roles=[ContentRole.PROJECT_INVENTORY, ContentRole.FINANCIAL],
                    confidence=0.95,
                )
                self.state.document_inventory.documents.insert(0, doc)
                existing.add(url)
        # Also add canonical Columbia-style CIP search if /cip source exists.
        for source in self.state.source_registry.sources:
            if source.url and source.url.rstrip("/").endswith("/cip"):
                candidate = source.url.replace("/cip", "/webapps/cipweb/project_search.php")
                # Prefer absolute known pattern on same host
                from org_intel.utils.urls import domain_of

                host = domain_of(source.url)
                if host:
                    candidate = f"https://{host}/webapps/cipweb/project_search.php"
                if candidate.rstrip("/") not in existing:
                    doc = DocumentRecord(
                        title="Capital Improvement Projects (CIP) Search",
                        document_type=DocumentType.LIVE_REGISTRY,
                        url=candidate,
                        source_id=source.source_id,
                        publishing_entity=source.publishing_entity,
                        file_type="html",
                        likely_project_relevance=0.99,
                        likely_financial_relevance=0.75,
                        content_roles=[ContentRole.PROJECT_INVENTORY],
                        confidence=0.9,
                    )
                    self.state.document_inventory.documents.insert(0, doc)
                    existing.add(candidate.rstrip("/"))

    def _enrich_cip_detail_pages(self, projects: list[ProjectRecord]) -> list[ProjectRecord]:
        from org_intel.projects.cip_detail import enrich_from_cip_detail_html
        from org_intel.projects.phase import normalize_phase

        # Cap live detail fetches for affordability; prioritize non-terminal stages.
        terminal = {"cancelled", "closed", "in service", "completed"}
        ranked = sorted(
            projects,
            key=lambda p: (
                0
                if (p.published_status or "").lower().split()[0:1]
                and (p.published_status or "").lower().split()[0] not in terminal
                else 1,
                p.project_name,
            ),
        )
        fetched = 0
        max_fetch = min(80, self.settings.max_documents)
        for project in ranked:
            detail = None
            for link in project.source_links:
                pass
            # Prefer shallow index detail URL carried via evidence/source
            # Reconstruct from project_index match
            match = next(
                (
                    i
                    for i in self.state.project_index
                    if (i.project_id and i.project_id == project.project_id)
                    or i.project_name == project.project_name
                ),
                None,
            )
            if match and match.project_detail_url:
                detail = match.project_detail_url
            if not detail or "display_project.php" not in detail:
                continue
            if fetched >= max_fetch:
                break
            stage = (project.published_status or "").lower()
            if any(t in stage for t in terminal) and not self.run.include_completed:
                continue
            try:
                result = self.http.fetch(detail)
                project = enrich_from_cip_detail_html(project, result.text, detail)
                phase, inferred, evidence = normalize_phase(
                    project.published_status or project.phase_evidence or ""
                )
                if phase.value != "unknown":
                    project.normalized_phase = phase
                    project.phase_is_inferred = inferred
                    project.phase_evidence = evidence or project.phase_evidence
                fetched += 1
            except Exception:
                continue
        return ranked

    def _phase_procurement(self) -> None:
        if self._skip("procurement_validation") and self.state.solicitations is not None:
            if self.state.incumbent_analysis:
                return
        assert self.state.identity and self.state.document_inventory
        sols = search_solicitations(
            self.state.identity.organization_id,
            self.state.document_inventory,
            self.state.page_indexes,
            self.state.projects_full,
        )
        events = search_awards(
            self.state.identity.organization_id,
            self.state.document_inventory,
            self.state.page_indexes,
            self.state.projects_full,
        )
        # attach solicitation ids
        for sol in sols:
            for pid in sol.related_project_ids:
                for project in self.state.projects_full:
                    if project.project_id == pid or project.record_id == pid:
                        if sol.solicitation_number:
                            project.solicitation_ids.append(sol.solicitation_number)
        analysis = build_incumbent_analysis(
            self.state.identity.organization_id,
            self.state.projects_full,
            events,
        )
        self.state.solicitations = sols
        self.state.procurement_events = events
        self.state.incumbent_analysis = analysis
        self._save_phase(
            "procurement_validation",
            {
                "solicitations": [s.model_dump(mode="json") for s in sols],
                "events": [e.model_dump(mode="json") for e in events],
                "incumbents": analysis.model_dump(mode="json"),
            },
        )

    def _phase_consolidation(self) -> None:
        if self._skip("consolidation") and self.state.projects_full:
            # still run once unless forced
            if not self.run.force and self.db.get_checkpoint(self.run_id, "consolidation"):
                return
        self.state.projects_full = consolidate_many(self.state.projects_full)
        merges = find_merge_candidates(self.state.projects_full)
        self._save_phase(
            "consolidation",
            {
                "projects": [p.model_dump(mode="json") for p in self.state.projects_full],
                "merge_candidates": [m.model_dump(mode="json") for m in merges],
            },
        )

    def _phase_opportunities(self) -> None:
        if self._skip("opportunity_assessment") and self.state.opportunities:
            return
        opps = assess_projects(self.state.projects_full, router=self.router)
        self.state.opportunities = opps
        self._save_phase("opportunity_assessment", opps)

    def _phase_contacts(self) -> None:
        if self._skip("contacts") and self.state.contacts:
            return
        assert self.state.identity and self.state.org_graph
        contacts = map_stakeholders(
            self.state.identity,
            self.state.org_graph,
            self.html,
            self.state.projects_full,
        )
        contacts.contacts = strip_manufactured_emails(contacts.contacts)
        self.state.contacts = contacts
        self._save_phase("contacts", contacts)

    def _phase_contacts_light(self) -> None:
        if self.state.contacts or not self.state.identity or not self.state.org_graph:
            return
        self._phase_contacts()

    def _phase_validation_gaps(self) -> None:
        if self._skip("validation_and_gaps") and self.state.research_gaps:
            return
        assert self.state.identity
        self.state.validation_plan = build_validation_plan(
            self.state.projects_full, self.state.opportunities
        )
        self.state.research_gaps = build_research_gaps(
            self.state.identity,
            self.state.source_registry
            or SourceRegistry(organization_id=self.state.identity.organization_id),
            self.state.document_inventory
            or DocumentInventory(organization_id=self.state.identity.organization_id),
            self.state.financial_profile
            or FinancialCapitalProfile(organization_id=self.state.identity.organization_id),
            self.state.projects_full,
            self.state.opportunities,
            self.state.contacts
            or StakeholderMap(organization_id=self.state.identity.organization_id),
        )
        self._save_phase(
            "validation_and_gaps",
            {
                "validation_plan": [v.model_dump(mode="json") for v in self.state.validation_plan],
                "research_gaps": [g.model_dump(mode="json") for g in self.state.research_gaps],
            },
        )

    def _phase_refresh(self) -> None:
        if not self.state.document_inventory:
            return
        previous_projects = list(self.state.projects_full)
        changed, notes = refresh_documents(self.state.document_inventory, self.http)
        logger.info("refresh_documents", changed=len(changed), notes=notes[:5])
        # Force re-run of later phases for changed content
        for phase in (
            "anchor_selection",
            "project_index",
            "document_indexing",
            "project_source_matching",
            "project_extraction",
            "procurement_validation",
            "consolidation",
            "opportunity_assessment",
            "validation_and_gaps",
            "export",
        ):
            self.db.save_checkpoint(
                self.run_id,
                phase,
                None,
                organization_id=self.state.identity.organization_id if self.state.identity else None,
                status="stale",
            )
        # After later phases run, compute changes
        self._refresh_previous_projects = previous_projects  # type: ignore[attr-defined]

    def _export(self) -> dict[str, Any]:
        if self._skip("export") and (self.output_dir / "run_manifest.json").exists() and not self.run.force:
            # rebuild exports without research is still useful; always export
            pass

        # If refresh, compute change history
        prev = getattr(self, "_refresh_previous_projects", None)
        if prev is not None:
            self.state.change_history = compute_refresh_changes(prev, self.state.projects_full)

        artifacts = self._artifacts()
        export_json_bundle(self.output_dir, artifacts)
        export_markdown_report(self.output_dir, artifacts)
        export_excel_workbook(self.output_dir, artifacts)
        self._save_phase("export", {"output_dir": str(self.output_dir)})
        return artifacts

    def _artifacts(self) -> dict[str, Any]:
        return {
            "organization_profile": self.state.identity,
            "source_registry": self.state.source_registry,
            "document_inventory": self.state.document_inventory,
            "financial_capital_profile": self.state.financial_profile,
            "organization_relationships": self.state.org_graph,
            "project_index": self.state.project_index,
            "project_source_map": self.state.project_source_map,
            "projects_full": self.state.projects_full,
            "opportunities": self.state.opportunities,
            "incumbent_vendor_analysis": self.state.incumbent_analysis,
            "contacts": self.state.contacts,
            "validation_plan": self.state.validation_plan,
            "research_gaps": self.state.research_gaps,
            "change_history": self.state.change_history,
            "cost_ledger": self.db.cost_entries(self.run_id),
            "solicitations": self.state.solicitations,
            "anchor_selection": self.state.anchor_selection,
            "run_manifest": self._manifest_dict(status="partial" if self.partial else "completed"),
        }

    # ---- checkpoint helpers ----

    def _skip(self, phase: str) -> bool:
        if self.run.force:
            return False
        if not self.run.resume:
            return False
        return self.db.get_checkpoint(self.run_id, phase) is not None

    def _save_phase(self, phase: str, payload: Any) -> None:
        path = self.checkpoint_dir / f"{phase}.json"
        atomic_write_json(path, _serialize(payload))
        org_id = self.state.identity.organization_id if self.state.identity else None
        self.db.save_checkpoint(self.run_id, phase, path, organization_id=org_id)
        logger.info("checkpoint_saved", phase=phase, path=str(path))

    def _load_checkpoints(self) -> None:
        loaders = {
            "canonical_identity": ("identity", OrganizationIdentity),
            "organization_map": ("org_graph", OrganizationRelationshipGraph),
            "source_discovery": ("source_registry", SourceRegistry),
            "document_inventory": ("document_inventory", DocumentInventory),
            "financial_profile": ("financial_profile", FinancialCapitalProfile),
            "contacts": ("contacts", StakeholderMap),
            "incumbent_vendor_analysis": ("incumbent_analysis", IncumbentVendorAnalysis),
        }
        for phase, (attr, model) in loaders.items():
            data = self.db.load_checkpoint_payload(self.run_id, phase)
            if data:
                setattr(self.state, attr, model.model_validate(data))

        data = self.db.load_checkpoint_payload(self.run_id, "anchor_selection")
        if data:
            self.state.anchor_selection = data

        data = self.db.load_checkpoint_payload(self.run_id, "project_index")
        if data:
            self.state.project_index = [ShallowProjectIndexRecord.model_validate(x) for x in data]

        data = self.db.load_checkpoint_payload(self.run_id, "project_source_matching")
        if data:
            self.state.project_source_map = [ProjectSourceLink.model_validate(x) for x in data]

        data = self.db.load_checkpoint_payload(self.run_id, "project_extraction")
        if data:
            self.state.projects_full = [ProjectRecord.model_validate(x) for x in data]

        data = self.db.load_checkpoint_payload(self.run_id, "opportunity_assessment")
        if data:
            self.state.opportunities = [OpportunityAssessment.model_validate(x) for x in data]

        data = self.db.load_checkpoint_payload(self.run_id, "procurement_validation")
        if data and isinstance(data, dict):
            from org_intel.schemas.procurement import SolicitationRecord, ProcurementEvent

            self.state.solicitations = [
                SolicitationRecord.model_validate(x) for x in data.get("solicitations") or []
            ]
            self.state.procurement_events = [
                ProcurementEvent.model_validate(x) for x in data.get("events") or []
            ]
            if data.get("incumbents"):
                self.state.incumbent_analysis = IncumbentVendorAnalysis.model_validate(
                    data["incumbents"]
                )

        data = self.db.load_checkpoint_payload(self.run_id, "validation_and_gaps")
        if data and isinstance(data, dict):
            from org_intel.schemas.evidence import ResearchGap, ValidationQuestion

            self.state.validation_plan = [
                ValidationQuestion.model_validate(x) for x in data.get("validation_plan") or []
            ]
            self.state.research_gaps = [
                ResearchGap.model_validate(x) for x in data.get("research_gaps") or []
            ]

    def _verify_resume_compatibility(self) -> None:
        manifest_path = self.output_dir / "run_manifest.json"
        if not manifest_path.exists():
            return
        prior = read_json(manifest_path)
        prior_url = normalize_url(prior.get("org_url") or "")
        current_url = normalize_url(self.run.org_url or prior_url)
        if prior_url and current_url and prior_url != current_url:
            raise RuntimeError(
                f"Resume organization URL mismatch: prior={prior_url} current={current_url}"
            )
        if self.state.identity and self.run.org_name:
            # soft check
            if self.run.org_name.lower() not in self.state.identity.canonical_name.lower():
                self.state.identity.ambiguity_notes.append(
                    f"Resume supplied org-name '{self.run.org_name}' differs from "
                    f"checkpoint identity '{self.state.identity.canonical_name}'."
                )

    def _manifest_dict(self, status: str) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "org_url": self.run.org_url,
            "organization_id": self.state.identity.organization_id if self.state.identity else None,
            "canonical_name": self.state.identity.canonical_name if self.state.identity else None,
            "mode": self.run.mode,
            "output_dir": str(self.output_dir),
            "status": status,
            "partial": self.partial,
            "stop_reason": self.stop_reason,
            "completed_phases": sorted(self.db.completed_phases(self.run_id)),
            "total_cost_usd": self.db.total_cost(self.run_id),
            "max_cost_usd": self.settings.max_cost_usd,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "config": {
                "official_sources_only": self.settings.official_sources_only,
                "max_documents": self.settings.max_documents,
                "max_pages": self.settings.max_pages,
                "include_completed": self.run.include_completed,
            },
        }

    def _write_manifest(self, status: str) -> None:
        atomic_write_json(self.output_dir / "run_manifest.json", self._manifest_dict(status))


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value
