#!/usr/bin/env node
/**
 * Automated Domain Partitioning & Manifest Discovery Script
 * Classifies codebase files into 6 specialized architectural domains for subagents.
 */

const fs = require('fs');
const path = require('path');

const IGNORED_DIRS = new Set([
  'node_modules',
  '.git',
  '.expo',
  '.fallow',
  'coverage',
  'dist',
  'build',
  '.vscode',
  '.husky',
  'scratch',
  '.gemini',
]);

const IGNORED_EXTENSIONS = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.ico',
  '.apk',
  '.ipa',
  '.lock',
  '.log',
]);

function scanDir(dir, fileList = [], rootDir = dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    const relPath = path.relative(rootDir, fullPath);

    if (entry.isDirectory()) {
      if (!IGNORED_DIRS.has(entry.name) && !entry.name.startsWith('.staging')) {
        scanDir(fullPath, fileList, rootDir);
      }
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      if (!IGNORED_EXTENSIONS.has(ext)) {
        fileList.push(relPath);
      }
    }
  }
  return fileList;
}

function classifyFiles(files, rootDir) {
  const domains = {
    navigation_ux: {
      id: 'navigation_ux',
      name: 'Navigation, Screens & UX Architecture',
      outputModule: '02-screens-and-navigation.md',
      files: [],
    },
    state_domain: {
      id: 'state_domain',
      name: 'State Management, Domain Models & Reactive Hooks',
      outputModule: '03-state-management-and-domain.md',
      files: [],
    },
    apis_networking: {
      id: 'apis_networking',
      name: 'External APIs, Networking & Web Proxy Gateway',
      outputModule: '05-apis-networking-and-proxy.md',
      files: [],
    },
    sensors_native: {
      id: 'sensors_native',
      name: 'Hardware Sensors, Kinematics & Native Platform Architecture',
      outputModule: '04-sensors-kinematics-and-native.md',
      files: [],
    },
    system_c4_requirements: {
      id: 'system_c4_requirements',
      name: 'System Context, Requirements & C4 Blueprint',
      outputModule: 'index.md, 01-c4-context-and-containers.md, 06-cross-cutting-concerns.md',
      files: [],
    },
    solid_testing_governance: {
      id: 'solid_testing_governance',
      name: 'SOLID Principles, Test Strategy & CI/CD Governance',
      outputModule:
        '07-solid-principles-and-patterns.md, 08-testing-and-cicd.md, 09-appendix-technical-debt.md',
      files: [],
    },
  };

  for (const f of files) {
    const norm = f.replace(/\\/g, '/');

    // 1. Tests & CI/CD & Governance
    if (
      norm.startsWith('__tests__/') ||
      norm.startsWith('.github/') ||
      norm === 'jest.setup.js' ||
      norm === 'jest.config.js' ||
      norm === 'eslint.config.js' ||
      norm === 'tsconfig.json' ||
      norm === 'eas.json' ||
      norm === 'metro.config.js'
    ) {
      domains.solid_testing_governance.files.push(f);
      continue;
    }

    // 2. Navigation & UI Screens / Presentation
    if ((norm.startsWith('app/') || norm.startsWith('src/app/')) && !norm.includes('api/')) {
      domains.navigation_ux.files.push(f);
    }
    if (norm.startsWith('components/') || norm.startsWith('src/components/')) {
      domains.navigation_ux.files.push(f);
    }
    if (norm.startsWith('public/')) {
      domains.navigation_ux.files.push(f);
    }

    // 3. State & Stores & Domain Models
    if (
      norm.startsWith('store/') ||
      norm.startsWith('src/store/') ||
      norm === 'src/services/store.ts' ||
      norm === 'src/services/interfaces.ts' ||
      norm === 'src/services/splitCalculator.ts' ||
      norm === 'src/services/analytics.ts' ||
      norm.startsWith('src/types/') ||
      norm.startsWith('src/data/')
    ) {
      domains.state_domain.files.push(f);
    }

    // 4. APIs & Networking & Cloud / Database
    if (
      norm.startsWith('lib/api/') ||
      norm.startsWith('app/api/') ||
      norm.startsWith('docs/api/') ||
      norm === 'src/services/supabase.ts' ||
      norm === 'src/services/authService.ts' ||
      norm === 'src/services/syncEngine.ts' ||
      norm === 'src/services/realtimeSync.ts' ||
      norm === 'src/services/migrationService.ts' ||
      norm === 'src/services/aiPromptGenerator.ts' ||
      norm === 'src/services/jsonExtractor.ts' ||
      norm === 'src/services/csvExporter.ts' ||
      norm === 'src/data/supabase_schema.sql'
    ) {
      domains.apis_networking.files.push(f);
    }

    // 5. Sensors, Native Platform, Notifications, File System & Kinematics
    if (
      norm.includes('motion-cues') ||
      norm.includes('speed-calculator') ||
      norm.includes('geometry') ||
      norm.includes('use-train-speed') ||
      norm.includes('use-location') ||
      norm.includes('use-qr-scanner') ||
      norm.includes('use-podcast-') ||
      norm.includes('audioStore') ||
      norm.includes('notifications') ||
      norm === 'src/services/pushNotificationService.ts' ||
      norm === 'src/services/fileExporter.ts' ||
      norm === 'public/sw.js' ||
      norm === 'public/manifest.json' ||
      norm.includes('haptics') ||
      norm.includes('clipboard')
    ) {
      domains.sensors_native.files.push(f);
    }

    // 6. Cross-cutting & System Config
    if (
      norm === 'package.json' ||
      norm === 'app.json' ||
      norm === 'app.config.ts' ||
      norm.startsWith('lib/logger') ||
      norm.startsWith('lib/theme') ||
      norm.startsWith('lib/i18n/') ||
      norm.startsWith('src/theme/') ||
      norm.startsWith('src/i18n/') ||
      norm === 'src/services/logger.ts' ||
      norm === 'src/services/validator.ts' ||
      norm === 'src/services/duplicateDetector.ts' ||
      norm === 'src/utils/uuid.ts'
    ) {
      domains.system_c4_requirements.files.push(f);
    }

    // Domain hooks classification
    if (norm.startsWith('hooks/') || norm.startsWith('src/hooks/')) {
      if (
        norm.includes('sync') ||
        norm.includes('polling') ||
        norm.includes('weather') ||
        norm.includes('news') ||
        norm.includes('discover') ||
        norm.includes('media')
      ) {
        domains.state_domain.files.push(f);
      } else if (
        norm.includes('sheet') ||
        norm.includes('modal') ||
        norm.includes('styles') ||
        norm.includes('login')
      ) {
        domains.navigation_ux.files.push(f);
      }
    }
  }

  // Deduplicate file lists per domain
  for (const k of Object.keys(domains)) {
    domains[k].files = Array.from(new Set(domains[k].files)).sort();
  }

  return domains;
}

