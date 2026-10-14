#!/usr/bin/env node
/**
 * Automated System Design Blueprint Assembler & Link Validator
 * Validates module completeness, verifies relative cross-module links,
 * and ensures standardized navigation breadcrumbs across docs/architecture/.
 */

const fs = require('fs');
const path = require('path');

const CANONICAL_MODULES = [
  {
    id: '00',
    file: 'index.md',
    title: 'Index & Master Blueprint',
    prev: null,
    next: '01-c4-context-and-containers.md',
    nextTitle: 'C4 Context & Containers',
  },
  {
    id: '01',
    file: '01-c4-context-and-containers.md',
    title: 'C4 Architecture Model: Context & Container Topology',
    prev: 'index.md',
    prevTitle: 'Index',
    next: '02-screens-and-navigation.md',
    nextTitle: 'Screens & Navigation',
  },
  {
    id: '02',
    file: '02-screens-and-navigation.md',
    title: 'Screens, Navigation & UX Architecture',
    prev: '01-c4-context-and-containers.md',
    prevTitle: 'C4 Context & Containers',
    next: '03-state-management-and-domain.md',
    nextTitle: 'State Management & Domain Logic',
  },
  {
    id: '03',
    file: '03-state-management-and-domain.md',
    title: 'State Management & Domain Architecture',
    prev: '02-screens-and-navigation.md',
    prevTitle: 'Screens & Navigation',
    next: '04-sensors-kinematics-and-native.md',
    nextTitle: 'Hardware Sensors & Kinematics',
  },
  {
    id: '04',
    file: '04-sensors-kinematics-and-native.md',
    title: 'Hardware Sensors, Kinematics & Native Subsystems',
    prev: '03-state-management-and-domain.md',
    prevTitle: 'State Management & Domain Logic',
    next: '05-apis-networking-and-proxy.md',
    nextTitle: 'External APIs & Networking',
  },
  {
    id: '05',
    file: '05-apis-networking-and-proxy.md',
    title: 'External APIs, Networking & Web Proxy Architecture',
    prev: '04-sensors-kinematics-and-native.md',
    prevTitle: 'Hardware Sensors & Kinematics',
    next: '06-cross-cutting-concerns.md',
    nextTitle: 'Cross-Cutting Concerns',
  },
  {
    id: '06',
    file: '06-cross-cutting-concerns.md',
    title: 'Cross-Cutting Architectural Concerns',
    prev: '05-apis-networking-and-proxy.md',
    prevTitle: 'External APIs & Networking',
    next: '07-solid-principles-and-patterns.md',
    nextTitle: 'SOLID Principles & Patterns',
  },
  {
    id: '07',
    file: '07-solid-principles-and-patterns.md',
    title: 'SOLID Principles & Design Patterns Architecture',
    prev: '06-cross-cutting-concerns.md',
    prevTitle: 'Cross-Cutting Concerns',
    next: '08-testing-and-cicd.md',
    nextTitle: 'Testing Strategy & CI/CD',
  },
  {
    id: '08',
    file: '08-testing-and-cicd.md',
    title: 'Testing Strategy & CI/CD Quality Gates Architecture',
    prev: '07-solid-principles-and-patterns.md',
    prevTitle: 'SOLID Principles & Patterns',
    next: '09-appendix-technical-debt.md',
    nextTitle: 'Technical Debt & Appendix',
  },
  {
    id: '09',
    file: '09-appendix-technical-debt.md',
    title: 'Technical Debt Matrix & Remediation Roadmap',
    prev: '08-testing-and-cicd.md',
    prevTitle: 'Testing Strategy & CI/CD',
    next: null,
  },
];

function buildBreadcrumb(mod) {
  const parts = [];
  if (mod.prev) {
    parts.push(`[← Previous: ${mod.prevTitle}](./${mod.prev})`);
  }
  parts.push(`[Index](./index.md)`);
  if (mod.next) {
    parts.push(`[Next: ${mod.nextTitle} →](./${mod.next})`);
  }
  return parts.join(' | ');
}

