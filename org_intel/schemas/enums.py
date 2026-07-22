"""Shared enumerations."""

from __future__ import annotations

from enum import Enum


class OrganizationType(str, Enum):
    CITY = "city"
    COUNTY = "county"
    WATER_DISTRICT = "water_district"
    UTILITY_AUTHORITY = "utility_authority"
    AIRPORT = "airport"
    PORT_AUTHORITY = "port_authority"
    TRANSIT_AGENCY = "transit_agency"
    SCHOOL_DISTRICT = "school_district"
    UNIVERSITY = "university"
    HOSPITAL = "hospital"
    STATE_AGENCY = "state_agency"
    HOUSING_AUTHORITY = "housing_authority"
    PARK_DISTRICT = "park_district"
    TRANSPORTATION_AUTHORITY = "transportation_authority"
    JOINT_POWERS_AUTHORITY = "joint_powers_authority"
    OTHER_PUBLIC = "other_public"
    UNKNOWN = "unknown"


class SourceRole(str, Enum):
    MAIN_WEBSITE = "main_official_website"
    BUDGET_PORTAL = "budget_portal"
    CIP_PORTAL = "capital_improvement_portal"
    LIVE_PROJECT_REGISTRY = "live_project_registry"
    BOARD_AGENDA = "board_or_council_agenda_system"
    LEGISTAR = "legistar"
    GRANICUS = "granicus"
    BOARDDOCS = "boarddocs"
    OPENGOV = "opengov"
    MUNICODE = "municode"
    PUBLIC_NOTICES = "public_notices"
    PROCUREMENT_PAGE = "procurement_page"
    BID_PORTAL = "bid_portal"
    DEMANDSTAR = "demandstar"
    BONFIRE = "bonfire"
    PLANETBIDS = "planetbids"
    IONWAVE = "ionwave"
    OPENGOV_PROCUREMENT = "opengov_procurement"
    BIDNET = "bidnet"
    STATE_PROCUREMENT = "state_procurement_portal"
    PUBLIC_ENGAGEMENT = "public_engagement_portal"
    PROJECT_WEBSITE = "project_specific_website"
    FINANCIAL_ARCHIVE = "financial_report_archive"
    BOND_DISCLOSURE = "bond_disclosure_site"
    MASTER_PLAN_ARCHIVE = "master_plan_archive"
    GIS_MAP = "gis_project_map"
    GRANT_PORTAL = "grant_portal"
    SRF_SOURCE = "state_revolving_fund_source"
    DOCUMENT_LIBRARY = "department_document_library"
    OTHER = "other"


class ContentRole(str, Enum):
    PROJECT_INVENTORY = "project_inventory"
    FINANCIAL = "financial"
    TECHNICAL_PLANNING = "technical_planning"
    APPROVAL = "approval"
    PROCUREMENT = "procurement"
    AWARD = "award"
    PUBLIC_ENGAGEMENT = "public_engagement"
    FINANCING = "financing"
    HISTORICAL = "historical"
    CONTACT = "contact"
    REGULATORY = "regulatory"


class OfficialStatus(str, Enum):
    OFFICIAL = "official"
    OFFICIAL_THIRD_PARTY_HOST = "official_third_party_host"
    SECONDARY = "secondary"


class SourceAccessMethod(str, Enum):
    HTML = "html"
    JAVASCRIPT = "javascript"
    PDF = "pdf"
    API = "api"
    SEARCH_PORTAL = "search_portal"
    SPREADSHEET = "spreadsheet"


class SourcePriority(str, Enum):
    ANCHOR = "anchor"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    BROKEN = "broken"
    UNKNOWN = "unknown"


class DocumentType(str, Enum):
    ADOPTED_BUDGET = "adopted_budget"
    PROPOSED_BUDGET = "proposed_budget"
    CAPITAL_IMPROVEMENT_PLAN = "capital_improvement_plan"
    CAPITAL_BUDGET = "capital_budget"
    CAPITAL_FACILITIES_PLAN = "capital_facilities_plan"
    MULTI_YEAR_FINANCIAL_PLAN = "multi_year_financial_plan"
    MASTER_PLAN = "master_plan"
    FACILITIES_PLAN = "facilities_plan"
    UTILITY_PLAN = "utility_plan"
    INTEGRATED_RESOURCE_PLAN = "integrated_resource_plan"
    WATER_SYSTEM_PLAN = "water_system_plan"
    WASTEWATER_FACILITIES_PLAN = "wastewater_facilities_plan"
    STORMWATER_PLAN = "stormwater_plan"
    AIRPORT_MASTER_PLAN = "airport_master_plan"
    TRANSPORTATION_PLAN = "transportation_plan"
    PARKS_MASTER_PLAN = "parks_master_plan"
    BOND_PROJECT_LIST = "bond_project_list"
    BALLOT_PROJECT_LIST = "ballot_project_list"
    OFFICIAL_STATEMENT = "official_statement"
    ACFR = "acfr"
    COUNCIL_PACKET = "council_or_board_packet"
    STAFF_REPORT = "staff_report"
    RESOLUTION = "resolution"
    ORDINANCE = "ordinance"
    PROFESSIONAL_SERVICES_AGREEMENT = "professional_services_agreement"
    CONSULTANT_AMENDMENT = "consultant_amendment"
    BID_SOLICITATION = "bid_solicitation"
    AWARD_NOTICE = "award_notice"
    PROJECT_PAGE = "project_page"
    PUBLIC_HEARING_PRESENTATION = "public_hearing_presentation"
    FEASIBILITY_STUDY = "feasibility_study"
    ENGINEERING_REPORT = "engineering_report"
    CIP_SPREADSHEET = "cip_spreadsheet"
    LIVE_REGISTRY = "live_registry"
    OTHER = "other"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ADOPTED = "adopted"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class RecordType(str, Enum):
    SPECIFIC_CAPITAL_PROJECT = "specific_capital_project"
    CAPITAL_PROGRAM = "capital_program"
    BUDGET_LINE_ITEM = "budget_line_item"
    MAJOR_EQUIPMENT_PURCHASE = "major_equipment_purchase"
    STUDY_OR_PLAN = "study_or_plan"
    DEBT_FINANCING_RECORD = "debt_financing_record"
    FUND_OR_TRANSFER = "fund_or_transfer"
    MAINTENANCE_PROGRAM = "maintenance_program"
    COMPLETED_HISTORICAL_PROJECT = "completed_historical_project"
    UNKNOWN = "unknown"


