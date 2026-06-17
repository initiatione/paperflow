const fs = require("fs");
const path = require("path");

const targetPath = process.argv[2] || process.env.PLUGIN_EVAL_TARGET;
const targetKind = process.argv[3] || process.env.PLUGIN_EVAL_TARGET_KIND || "unknown";

const TEXT_EXTENSIONS = new Set([".md", ".py", ".js", ".json", ".yaml", ".yml", ".toml"]);
const SKIP_DIRS = new Set([".git", ".plugin-eval", "node_modules", "__pycache__", ".pytest_cache"]);

function walkFiles(root) {
  const files = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) {
      continue;
    }
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(fullPath));
      continue;
    }
    if (entry.isFile() && TEXT_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
      files.push(fullPath);
    }
  }
  return files;
}

function readCorpus(root) {
  if (!root || !fs.existsSync(root)) {
    return "";
  }
  return walkFiles(root)
    .map((filePath) => fs.readFileSync(filePath, "utf8"))
    .join("\n")
    .toLowerCase();
}

function check(id, message, passed, evidence, remediation) {
  return {
    id,
    category: "paper-source-quality-gates",
    severity: passed ? "info" : "error",
    status: passed ? "pass" : "fail",
    message,
    evidence,
    remediation: passed ? [] : remediation
  };
}

const corpus = readCorpus(targetPath);
const hasRunState = corpus.includes("run-state.json");
const hasCriticGate = corpus.includes("critic") && corpus.includes("gate");
const hasNoCriticNoWrite = corpus.includes("no critic pass, no compiled wiki write");
const hasRawRetention = corpus.includes("paper.pdf") && corpus.includes("metadata.json");
const hasDevelopmentQualityLoop = (
  corpus.includes("plugin eval") &&
  corpus.includes("paper-source-quality-gates") &&
  corpus.includes("evaluation-brief") &&
  corpus.includes("propose-evolution")
);
const hasQualityLoopSourcesComplete = (
  corpus.includes("source_completeness") &&
  corpus.includes("quality_loop_sources_complete") &&
  corpus.includes("collect-missing-quality-evidence")
);
const hasBenchmarkContract = (
  corpus.includes("paper-source-benchmark-v1") &&
  corpus.includes("benchmark_contract") &&
  corpus.includes("invalid_sources")
);

const checks = [
  check(
    "paper-source-run-state-contract",
    "Paper Source workflow must expose run-state.json as the routing state source.",
    hasRunState,
    hasRunState ? ["Found run-state.json contract text."] : ["Missing run-state.json contract text."],
    ["Document and test that routed runs write and resume from run-state.json."]
  ),
  check(
    "paper-source-critic-gate-contract",
    "Paper Source must represent a critic gate before compiled wiki promotion.",
    hasCriticGate,
    hasCriticGate ? ["Found critic gate contract text."] : ["Missing critic gate contract text."],
    ["Add critic gate routing, state, documentation, and tests before compiled wiki writes exist."]
  ),
  check(
    "paper-source-no-critic-no-wiki-write",
    "Paper Source must encode the invariant: No critic pass, no compiled wiki write.",
    hasNoCriticNoWrite,
    hasNoCriticNoWrite ? ["Found exact no-critic/no-write invariant."] : ["Missing exact no-critic/no-write invariant."],
    ["Add the exact invariant `No critic pass, no compiled wiki write` to docs, routing rules, and tests."]
  ),
  check(
    "paper-source-raw-artifact-retention",
    "Paper Source must preserve raw PDF and metadata artifacts.",
    hasRawRetention,
    hasRawRetention ? ["Found paper.pdf and metadata.json artifact contract text."] : ["Missing raw PDF or metadata artifact contract text."],
    ["Document and test retention of paper.pdf and metadata.json under the raw paper artifact layout."]
  ),
  check(
    "paper-source-development-quality-loop",
    "Paper Source plugin development must expose Plugin Eval, paper-source-quality-gates, evaluation-brief, and propose-evolution as a closed quality loop.",
    hasDevelopmentQualityLoop,
    hasDevelopmentQualityLoop ? ["Found development quality loop contract text."] : ["Missing development quality loop contract text."],
    ["Document the Plugin Eval -> paper-source-quality-gates -> benchmark -> compare before/after -> evaluation-brief -> propose-evolution loop."]
  ),
  check(
    "paper-source-quality-loop-sources-complete",
    "Paper Source evaluation-brief must record source completeness and a required gate when evidence sources are missing.",
    hasQualityLoopSourcesComplete,
    hasQualityLoopSourcesComplete ? ["Found source completeness contract text."] : ["Missing source completeness contract text."],
    ["Document source_completeness.complete, quality_loop_sources_complete, and collect-missing-quality-evidence in the evaluation-brief contract."]
  ),
  check(
    "paper-source-benchmark-contract",
    "Paper Source development benchmark evidence must use the paper-source-benchmark-v1 contract and mark invalid sources.",
    hasBenchmarkContract,
    hasBenchmarkContract ? ["Found benchmark schema and invalid source contract text."] : ["Missing benchmark schema or invalid source contract text."],
    ["Document and implement paper-source-benchmark-v1, benchmark_contract, and invalid_sources handling before treating benchmarks as comparable evidence."]
  )
];

const passedCount = checks.filter((item) => item.status === "pass").length;

console.log(
  JSON.stringify(
    {
      checks,
      metrics: [
        {
          id: "paper-source-quality-gate-pass-rate",
          category: "paper-source-quality-gates",
          value: passedCount / checks.length,
          unit: "ratio",
          band: passedCount === checks.length ? "good" : "poor"
        }
      ],
      artifacts: [
        {
          id: "paper-source-quality-gates-target",
          type: "path",
          label: "Paper Source quality gates target",
          description: `${targetKind}: ${targetPath}`
        }
      ]
    },
    null,
    2
  )
);
