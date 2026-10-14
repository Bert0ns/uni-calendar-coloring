#!/usr/bin/env node
/**
 * Automated Subagent Prompt Interpolation & Dispatch Generator
 *
 * Reads domain manifests, project metadata, and persona prompt templates,
 * interpolates all template variables ({{PROJECT_CONTEXT}}, {{TARGET_FILES}}, {{EXISTING_DOC_EXCERPT}}),
 * and generates ready-to-dispatch payloads for `invoke_subagent`.
 */

const fs = require('fs');
const path = require('path');
const { getDomainManifests } = require('./generate_manifest');

const DOMAIN_METADATA = {
  navigation_ux: {
    index: 1,
    id: 'navigation_ux',
    role: 'Navigation & UX Specialist',
    headingRegex: /## Subagent 1:\s*Navigation/i,
    outputFiles: ['02-screens-and-navigation.md'],
  },
  state_domain: {
    index: 2,
    id: 'state_domain',
    role: 'State & Domain Logic Specialist',
    headingRegex: /## Subagent 2:\s*State Management/i,
    outputFiles: ['03-state-management-and-domain.md'],
  },
  apis_networking: {
    index: 3,
    id: 'apis_networking',
    role: 'External APIs & Network Specialist',
    headingRegex: /## Subagent 3:\s*External APIs/i,
    outputFiles: ['05-apis-networking-and-proxy.md'],
  },
  sensors_native: {
    index: 4,
    id: 'sensors_native',
    role: 'Sensors & Native Specialist',
    headingRegex: /## Subagent 4:\s*(?:Hardware Sensors|Hardware)/i,
    outputFiles: ['04-sensors-kinematics-and-native.md'],
  },
  system_c4_requirements: {
    index: 5,
    id: 'system_c4_requirements',
    role: 'System Context & C4 Architect',
    headingRegex: /## Subagent 5:\s*System Context/i,
    outputFiles: ['index.md', '01-c4-context-and-containers.md', '06-cross-cutting-concerns.md'],
  },
  solid_testing_governance: {
    index: 6,
    id: 'solid_testing_governance',
    role: 'SOLID, QA & Governance Specialist',
    headingRegex: /## Subagent 6:\s*SOLID Principles/i,
    outputFiles: [
      '07-solid-principles-and-patterns.md',
      '08-testing-and-cicd.md',
      '09-appendix-technical-debt.md',
    ],
  },
};

/**
 * Extracts raw prompt templates from references/persona-prompts.md
 */