class ProjectPhase(str, Enum):
    CONCEPT_IDENTIFIED_NEED = "concept_identified_need"
    EARLY_PLANNING = "early_planning"
    FEASIBILITY_STUDY = "feasibility_study"
    MASTER_PLANNING = "master_planning"
    FUNDING_REQUESTED = "funding_requested"
    FUNDING_APPROVED = "funding_approved"
    CONSULTANT_SELECTION = "consultant_selection"
    PRELIMINARY_DESIGN = "preliminary_design"
    FINAL_DESIGN = "final_design"
    PERMITTING_ENVIRONMENTAL_REVIEW = "permitting_environmental_review"
    PRE_PROCUREMENT = "pre_procurement"
    RFQ_RFP_PREPARATION = "rfq_rfp_preparation"
    RFQ_RFP_ISSUED = "rfq_rfp_issued"
    BID_EVALUATION = "bid_evaluation"
    CONTRACT_AWARDED = "contract_awarded"
    CONSTRUCTION = "construction"
    COMMISSIONING = "commissioning"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ProcurementStatus(str, Enum):
    NO_PROCUREMENT_EVIDENCE = "no_procurement_evidence"
    INTERNAL_PLANNING = "internal_planning"
    CONSULTANT_SELECTION_EXPECTED = "consultant_selection_expected"
    SOLICITATION_IN_PREPARATION = "solicitation_in_preparation"
    RFQ_RFP_ACTIVE = "rfq_rfp_active"
    BID_ACTIVE = "bid_active"
    EVALUATION_UNDERWAY = "evaluation_underway"
    CONSULTANT_SELECTED = "consultant_selected"
    CONTRACTOR_SELECTED = "contractor_selected"
    CONTRACT_AWARDED = "contract_awarded"
    CONSTRUCTION_UNDERWAY = "construction_underway"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class PreRfqClassification(str, Enum):
    STRONG_PRE_RFQ = "strong_pre_rfq"
    POSSIBLE_PRE_RFQ = "possible_pre_rfq"
    MONITOR = "monitor"
    TOO_EARLY = "too_early"
    PROCUREMENT_ACTIVE = "procurement_active"
    CONSULTANT_SELECTED = "consultant_selected"
    CONTRACT_AWARDED = "contract_awarded"
    CONSTRUCTION_UNDERWAY = "construction_underway"
    COMPLETED = "completed"
    NOT_AN_EXTERNAL_OPPORTUNITY = "not_an_external_opportunity"
    INSUFFICIENT_INFORMATION = "insufficient_information"


# Alias used in opportunity assessments
OpportunityClass = PreRfqClassification


class FieldProvenance(str, Enum):
    STATED = "stated"
    CALCULATED = "calculated"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class MatchMethod(str, Enum):
    PROJECT_ID = "project_id"
    EXACT_NAME = "exact_name"
    FUZZY_NAME = "fuzzy_name"
    LOCATION = "location"
    SEMANTIC = "semantic"
    DEPARTMENT = "department"
    URL = "url"


class EmailStatus(str, Enum):
    CONFIRMED = "confirmed"
    PATTERN_INFERRED = "pattern_inferred"
    UNVERIFIED = "unverified"
    NONE = "none"


class EntityNodeType(str, Enum):
    ORGANIZATION = "organization"
    GOVERNING_BODY = "governing_body"
    DEPARTMENT = "department"
    DIVISION = "division"
    UTILITY = "utility"
    AUTHORITY = "authority"
    COMMITTEE = "committee"
    ADVISORY_BOARD = "advisory_board"
    PROCUREMENT_OFFICE = "procurement_office"
    RELATED_ENTITY = "related_entity"


class RelationshipType(str, Enum):
    REPORTS_TO = "reports_to"
    OWNED_BY = "owned_by"
    GOVERNED_BY = "governed_by"
    APPROVES = "approves"
    PROCURES_FOR = "procures_for"
    MANAGES_PROJECTS_FOR = "manages_projects_for"
    FUNDS = "funds"
    ADVISES = "advises"
    PUBLISHES_DOCUMENTS_FOR = "publishes_documents_for"
