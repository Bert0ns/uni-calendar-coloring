#!/usr/bin/env node
/**
 * Unified Architecture Blueprint Quality Verification Gate
 * Performs end-to-end static quality checks on docs/architecture/:
 *  1. Canonical module presence (10/10 modules)
 *  2. Bidirectional breadcrumb navigation (top & bottom)
 *  3. Internal relative link integrity & file symbol existence
 *  4. 100% Native Mermaid diagram syntax & zero-ASCII-art gating
 */

const fs = require('fs');
const path = require('path');
const { CANONICAL_MODULES, buildBreadcrumb } = require('./assemble_blueprint');
const {
  lintMermaidBlock,
  extractMermaidBlocks,
  lintDocumentForForbiddenAscii,
} = require('./verify_mermaid');

function verifyBlueprint(targetDir, options = {}) {
  const rootDir = process.cwd();
  const archDir = targetDir || path.join(rootDir, 'docs/architecture');

  const results = {
    modulesChecked: 0,
    diagramsChecked: 0,
    linksChecked: 0,
    errors: [],
    warnings: [],
  };

  if (!fs.existsSync(archDir)) {
    results.errors.push(`Architecture directory not found: ${archDir}`);
    return results;
  }

  // 1. Check all canonical modules exist
  for (const mod of CANONICAL_MODULES) {
    const modPath = path.join(archDir, mod.file);
    results.modulesChecked++;

    if (!fs.existsSync(modPath)) {
      results.errors.push(
        `[MISSING_MODULE] Missing canonical module: ${mod.file} (Module ${mod.id})`,
      );
      continue;
    }

    const content = fs.readFileSync(modPath, 'utf8');
    const lines = content.split('\n');
    const expectedBreadcrumb = buildBreadcrumb(mod);

    // 2. Breadcrumb Verification (Top & Bottom)
    let hasTopBreadcrumb = false;
    for (let i = 0; i < Math.min(15, lines.length); i++) {
      if (lines[i].includes('[Index](./index.md)')) {
        hasTopBreadcrumb = true;
        break;
      }
    }
    if (!hasTopBreadcrumb) {
      results.errors.push(
        `[MISSING_TOP_BREADCRUMB] ${mod.file} is missing top navigation breadcrumb.`,
      );
    }

    let hasBottomBreadcrumb = false;
    for (let i = lines.length - 1; i >= Math.max(0, lines.length - 15); i--) {
      if (lines[i].includes('[Index](./index.md)')) {
        hasBottomBreadcrumb = true;
        break;
      }
    }
    if (!hasBottomBreadcrumb && lines.length > 20) {
      results.errors.push(
        `[MISSING_BOTTOM_BREADCRUMB] ${mod.file} is missing bottom navigation breadcrumb.`,
      );
    }

    // 3. Internal Markdown Link Verification
    const relativeLinkRegex = /\[([^\]]+)\]\(\.\/([^)]+\.md)\)/g;
    let linkMatch;
    while ((linkMatch = relativeLinkRegex.exec(content)) !== null) {
      results.linksChecked++;
      const targetRel = linkMatch[2];
      const targetFull = path.join(archDir, targetRel);
      if (!fs.existsSync(targetFull)) {
        results.errors.push(
          `[BROKEN_INTERNAL_LINK] ${mod.file}: [${linkMatch[1]}](./${targetRel}) -> File not found on disk`,
        );
      }
    }

    // 4. Code Symbol Link File Existence Check
    const fileLinkRegex = /\[([^\]]+)\]\((file:\/\/\/(?:[^\s()]+|\([^\s()]+\))+)\)/g;
    let fileMatch;
    while ((fileMatch = fileLinkRegex.exec(content)) !== null) {
      results.linksChecked++;
      const fileUri = fileMatch[2];
      // Extract absolute path from file:///...#L10-L20 and handle URL encoding
      const rawPath = fileUri.replace(/^file:\/\//, '').split('#')[0];
      const cleanPath = decodeURIComponent(rawPath);
      if (!fs.existsSync(cleanPath)) {
        results.warnings.push(
          `[MISSING_SOURCE_FILE] ${mod.file}: Reference to non-existent file: ${cleanPath}`,
        );
      }
    }

    // 5. Full Document Forbidden ASCII Check
    if (lintDocumentForForbiddenAscii) {
      const asciiErrors = lintDocumentForForbiddenAscii(content, mod.file);
      for (const ae of asciiErrors) {
        results.errors.push(`[ASCII_ART_ERROR] ${mod.file}:L${ae.line} [${ae.rule}] ${ae.message}`);
      }
    }

    // 6. Mermaid Diagram Linting
    const mermaidBlocks = extractMermaidBlocks(content, mod.file);
    for (const b of mermaidBlocks) {
      results.diagramsChecked++;
      const { errors: mErrors, warnings: mWarnings } = lintMermaidBlock(b);
      for (const me of mErrors) {
        results.errors.push(`[MERMAID_ERROR] ${mod.file}:L${me.line} [${me.rule}] ${me.message}`);
      }
      for (const mw of mWarnings) {
        results.warnings.push(`[MERMAID_WARN] ${mod.file}:L${mw.line} [${mw.rule}] ${mw.message}`);
      }
    }
  }

  return results;
}

function runVerificationCli() {
  const args = process.argv.slice(2);
  const targetDir =
    args.find((a) => !a.startsWith('--')) || path.join(process.cwd(), 'docs/architecture');
  const isJson = args.includes('--json');

  const results = verifyBlueprint(targetDir);

  if (isJson) {
    console.log(JSON.stringify(results, null, 2));
    process.exit(results.errors.length > 0 ? 1 : 0);
  }

  console.log(`\n🔍 Architecture Blueprint Unified Quality Gate: ${targetDir}\n`);
  console.log(`- Canonical Modules Checked: ${results.modulesChecked}/10`);
  console.log(`- Diagram Blocks Validated:  ${results.diagramsChecked}`);
  console.log(`- Links & Symbol Citations:  ${results.linksChecked}`);
  console.log(`- Total Errors:              ${results.errors.length}`);
  console.log(`- Total Warnings:            ${results.warnings.length}`);
  console.log('─'.repeat(60) + '\n');

  if (results.warnings.length > 0) {
    console.log('⚠️  Warnings:');
    for (const w of results.warnings) {
      console.warn(`  - ${w}`);
    }
    console.log('');
  }

  if (results.errors.length > 0) {
    console.error('❌ Quality Gate Failures:');
    for (const e of results.errors) {
      console.error(`  - ${e}`);
    }
    console.error('\n💥 Unified Architecture Quality Gate failed. Please resolve above errors.\n');
    process.exit(1);
  } else {
    console.log('✨ All 10 architecture blueprint modules passed all quality gates!\n');
    process.exit(0);
  }
}

if (require.main === module) {
  runVerificationCli();
}

module.exports = { verifyBlueprint };