function extractPersonaPrompts(referencesDir) {
  const promptsFile = path.join(referencesDir, 'persona-prompts.md');
  if (!fs.existsSync(promptsFile)) {
    throw new Error(`Persona prompts file not found at: ${promptsFile}`);
  }

  const content = fs.readFileSync(promptsFile, 'utf8');
  const extracted = {};

  // Split by markdown code fences within sections
  const sections = content.split(/\n(?=## Subagent \d+:)/);

  for (const section of sections) {
    for (const [domainId, meta] of Object.entries(DOMAIN_METADATA)) {
      if (meta.headingRegex.test(section)) {
        // Extract content inside ```markdown ... ```
        const match = section.match(/```markdown\n([\s\S]*?)\n```/);
        if (match && match[1]) {
          extracted[domainId] = match[1].trim();
        }
      }
    }
  }

  return extracted;
}

/**
 * Extracts high-level project context from package.json and workspace structure
 */
function extractProjectContext(rootDir) {
  let pkgName = 'bert0ns-family-management';
  let techDetails = [];

  const pkgPath = path.join(rootDir, 'package.json');
  if (fs.existsSync(pkgPath)) {
    try {
      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
      pkgName = pkg.name || pkgName;
      const deps = {
        ...(pkg.dependencies || {}),
        ...(pkg.devDependencies || {}),
      };

      if (deps['react-native']) techDetails.push(`React Native ${deps['react-native']}`);
      if (deps['expo']) techDetails.push(`Expo ${deps['expo']}`);
      if (deps['expo-router']) techDetails.push(`Expo Router ${deps['expo-router']}`);
      if (deps['@supabase/supabase-js'])
        techDetails.push(`Supabase ${deps['@supabase/supabase-js']}`);
      if (deps['zustand']) techDetails.push(`Zustand ${deps['zustand']}`);
      if (deps['typescript']) techDetails.push(`TypeScript ${deps['typescript']}`);
      if (deps['zod']) techDetails.push(`Zod ${deps['zod']}`);
    } catch (_) {
      // Ignore JSON parse errors
    }
  }

  return `${pkgName} — Privacy-First Cross-Platform Household Expense & Family Financial Analytics (${techDetails.join(', ') || 'React Native / Expo / Supabase'})`;
}

/**
 * Generates an existing documentation excerpt if brownfield docs exist
 */
function extractExistingDocExcerpt(rootDir, outputFiles) {
  const excerpts = [];
  for (const file of outputFiles) {
    const filePath = path.join(rootDir, 'docs', 'architecture', file);
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.split('\n').slice(0, 15).join('\n');
      excerpts.push(`### Excerpt from docs/architecture/${file}:\n${lines}\n...`);
    }
  }

  return excerpts.length > 0
    ? excerpts.join('\n\n')
    : 'No prior module file found (Greenfield / Full Generation Mode).';
}

/**
 * Builds the fully interpolated subagent dispatch payload
 */
function buildDispatchPayload(options = {}) {
  const rootDir = options.rootDir || process.cwd();
  const referencesDir =
    options.referencesDir ||
    path.join(rootDir, '.agents', 'skills', 'system-design-docs', 'references');
  const mode = options.mode === 'write' || options.mode === 'self' ? 'self' : 'research';
  const model = options.model || 'inherit';
  const domainFilter = options.domain || null;

  const rawPrompts = extractPersonaPrompts(referencesDir);
  const domainManifests = getDomainManifests(rootDir);
  const projectContext = extractProjectContext(rootDir);

  const subagents = [];

  for (const [domainId, meta] of Object.entries(DOMAIN_METADATA)) {
    if (domainFilter && domainFilter !== domainId) {
      continue;
    }

    const rawTemplate = rawPrompts[domainId];
    if (!rawTemplate) {
      continue;
    }

    const manifest = domainManifests[domainId] || { files: [] };
    const targetFilesFormatted =
      manifest.files.length > 0
        ? manifest.files.map((f) => `- \`${f}\``).join('\n')
        : '- None discovered (check manifest rules)';

    const existingDocExcerpt = extractExistingDocExcerpt(rootDir, meta.outputFiles);

    // Variable substitutions
    let prompt = rawTemplate
      .replace(/{{PROJECT_CONTEXT}}/g, projectContext)
      .replace(/{{TARGET_FILES}}/g, targetFilesFormatted)
      .replace(/{{EXISTING_DOC_EXCERPT}}/g, existingDocExcerpt);

    // If research mode (read-only), append instructions on returning full content in message
    if (mode === 'research') {
      const fileExamples = meta.outputFiles
        .map(
          (f) =>
            `<!-- FILE: docs/architecture/${f} -->\n# Complete Architectural Specification for ${f}\n<!-- END_FILE -->`,
        )
        .join('\n\n');
      prompt += `\n\n### Mode Instruction (Read-Only Research Subagent):\nDo NOT attempt to write files to disk. Return your full, complete, high-fidelity markdown document inside your response message enclosed in explicit file delimiters:\n\n${fileExamples}\n\nThis allows the orchestrator to automatically unpack and stage all files without manual slicing.`;
    }

    subagents.push({
      Role: meta.role,
      TypeName: mode,
      Model: model,
      Prompt: prompt,
      DomainId: domainId,
      AssignedFiles: meta.outputFiles,
    });
  }

  return {
    Subagents: subagents,
  };
}

function main() {
  const args = process.argv.slice(2);
  const rootDir = args.find((a) => !a.startsWith('--')) || process.cwd();

  const domainArg = args.find((a) => a.startsWith('--domain='))?.split('=')[1];
  const modeArg =
    args.find((a) => a.startsWith('--mode=') || a.startsWith('--type='))?.split('=')[1] ||
    'research';
  const modelArg = args.find((a) => a.startsWith('--model='))?.split('=')[1] || 'inherit';
  const isMarkdown = args.includes('--markdown') || args.includes('--raw');
  const saveToSpecified = args.find((a) => a.startsWith('--save-to='))?.split('=')[1];
  const shouldSave = args.includes('--save') || Boolean(saveToSpecified);

  const payload = buildDispatchPayload({
    rootDir,
    domain: domainArg,
    mode: modeArg,
    model: modelArg,
  });

  if (isMarkdown) {
    console.log('# Interpolated Subagent Dispatch Prompts\n');
    for (const sub of payload.Subagents) {
      console.log(`## Domain: ${sub.Role} (${sub.DomainId})`);
      console.log(`- **Subagent TypeName:** \`${sub.TypeName}\``);
      console.log(`- **Assigned Modules:** ${sub.AssignedFiles.join(', ')}\n`);
      console.log('```markdown');
      console.log(sub.Prompt);
      console.log('```\n');
    }
    return;
  }

  const jsonStr = JSON.stringify(payload, null, 2);

  if (shouldSave) {
    const defaultOut = path.join(
      rootDir,
      '.agents',
      'skills',
      'system-design-docs',
      'scratch',
      'dispatch_payload.json',
    );
    const targetFile = saveToSpecified || defaultOut;
    fs.mkdirSync(path.dirname(targetFile), { recursive: true });
    fs.writeFileSync(targetFile, jsonStr, 'utf8');
    console.log(
      `✅ Saved ready-to-dispatch payload (${payload.Subagents.length} subagents) to: ${targetFile}`,
    );
  } else {
    console.log(jsonStr);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  DOMAIN_METADATA,
  extractPersonaPrompts,
  extractProjectContext,
  extractExistingDocExcerpt,
  buildDispatchPayload,
};