function injectBreadcrumbs(content, mod) {
  const breadcrumb = buildBreadcrumb(mod);
  const lines = content.trim().split('\n');

  // 1. Top Breadcrumb: find existing or insert after title/header block
  let topBreadcrumbIdx = -1;
  for (let i = 0; i < Math.min(15, lines.length); i++) {
    if (
      lines[i].includes('[Index](./index.md)') ||
      lines[i].includes('[← Previous') ||
      lines[i].includes('[Next:')
    ) {
      topBreadcrumbIdx = i;
      break;
    }
  }

  if (topBreadcrumbIdx !== -1) {
    lines[topBreadcrumbIdx] = breadcrumb;
  } else {
    let titleIdx = -1;
    for (let i = 0; i < Math.min(10, lines.length); i++) {
      if (lines[i].startsWith('# ')) {
        titleIdx = i;
        break;
      }
    }

    if (titleIdx !== -1) {
      let insertIdx = titleIdx + 1;
      while (
        insertIdx < lines.length &&
        (lines[insertIdx].startsWith('>') || lines[insertIdx].trim() === '')
      ) {
        insertIdx++;
      }
      lines.splice(insertIdx, 0, '', breadcrumb, '');
    } else {
      lines.unshift(breadcrumb, '');
    }
  }

  // 2. Bottom Breadcrumb: find existing in last 10 lines or append
  while (lines.length > 0 && lines[lines.length - 1].trim() === '') {
    lines.pop();
  }

  let bottomBreadcrumbIdx = -1;
  for (let i = lines.length - 1; i >= Math.max(0, lines.length - 10); i--) {
    if (
      i > 15 &&
      (lines[i].includes('[Index](./index.md)') ||
        lines[i].includes('[← Previous') ||
        lines[i].includes('[Next:'))
    ) {
      bottomBreadcrumbIdx = i;
      break;
    }
  }

  if (bottomBreadcrumbIdx !== -1) {
    lines[bottomBreadcrumbIdx] = breadcrumb;
  } else {
    lines.push('', '---', '', breadcrumb);
  }

  return lines.join('\n') + '\n';
}

function sanitizeMermaidBlock(blockCode) {
  const lines = blockCode.split('\n');
  if (lines.length === 0) return blockCode;

  const header = lines[0].trim();

  // 1. Flowchart / Graph sanitization
  if (header.startsWith('flowchart') || header.startsWith('graph')) {
    for (let i = 1; i < lines.length; i++) {
      let line = lines[i];
      const trimmed = line.trim();
      if (
        trimmed.startsWith('%%') ||
        trimmed.startsWith('subgraph') ||
        trimmed.startsWith('end') ||
        trimmed.startsWith('direction') ||
        trimmed.startsWith('style') ||
        trimmed.startsWith('classDef') ||
        trimmed.startsWith('linkStyle')
      ) {
        continue;
      }

      // Quote node labels containing parentheses or slashes ONLY if not already quoted
      if (!/\[".*?"\]/.test(line)) {
        line = line.replace(/([a-zA-Z0-9_-]+)\[([^"\]\n]*[\(\)\/][^"\]\n]*)\]/g, '$1["$2"]');
      }
      if (!/\(".*?"\)/.test(line)) {
        line = line.replace(/([a-zA-Z0-9_-]+)\(([^"\)\n]*[\[\]\/][^"\)\n]*)\)/g, '$1("$2")');
      }
      if (!/\{".*?"\}/.test(line)) {
        line = line.replace(/([a-zA-Z0-9_-]+)\{([^"\}\n]*[\(\)\/][^"\}\n]*)\}/g, '$1{"$2"}');
      }

      lines[i] = line;
    }
  }

  // 2. Sequence diagram sanitization (ensure autonumber)
  if (header.startsWith('sequenceDiagram')) {
    let hasAutonumber = false;
    for (let i = 1; i < Math.min(5, lines.length); i++) {
      if (lines[i].trim() === 'autonumber') {
        hasAutonumber = true;
        break;
      }
    }
    if (!hasAutonumber) {
      lines.splice(1, 0, '    autonumber');
    }
  }

  // 3. Class diagram sanitization (<T> -> ~T~)
  if (header.startsWith('classDiagram')) {
    for (let i = 1; i < lines.length; i++) {
      lines[i] = lines[i].replace(/(?<!<)<([A-Za-z0-9_,\s]+)>(?!>)/g, '~$1~');
    }
  }

  return lines.join('\n');
}

function sanitizeMarkdownMermaid(content) {
  const mermaidRegex = /```mermaid\s*\n([\s\S]*?)```/g;
  return content.replace(mermaidRegex, (match, code) => {
    const sanitized = sanitizeMermaidBlock(code.trim());
    return `\`\`\`mermaid\n${sanitized}\n\`\`\``;
  });
}

