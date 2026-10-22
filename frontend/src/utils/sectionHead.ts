/**
 * Which colleague a leave or official work application goes to for approval.
 *
 * Shared by Apply Leave and Official Work so the two forms cannot drift apart
 * on who the section head is.
 */

/** Anything the employees endpoint returns; only these fields are read. */
export interface EmployeeLike {
  erp_id: number | string;
  section_id: number | string;
  /** The grade's label, e.g. "G-11", when the API supplies it. */
  grade?: string | null;
  grade_id?: number | string | null;
  /** 1 for a current employee. Absent on an older API, treated as current. */
  flag?: number | string | null;
}

/**
 * Seniority as a number: G-11 is 11, G-01 is 1, higher is more senior.
 *
 * Prefers the grade's own label and falls back to `grade_id`, which carries the
 * same number for G-01 to G-11. A label without a number ("Internee") ranks 0,
 * below G-01: its `grade_id` is 12, which would otherwise rank an internee
 * above everyone and make them a section head. Anything unrecognisable ranks
 * last rather than ranking top by accident.
 */
export function gradeRank(employee: EmployeeLike | undefined | null): number {
  const name = String(employee?.grade ?? "").trim();
  const fromName = name.replace(/\D/g, "");
  if (fromName) return Number(fromName);
  if (name) return 0;

  const fromId = Number(employee?.grade_id);
  return Number.isFinite(fromId) ? fromId : -1;
}

const isCurrent = (employee: EmployeeLike): boolean =>
  employee.flag === undefined || employee.flag === null || Number(employee.flag) === 1;

/**
 * The section head for an applicant: the most senior current employee in their
 * own section — **including the applicant**.
 *
 * Somebody has to approve the head's own leave, and in this organisation that
 * is the head. So when the most senior person in a section applies, they are
 * their own approving authority; excluding themselves put their application in
 * front of a junior colleague, which is what this replaced. A tie at the top
 * grade also resolves to the applicant for the same reason.
 *
 * Seniority alone decides it. An earlier rule required grade 9 or above, which
 * left anyone in a section topping out at grade 8 with no head at all.
 *
 * Returns null only when the applicant is not in the list at all.
 */
export function findSectionHead<T extends EmployeeLike>(
  employees: T[],
  self: T
): T | null {
  const candidates = employees.filter(
    (employee) =>
      Number(employee.section_id) === Number(self.section_id) && isCurrent(employee)
  );

  // The applicant belongs in the running even if their own row is inactive or
  // missing from the list, so that a head is always proposed.
  if (!candidates.some((e) => Number(e.erp_id) === Number(self.erp_id))) {
    candidates.push(self);
  }

  if (candidates.length === 0) return null;

  const isSelf = (employee: T) => Number(employee.erp_id) === Number(self.erp_id);

  return candidates.reduce((best, employee) => {
    const difference = gradeRank(employee) - gradeRank(best);
    if (difference > 0) return employee;
    if (difference < 0) return best;

    // Same grade: the applicant wins, so the most senior person in a section
    // approves their own application rather than a peer's name appearing.
    if (isSelf(employee)) return employee;
    if (isSelf(best)) return best;

    // Otherwise the lower ERP id, so the same name is offered on every visit.
    return Number(employee.erp_id) < Number(best.erp_id) ? employee : best;
  });
}

/**
 * Colleagues to offer as approving authority: the applicant's own section
 * first, most senior first, then everyone else.
 */
export function sortedApprovers<T extends EmployeeLike>(
  employees: T[],
  self: T | undefined
): T[] {
  const active = employees.filter(isCurrent);
  if (!self) return active;

  const bySeniorityThenName = (a: T, b: T) =>
    gradeRank(b) - gradeRank(a) || Number(a.erp_id) - Number(b.erp_id);

  const sameSection = active
    .filter((e) => Number(e.section_id) === Number(self.section_id))
    .sort(bySeniorityThenName);

  const others = active
    .filter((e) => Number(e.section_id) !== Number(self.section_id))
    .sort(bySeniorityThenName);

  return [...sameSection, ...others];
}

/**
 * The section that holds the head of the whole department (the CEO), and the
 * grade from which an applicant's approver is that department head instead of
 * their own section head. A section head's own leave goes to the CEO.
 */
export const DEPARTMENT_SECTION_NAME = "ISMO";
export const DEPARTMENT_HEAD_MIN_GRADE = 10;

/**
 * The grade from which Official Work is created already approved. Compared
 * against gradeRank, never the raw `grade_id`: Internee's id is 12, so
 * `grade_id >= 9` auto-approved every internee.
 */
export const AUTO_APPROVE_MIN_GRADE = 9;

/**
 * The head of the whole department: the most senior current employee in the
 * department section (ERP 1134, the CEO, today). Worked out rather than fixed,
 * so a new CEO is picked up without a code change. Ties go to the lower ERP id.
 */
export function findDepartmentHead<T extends EmployeeLike>(
  employees: T[],
  departmentSectionId: number | string | null | undefined
): T | null {
  if (departmentSectionId === null || departmentSectionId === undefined) return null;
  const members = employees.filter(
    (employee) =>
      Number(employee.section_id) === Number(departmentSectionId) && isCurrent(employee)
  );
  if (members.length === 0) return null;
  return members.reduce((best, employee) => {
    const difference = gradeRank(employee) - gradeRank(best);
    if (difference !== 0) return difference > 0 ? employee : best;
    return Number(employee.erp_id) < Number(best.erp_id) ? employee : best;
  });
}

/**
 * Who an applicant's leave goes to by default: the department head for
 * MG-10 and above, otherwise their section head (see findSectionHead).
 */
export function findApprovingAuthority<T extends EmployeeLike>(
  employees: T[],
  self: T,
  departmentSectionId: number | string | null | undefined
): T | null {
  if (gradeRank(self) >= DEPARTMENT_HEAD_MIN_GRADE) {
    const departmentHead = findDepartmentHead(employees, departmentSectionId);
    if (departmentHead) return departmentHead;
  }
  return findSectionHead(employees, self);
}

/**
 * Approver choices for an applicant: their own section first, most senior
 * first, then everyone else - with the department head (CEO) moved to the top
 * for MG-10 and above, so the default is also the first entry.
 */
export function approverChoices<T extends EmployeeLike>(
  employees: T[],
  self: T | undefined,
  departmentSectionId: number | string | null | undefined
): T[] {
  const approvers = sortedApprovers(employees, self);
  if (!self || gradeRank(self) < DEPARTMENT_HEAD_MIN_GRADE) return approvers;
  const departmentHead = findDepartmentHead(employees, departmentSectionId);
  if (!departmentHead) return approvers;
  return [
    departmentHead,
    ...approvers.filter((e) => Number(e.erp_id) !== Number(departmentHead.erp_id)),
  ];
}
