#!/usr/bin/env node
/**
 * Automated Mermaid Diagram Syntax & Quality Linter Script
 * Scans markdown architecture documents and validates Mermaid blocks against diagram guidelines.
 */

const fs = require('fs');
const path = require('path');

const ASCII_BOX_REGEX = /[┌┐└┘│─]|(\+---)|(\+===)/;

function extractMermaidBlocks(content, filePath) {
  const lines = content.split('\n');
  const blocks = [];
  let inBlock = false;
  let blockLines = [];
  let startLine = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!inBlock && line.trim().startsWith('```mermaid')) {
      inBlock = true;
      startLine = i + 1;
      blockLines = [];
    } else if (inBlock && line.trim() === '```') {
      inBlock = false;
      blocks.push({
        filePath,
        startLine,
        endLine: i + 1,
        code: blockLines.join('\n'),
        lines: blockLines,
      });
    } else if (inBlock) {
      blockLines.push(line);
    }
  }

  return blocks;
}

function lintMermaidBlock(block) {
  const errors = [];
  const warnings = [];
  const text = block.code;
  const header = block.lines[0]?.trim() || '';

  // 1. Zero ASCII Art Gate
  for (let idx = 0; idx < block.lines.length; idx++) {
    const line = block.lines[idx];
    if (ASCII_BOX_REGEX.test(line)) {
      errors.push({
        line: block.startLine + idx + 1,
        rule: 'ZERO_ASCII_ART',
        message: `Forbidden ASCII box character detected on line ${block.startLine + idx + 1}`,
      });
    }

    // Check for unescaped nested double quotes inside node delimiters
    if (/\["([^"\]\r\n]*"[^"\]\r\n]*)+"[\])]/.test(line)) {
      errors.push({
        line: block.startLine + idx + 1,
        rule: 'MERMAID_NESTED_QUOTES',
        message: `Unescaped nested double quotes detected in Mermaid node label on line ${block.startLine + idx + 1}: ${line.trim()}`,
      });
    }
  }

  // 2. Flowchart Checks
  if (header.startsWith('flowchart')) {
    if (header.includes('LR')) {
      // Allow LR for compact linear pipelines or diagrams with nested direction TB subgraphs
      const nodeCount = (text.match(/-->|-.->|==>/g) || []).length;
      const hasNestedTB = text.includes('direction TB');
      const isLinearPipeline = nodeCount <= 6 && !text.includes('subgraph');

      if (!hasNestedTB && !isLinearPipeline) {
        warnings.push({
          line: block.startLine + 1,
          rule: 'FLOWCHART_DIRECTION_WARN',
          message: `Flowchart uses broad horizontal 'LR' direction (${nodeCount} transitions). Top-to-bottom ('TB'/'TD') or nested 'direction TB' subgraphs are recommended for standard document widths.`,
        });
      }
    }
  }

  // 3. Sequence Diagram Checks
  if (header.startsWith('sequenceDiagram')) {
    if (!text.includes('autonumber')) {
      warnings.push({
        line: block.startLine + 1,
        rule: 'SEQUENCE_AUTONUMBER',
        message: `Sequence diagram missing 'autonumber' declaration for step traceability.`,
      });
    }

    const participants = block.lines
      .filter((l) => l.trim().startsWith('participant ') || l.trim().startsWith('actor '))
      .map((l) => l.trim().split(/\s+/)[1]);

    if (participants.length > 6) {
      warnings.push({
        line: block.startLine + 1,
        rule: 'SEQUENCE_MAX_PARTICIPANTS',
        message: `Sequence diagram defines ${participants.length} participants (recommended max is 6 to avoid horizontal clipping).`,
      });
    }
  }

  // 4. Class Diagram Checks
  if (header.startsWith('classDiagram')) {
    for (let idx = 0; idx < block.lines.length; idx++) {
      const line = block.lines[idx];
      // Check for unescaped generic syntax like Promise<void> instead of Promise~void~
      if (/(?<!<)<[A-Za-z0-9_, ]+>(?!>)/.test(line)) {
        errors.push({
          line: block.startLine + idx + 1,
          rule: 'CLASS_GENERICS_UNESCAPED',
          message: `Unescaped generic '<...>' detected on line ${block.startLine + idx + 1}. Use '~T~' (e.g. Promise~void~).`,
        });
      }
    }
  }

  // 5. State Diagram Checks
  if (header.startsWith('stateDiagram') || header.startsWith('stateDiagram-v2')) {
    if (!header.startsWith('stateDiagram-v2')) {
      warnings.push({
        line: block.startLine + 1,
        rule: 'STATE_DIAGRAM_V2',
        message: `Recommend using 'stateDiagram-v2' modern renderer instead of legacy 'stateDiagram'.`,
      });
    }
  }

  return { errors, warnings };
}

