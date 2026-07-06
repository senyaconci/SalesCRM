/**
 * Human-readable labels and badge color classes for the domain enums.
 * Kept in one place so every screen renders statuses/stages consistently.
 */

export type BadgeTone =
  | "gray"
  | "blue"
  | "green"
  | "amber"
  | "red"
  | "purple"
  | "teal"
  | "slate";

export const badgeToneClass: Record<BadgeTone, string> = {
  gray: "bg-gray-100 text-gray-700 ring-gray-200",
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  blue: "bg-blue-100 text-blue-700 ring-blue-200",
  green: "bg-green-100 text-green-700 ring-green-200",
  amber: "bg-amber-100 text-amber-800 ring-amber-200",
  red: "bg-red-100 text-red-700 ring-red-200",
  purple: "bg-purple-100 text-purple-700 ring-purple-200",
  teal: "bg-teal-100 text-teal-700 ring-teal-200",
};

function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export const projectStatusLabel: Record<string, string> = {
  NEW: "New",
  ASSIGNED: "Assigned",
  OUTREACH_STARTED: "Outreach Started",
  CONTACTED: "Contacted",
  VALIDATING: "Validating",
  VALIDATED_RELEVANT: "Validated — Relevant",
  VALIDATED_NOT_RELEVANT: "Validated — Not Relevant",
  INTRO_REQUESTED: "Intro Requested",
  INTRO_MADE: "Intro Made",
  CUSTOMER_REVIEWING: "Customer Reviewing",
  FOLLOW_UP_LATER: "Follow-up Later",
  CLOSED_WON: "Closed Won",
  CLOSED_LOST: "Closed Lost",
  DEAD: "Dead",
};

export const projectStatusTone: Record<string, BadgeTone> = {
  NEW: "gray",
  ASSIGNED: "slate",
  OUTREACH_STARTED: "blue",
  CONTACTED: "blue",
  VALIDATING: "amber",
  VALIDATED_RELEVANT: "green",
  VALIDATED_NOT_RELEVANT: "gray",
  INTRO_REQUESTED: "purple",
  INTRO_MADE: "purple",
  CUSTOMER_REVIEWING: "teal",
  FOLLOW_UP_LATER: "amber",
  CLOSED_WON: "green",
  CLOSED_LOST: "red",
  DEAD: "red",
};

export const contactStatusLabel: Record<string, string> = {
  NOT_CONTACTED: "Not Contacted",
  CALL_ATTEMPTED: "Call Attempted",
  LEFT_VOICEMAIL: "Left Voicemail",
  EMAIL_SENT: "Email Sent",
  SMS_SENT: "SMS Sent",
  REPLIED: "Replied",
  CONNECTED: "Connected",
  WRONG_PERSON: "Wrong Person",
  REFERRED: "Referred",
  INTERESTED: "Interested",
  NOT_INTERESTED: "Not Interested",
  DO_NOT_CONTACT: "Do Not Contact",
  INVALID: "Invalid",
};

export const contactStatusTone: Record<string, BadgeTone> = {
  NOT_CONTACTED: "gray",
  CALL_ATTEMPTED: "slate",
  LEFT_VOICEMAIL: "slate",
  EMAIL_SENT: "blue",
  SMS_SENT: "blue",
  REPLIED: "teal",
  CONNECTED: "blue",
  WRONG_PERSON: "red",
  REFERRED: "purple",
  INTERESTED: "green",
  NOT_INTERESTED: "red",
  DO_NOT_CONTACT: "red",
  INVALID: "red",
};

export const priorityTone: Record<string, BadgeTone> = {
  LOW: "gray",
  MEDIUM: "blue",
  HIGH: "amber",
  URGENT: "red",
};

export const stageLabel: Record<string, string> = {
  IDENTIFIED: "Identified",
  PROPOSED: "Proposed",
  PLANNING: "Planning",
  FUNDED: "Funded",
  DESIGN: "Design",
  PRE_RFP: "Pre-RFP",
  RFP: "RFP",
  CONSTRUCTION: "Construction",
  CLOSED: "Closed",
  UNKNOWN: "Unknown",
};

export const relevanceLabel: Record<string, string> = {
  PRIMARY_DECISION_MAKER: "Primary Decision Maker",
  INFLUENCER: "Influencer",
  PROCUREMENT: "Procurement",
  FACILITIES: "Facilities",
  ENGINEERING: "Engineering",
  ADMIN: "Admin",
  UNKNOWN: "Unknown",
};

export const activityTypeLabel: Record<string, string> = {
  CALL: "Call",
  EMAIL: "Email",
  SMS: "SMS",
  NOTE: "Note",
  STATUS_CHANGE: "Status Change",
  ASSIGNMENT_CHANGE: "Assignment Change",
  FOLLOW_UP: "Follow-up",
  SYSTEM: "System",
};

export const outcomeLabel: Record<string, string> = {
  NO_ANSWER: "No Answer",
  LEFT_VOICEMAIL: "Left Voicemail",
  CONNECTED: "Connected",
  SENT: "Sent",
  REPLIED: "Replied",
  BOUNCED: "Bounced",
  WRONG_PERSON: "Wrong Person",
  REFERRED: "Referred",
  INTERESTED: "Interested",
  NOT_INTERESTED: "Not Interested",
  OTHER: "Other",
};

// Enum value arrays for building dropdowns without importing Prisma on client.
export const PROJECT_STATUSES = Object.keys(projectStatusLabel);
export const CONTACT_STATUSES = Object.keys(contactStatusLabel);
export const STAGES = Object.keys(stageLabel);
export const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"];
export const CATEGORIES = [
  "BOILERS",
  "STEAM",
  "THERMAL_PLANT",
  "WATER",
  "WASTEWATER",
  "ELECTRICAL",
  "HVAC",
  "OTHER",
];
export const OWNER_ORG_TYPES = [
  "HOSPITAL",
  "UNIVERSITY",
  "COLLEGE",
  "SCHOOL_DISTRICT",
  "HIGH_SCHOOL",
  "CITY",
  "COUNTY",
  "STATE_AGENCY",
  "AIRPORT",
  "WATER_DISTRICT",
  "OTHER",
];
export const RELEVANCES = Object.keys(relevanceLabel);
export const CONTACT_SIDES = ["BUYER", "VENDOR", "INTERNAL", "OTHER"];
export const CALL_OUTCOMES = [
  "NO_ANSWER",
  "LEFT_VOICEMAIL",
  "CONNECTED",
  "WRONG_PERSON",
  "REFERRED",
  "INTERESTED",
  "NOT_INTERESTED",
  "OTHER",
];

export function enumLabel(value?: string | null): string {
  if (!value) return "—";
  return titleCase(value);
}

export function categoryLabel(value?: string | null): string {
  if (!value) return "—";
  if (value === "THERMAL_PLANT") return "Thermal Plant";
  if (value === "HVAC") return "HVAC";
  if (value === "RFP") return "RFP";
  return titleCase(value);
}
