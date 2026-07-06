/**
 * Project/contact status automation rules.
 *
 * These are pure functions so the logic is easy to reason about and reuse from
 * the activity-logging server action.
 */

// Higher rank = further along the pipeline. Used to avoid downgrading a
// project when a later automation fires an earlier target status.
const PROJECT_STATUS_RANK: Record<string, number> = {
  NEW: 0,
  ASSIGNED: 1,
  OUTREACH_STARTED: 2,
  CONTACTED: 3,
  VALIDATING: 4,
  VALIDATED_RELEVANT: 5,
  INTRO_REQUESTED: 6,
  INTRO_MADE: 7,
  CUSTOMER_REVIEWING: 8,
  // Side/terminal states — treated as locked so automation won't override them.
  VALIDATED_NOT_RELEVANT: 90,
  FOLLOW_UP_LATER: 4,
  CLOSED_WON: 100,
  CLOSED_LOST: 100,
  DEAD: 100,
};

const TERMINAL_STATUSES = new Set([
  "CLOSED_WON",
  "CLOSED_LOST",
  "DEAD",
  "VALIDATED_NOT_RELEVANT",
]);

/** Returns the target status only if it moves the project forward. */
export function advanceProjectStatus(
  current: string,
  target: string
): string {
  if (TERMINAL_STATUSES.has(current)) return current;
  const currentRank = PROJECT_STATUS_RANK[current] ?? 0;
  const targetRank = PROJECT_STATUS_RANK[target] ?? 0;
  return targetRank > currentRank ? target : current;
}

/** Maps an activity outcome to the resulting contact status, if any. */
export function contactStatusForOutcome(
  outcome: string | null | undefined
): string | null {
  switch (outcome) {
    case "CONNECTED":
      return "CONNECTED";
    case "INTERESTED":
      return "INTERESTED";
    case "NOT_INTERESTED":
      return "NOT_INTERESTED";
    case "WRONG_PERSON":
      return "WRONG_PERSON";
    case "REFERRED":
      return "REFERRED";
    case "LEFT_VOICEMAIL":
      return "LEFT_VOICEMAIL";
    case "REPLIED":
      return "REPLIED";
    default:
      return null;
  }
}

/** Maps the channel of a "sent" style activity to a contact status. */
export function contactStatusForSent(type: string): string | null {
  switch (type) {
    case "EMAIL":
      return "EMAIL_SENT";
    case "SMS":
      return "SMS_SENT";
    case "CALL":
      return "CALL_ATTEMPTED";
    default:
      return null;
  }
}

export interface ActivityStatusEffects {
  contactStatus: string | null;
  projectStatusTarget: string | null;
  promptAddReferredContact: boolean;
}

/**
 * Given an activity's type/outcome, compute the intended contact status and the
 * project status the automation should attempt to advance to.
 *
 * `relevantValidation` lets the call-logging modal request VALIDATED_RELEVANT
 * instead of the default VALIDATING when a contact is interested.
 */
export function computeActivityEffects(params: {
  type: string;
  outcome?: string | null;
  relevantValidation?: boolean;
}): ActivityStatusEffects {
  const { type, outcome, relevantValidation } = params;

  let contactStatus = contactStatusForOutcome(outcome);
  let projectStatusTarget: string | null = null;
  let promptAddReferredContact = false;

  switch (outcome) {
    case "CONNECTED":
      projectStatusTarget = "CONTACTED";
      break;
    case "INTERESTED":
      projectStatusTarget = relevantValidation
        ? "VALIDATED_RELEVANT"
        : "VALIDATING";
      break;
    case "REFERRED":
      promptAddReferredContact = true;
      break;
    default:
      break;
  }

  // For plain "sent" channel logging without a stronger outcome, reflect the
  // channel on the contact if it is otherwise untouched.
  if (!contactStatus && (outcome === "SENT" || !outcome)) {
    contactStatus = contactStatusForSent(type);
  }

  return { contactStatus, projectStatusTarget, promptAddReferredContact };
}
