export interface TestEvidence {
  command: string[] | string;
  stdout: string;
  stderr: string;
  exit_code: number;
}

export interface DeveloperEvidenceData {
  changed_files: string[];
  git_branch: string;
  git_status: string;
  git_diff: string;
  test_results: TestEvidence[];
  commands: (string[] | string)[];
  codex_output: string;
}

const emptyEvidence: DeveloperEvidenceData = {
  changed_files: [],
  git_branch: "",
  git_status: "",
  git_diff: "",
  test_results: [],
  commands: [],
  codex_output: "",
};

export function parseDeveloperEvidence(
  output: string | null,
): DeveloperEvidenceData {
  if (!output) return emptyEvidence;
  try {
    const parsed = JSON.parse(output);
    const evidence = parsed?.evidence;
    if (!evidence || typeof evidence !== "object") return emptyEvidence;
    return {
      changed_files: Array.isArray(evidence.changed_files)
        ? evidence.changed_files
        : [],
      git_branch: String(evidence.git_branch ?? ""),
      git_status: String(evidence.git_status ?? ""),
      git_diff: String(evidence.git_diff ?? ""),
      test_results: Array.isArray(evidence.test_results)
        ? evidence.test_results
        : [],
      commands: Array.isArray(evidence.commands) ? evidence.commands : [],
      codex_output: String(evidence.codex_output ?? parsed?.execution?.output ?? ""),
    };
  } catch {
    return { ...emptyEvidence, codex_output: output };
  }
}