function promoteStagedFiles(archDir, cleanStaging = true) {
  const stagingDir = path.join(archDir, '.staging');
  if (!fs.existsSync(stagingDir)) return 0;

  const stagedFiles = fs.readdirSync(stagingDir);
  let promoted = 0;

  for (const f of stagedFiles) {
    if (f.endsWith('.md')) {
      const src = path.join(stagingDir, f);
      const dest = path.join(archDir, f);
      fs.copyFileSync(src, dest);
      promoted++;
    }
  }

  if (cleanStaging && fs.existsSync(stagingDir)) {
    fs.rmSync(stagingDir, { recursive: true, force: true });
    console.log(`🧹 Cleaned up staging directory: ${stagingDir}`);
  }

  return promoted;
}

function validateAndAssemble(targetDir, options = {}) {
  const errors = [];
  const warnings = [];

  console.log(`\n📐 Assembling & Validating Architecture Blueprint: ${targetDir}\n`);

  if (!fs.existsSync(targetDir)) {
    console.error(`❌ Target directory does not exist: ${targetDir}`);
    process.exit(1);
  }

  if (options.promote) {
    const count = promoteStagedFiles(targetDir, options.clean !== false);
    if (count > 0) {
      console.log(`🚀 Promoted ${count} file(s) from .staging/ to ${targetDir}`);
    }
  }

  // 1. Verify all 10 canonical modules exist
  for (const mod of CANONICAL_MODULES) {
    const filePath = path.join(targetDir, mod.file);
    if (!fs.existsSync(filePath)) {
      errors.push(`Missing canonical module file: ${mod.file} (Module ${mod.id})`);
    } else {
      let content = fs.readFileSync(filePath, 'utf8');

      // 2. Validate internal links
      const linkRegex = /\[([^\]]+)\]\(\.\/([^)]+\.md)\)/g;
      let match;
      while ((match = linkRegex.exec(content)) !== null) {
        const targetRelative = match[2];
        const targetFull = path.join(targetDir, targetRelative);
        if (!fs.existsSync(targetFull)) {
          errors.push(
            `Broken relative markdown link in ${mod.file}: [${match[1]}](./${targetRelative}) -> Target not found`,
          );
        }
      }

      // 3. Inject / Update breadcrumbs and sanitize Mermaid if requested
      if (options.fixBreadcrumbs || options.sanitizeMermaid) {
        let updatedContent = content;
        if (options.fixBreadcrumbs) {
          updatedContent = injectBreadcrumbs(updatedContent, mod);
        }
        if (options.sanitizeMermaid !== false) {
          updatedContent = sanitizeMarkdownMermaid(updatedContent);
        }

        if (updatedContent !== content) {
          fs.writeFileSync(filePath, updatedContent, 'utf8');
          content = updatedContent;
        }
      }

      // 4. Verify breadcrumbs exist
      if (!content.includes('[Index](./index.md)')) {
        warnings.push(`Module ${mod.file} is missing navigation breadcrumb.`);
      }
    }
  }

  // Summary
  console.log('─'.repeat(60));
  console.log(`Canonical Modules Checked: ${CANONICAL_MODULES.length}/10`);
  console.log(`Validation Errors: ${errors.length}`);
  console.log(`Validation Warnings: ${warnings.length}`);
  console.log('─'.repeat(60) + '\n');

  if (options.exit === false) {
    return { errors, warnings };
  }

  if (errors.length > 0) {
    for (const e of errors) {
      console.error(`  ❌ ${e}`);
    }
    console.error('\n💥 Architecture blueprint assembly failed validation.\n');
    process.exit(1);
  } else {
    console.log('✨ All 10 architecture modules assembled and validated successfully!\n');
    process.exit(0);
  }
}

/**
 * Unpacks multi-file delimiter payload strings (e.g. from research subagents) into staging directory.
 * Delimiter format:
 * <!-- FILE: docs/architecture/<filename>.md -->
 * ... content ...
 * <!-- END_FILE -->
 */
function unpackPayload(payloadText, stagingDir) {
  if (!payloadText || typeof payloadText !== 'string') {
    return [];
  }
  fs.mkdirSync(stagingDir, { recursive: true });

  const fileBlockRegex =
    /<!--\s*FILE:\s*(?:docs\/architecture\/)?([a-zA-Z0-9_.-]+)\s*-->([\s\S]*?)(?:<!--\s*END_FILE\s*-->|$)/g;
  const writtenFiles = [];
  let match;

  while ((match = fileBlockRegex.exec(payloadText)) !== null) {
    const filename = match[1].trim();
    const content = match[2].trim();
    if (filename && content) {
      const destPath = path.join(stagingDir, filename);
      fs.writeFileSync(destPath, content + '\n', 'utf8');
      writtenFiles.push(filename);
    }
  }

  return writtenFiles;
}