function main() {
  const args = process.argv.slice(2);
  const targetDir = args.find((a) => !a.startsWith('--')) || process.cwd();
  const format = args.includes('--json') ? 'json' : 'markdown';
  const domainFilter = args.find((a) => a.startsWith('--domain='))?.split('=')[1];

  const allFiles = scanDir(targetDir);
  const categorized = classifyFiles(allFiles, targetDir);

  if (domainFilter && categorized[domainFilter]) {
    if (format === 'json') {
      console.log(JSON.stringify(categorized[domainFilter], null, 2));
    } else {
      console.log(
        `### Domain: ${categorized[domainFilter].name} (${categorized[domainFilter].outputModule})`,
      );
      console.log(categorized[domainFilter].files.map((f) => `- \`${f}\``).join('\n'));
    }
    return;
  }

  if (format === 'json') {
    console.log(JSON.stringify(categorized, null, 2));
  } else {
    console.log('# Discovered Subsystem Manifests\n');
    for (const key of Object.keys(categorized)) {
      const d = categorized[key];
      console.log(`## ${d.name}`);
      console.log(`- **Assigned Deliverables:** \`${d.outputModule}\``);
      console.log(`- **Matched Source Files (${d.files.length}):**`);
      console.log(d.files.map((f) => `  - \`${f}\``).join('\n'));
      console.log('');
    }
  }
}

function getDomainManifests(targetDir = process.cwd()) {
  const allFiles = scanDir(targetDir);
  return classifyFiles(allFiles, targetDir);
}

function getDomainFiles(domainId, targetDir = process.cwd()) {
  const manifests = getDomainManifests(targetDir);
  return manifests[domainId]?.files || [];
}

if (require.main === module) {
  main();
}

module.exports = {
  scanDir,
  classifyFiles,
  scanCodebase: scanDir,
  partitionCodebase: classifyFiles,
  getDomainManifests,
  getDomainFiles,
};
