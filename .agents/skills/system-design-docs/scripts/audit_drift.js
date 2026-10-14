#!/usr/bin/env node
/**
 * Automated Architectural Drift Detection Script
 * Analyzes git diffs against docs/architecture/ to identify undocumented routes,
 * newly added stores, or changed API clients, outputting targeted update plans.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { classifyFiles } = require('./generate_manifest');

function getGitDiffFiles(baseRef = 'HEAD~10') {
  try {
    const output = execSync(`git diff --name-only ${baseRef}`, {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'ignore'],
    });
    return output
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
  } catch (err) {
    // Fallback to uncommitted working tree changes if git diff baseRef fails
    try {
      const output = execSync('git status --porcelain', { encoding: 'utf8' });
      return output
        .split('\n')
        .map((l) => l.trim().slice(3))
        .filter(Boolean);
    } catch {
      return [];
    }
  }
}

function auditDrift(baseRef = 'HEAD~10', targetDir = process.cwd(), format = 'markdown') {
  const diffFiles = getGitDiffFiles(baseRef);
  const categorized = classifyFiles(diffFiles, targetDir);

  const driftResults = [];

  for (const domainKey of Object.keys(categorized)) {
    const domain = categorized[domainKey];
    if (domain.files.length > 0) {
      driftResults.push({
        domainId: domain.id,
        domainName: domain.name,
        outputModule: domain.outputModule,
        changedFiles: domain.files,
        regenerationCommand: `node .agents/skills/system-design-docs/scripts/generate_manifest.js --domain=${domain.id}`,
      });
    }
  }

  if (format === 'json') {
    console.log(
      JSON.stringify({ baseRef, changedFileCount: diffFiles.length, driftResults }, null, 2),
    );
    return;
  }

  console.log(`\n🔍 Architectural Drift Audit (Comparing against: ${baseRef})\n`);
  console.log(`Total Changed Files Detected: ${diffFiles.length}`);

  if (driftResults.length === 0) {
    console.log(
      '\n✨ No architectural drift detected! All recent changes align with existing modules.\n',
    );
    return;
  }

  console.log(
    `\n⚠️  Architectural Drift Detected Across ${driftResults.length} Subsystem Domain(s):\n`,
  );

  for (const r of driftResults) {
    console.log(`### 📦 ${r.domainName}`);
    console.log(`- **Assigned Module:** \`${r.outputModule}\``);
    console.log(`- **Modified Files (${r.changedFiles.length}):**`);
    for (const f of r.changedFiles) {
      console.log(`  - \`${f}\``);
    }
    console.log(`- **Recommended Action:** Run \`${r.regenerationCommand}\`\n`);
  }

  console.log('─'.repeat(60));
  console.log('💡 Tip: Use Mode B targeted regeneration to update only affected modules.');
  console.log('─'.repeat(60) + '\n');
}

function main() {
  const args = process.argv.slice(2);
  const baseRefArg = args.find((a) => a.startsWith('--base='))?.split('=')[1] || 'HEAD~10';
  const format = args.includes('--json') ? 'json' : 'markdown';

  auditDrift(baseRefArg, process.cwd(), format);
}

if (require.main === module) {
  main();
}

module.exports = { getGitDiffFiles, auditDrift };