/**
 * Automatically extracts deliverables from subagent transcripts into staging directory.
 */
function unpackTranscriptFiles(transcriptPaths, stagingDir) {
  const unpacked = [];
  fs.mkdirSync(stagingDir, { recursive: true });

  for (const tPath of transcriptPaths) {
    if (!fs.existsSync(tPath)) continue;
    const lines = fs.readFileSync(tPath, 'utf8').trim().split('\n');

    let found = false;
    for (let i = lines.length - 1; i >= 0; i--) {
      try {
        const obj = JSON.parse(lines[i]);
        if (obj.tool_calls) {
          for (const tc of obj.tool_calls) {
            if (
              tc.name === 'send_message' &&
              tc.args?.Message &&
              tc.args.Message.includes('<!-- FILE:')
            ) {
              const files = unpackPayload(tc.args.Message, stagingDir);
              unpacked.push(...files);
              found = true;
              break;
            }
          }
        }
        if (found) break;
      } catch (e) {}
    }

    if (!found) {
      for (let i = lines.length - 1; i >= 0; i--) {
        try {
          const obj = JSON.parse(lines[i]);
          if (obj.source === 'MODEL' && obj.content && obj.content.includes('<!-- FILE:')) {
            const files = unpackPayload(obj.content, stagingDir);
            unpacked.push(...files);
            found = true;
            break;
          }
        } catch (e) {}
        if (found) break;
      }
    }
  }

  return [...new Set(unpacked)];
}

function autoFixCitations(targetDir) {
  const files = fs.readdirSync(targetDir);
  const commonDrifts = [
    { from: /scannerSection\.tsx/g, to: 'LoginScannerSection.tsx' },
    { from: /routeCard\.tsx/g, to: 'LoginRouteCard.tsx' },
    { from: /utils\/geo\.ts/g, to: 'utils/geometry.ts' },
    {
      from: /currentsapi-news\/currentsapi-news\.ts/g,
      to: 'currentsapi-news/currentsapi-news-service.ts',
    },
    { from: /masonryGrid\.tsx/g, to: 'masonry-grid.tsx' },
    { from: /actionButtons\.tsx/g, to: 'action-buttons.tsx' },
  ];

  let fixedCount = 0;
  for (const file of files) {
    if (file.endsWith('.md')) {
      const fullPath = path.join(targetDir, file);
      let content = fs.readFileSync(fullPath, 'utf8');
      let modified = false;

      for (const d of commonDrifts) {
        if (d.from.test(content)) {
          content = content.replace(d.from, d.to);
          modified = true;
          fixedCount++;
        }
      }

      if (modified) {
        fs.writeFileSync(fullPath, content, 'utf8');
      }
    }
  }

  return fixedCount;
}

function main() {
  const args = process.argv.slice(2);
  const targetDir =
    args.find((a) => !a.startsWith('--')) || path.join(process.cwd(), 'docs/architecture');
  const promote = args.includes('--promote');
  const fixBreadcrumbs = args.includes('--fix-breadcrumbs');
  const clean = !args.includes('--no-clean');
  const unpackArg = args.find((a) => a.startsWith('--unpack='))?.split('=')[1];
  const transcriptsArg = args.find((a) => a.startsWith('--from-transcripts='))?.split('=')[1];

  const stagingDir = path.join(targetDir, '.staging');

  if (unpackArg) {
    const payloadContent = fs.readFileSync(path.resolve(process.cwd(), unpackArg), 'utf8');
    const unpacked = unpackPayload(payloadContent, stagingDir);
    console.log(
      `📦 Unpacked ${unpacked.length} file(s) into ${stagingDir}: ${unpacked.join(', ')}`,
    );
  }

  if (transcriptsArg) {
    const transcriptList = transcriptsArg
      .split(',')
      .map((p) => path.resolve(process.cwd(), p.trim()));
    const unpacked = unpackTranscriptFiles(transcriptList, stagingDir);
    console.log(
      `📦 Unpacked ${unpacked.length} file(s) from transcripts into ${stagingDir}: ${unpacked.join(', ')}`,
    );
  }

  autoFixCitations(targetDir);

  validateAndAssemble(targetDir, { promote, fixBreadcrumbs, clean });
}

if (require.main === module) {
  main();
}

module.exports = {
  CANONICAL_MODULES,
  buildBreadcrumb,
  injectBreadcrumbs,
  sanitizeMermaidBlock,
  sanitizeMarkdownMermaid,
  promoteStagedFiles,
  unpackPayload,
  unpackTranscriptFiles,
  autoFixCitations,
  validateAndAssemble,
};