function lintDocumentForForbiddenAscii(content, filePath) {
  const lines = content.split('\n');
  const errors = [];
  let inCode = false;
  let codeTag = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {
      if (!inCode) {
        inCode = true;
        codeTag = line.trim().slice(3).trim().toLowerCase();
      } else {
        inCode = false;
        codeTag = '';
      }
      continue;
    }

    // Check for ASCII box drawings: +---+ or +===+ or box-drawing characters
    if (ASCII_BOX_REGEX.test(line)) {
      const isFileTree =
        (codeTag === 'text' || codeTag === 'bash') &&
        !line.includes('+---') &&
        !line.includes('+===');
      if (!isFileTree) {
        errors.push({
          line: i + 1,
          rule: 'ZERO_ASCII_ART',
          message: `Forbidden ASCII box character detected on line ${i + 1} in ${filePath}. Use standard Mermaid diagrams instead.`,
        });
      }
    }
  }

  return errors;
}

function scanAndLintDir(targetDir) {
  const files = fs.readdirSync(targetDir);
  let totalBlocks = 0;
  let totalErrors = 0;
  let totalWarnings = 0;

  console.log(`\n🔍 Scanning Mermaid diagrams in: ${targetDir}\n`);

  for (const file of files) {
    if (file.endsWith('.md')) {
      const fullPath = path.join(targetDir, file);
      const content = fs.readFileSync(fullPath, 'utf8');

      // Check full document for forbidden ASCII box art
      const asciiErrors = lintDocumentForForbiddenAscii(content, file);
      if (asciiErrors.length > 0) {
        for (const err of asciiErrors) {
          totalErrors++;
          console.error(`  ❌ [L${err.line}] [${err.rule}] ${err.message}`);
        }
      }

      const blocks = extractMermaidBlocks(content, file);

      if (blocks.length > 0) {
        console.log(`📄 ${file} (${blocks.length} Mermaid block${blocks.length > 1 ? 's' : ''})`);
        for (const b of blocks) {
          totalBlocks++;
          const { errors, warnings } = lintMermaidBlock(b);

          if (errors.length > 0) {
            for (const err of errors) {
              totalErrors++;
              console.error(`  ❌ [L${err.line}] [${err.rule}] ${err.message}`);
            }
          }

          if (warnings.length > 0) {
            for (const warn of warnings) {
              totalWarnings++;
              console.warn(`  ⚠️  [L${warn.line}] [${warn.rule}] ${warn.message}`);
            }
          }
        }
      }
    }
  }

  console.log('\n' + '─'.repeat(60));
  console.log(`Total Diagram Blocks Validated: ${totalBlocks}`);
  console.log(`Syntax Errors: ${totalErrors}`);
  console.log(`Quality Warnings: ${totalWarnings}`);
  console.log('─'.repeat(60) + '\n');

  if (totalErrors > 0) {
    console.error('💥 Mermaid validation failed with errors.\n');
    process.exit(1);
  } else {
    console.log('✨ All Mermaid diagrams passed quality validation!\n');
    process.exit(0);
  }
}

function main() {
  const args = process.argv.slice(2);
  const targetDir = args[0] || path.join(process.cwd(), 'docs/architecture');

  if (!fs.existsSync(targetDir)) {
    console.error(`Error: Directory not found: ${targetDir}`);
    process.exit(1);
  }

  scanAndLintDir(targetDir);
}

if (require.main === module) {
  main();
}

module.exports = {
  extractMermaidBlocks,
  lintMermaidBlock,
  lintDocumentForForbiddenAscii,
};
