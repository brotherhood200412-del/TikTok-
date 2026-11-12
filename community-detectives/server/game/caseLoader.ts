import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { parse } from 'yaml';
import { validateCase, type ValidationReport } from './validator.js';
import type { CaseDefinition } from '../../shared/case/schema.js';

export const CASES_DIR = path.resolve(import.meta.dirname, '../../content/cases');

export interface LoadedCase {
  file: string;
  raw: unknown;
  checksum: string;
  report: ValidationReport;
  def?: CaseDefinition;
}

export async function loadCaseFile(file: string): Promise<LoadedCase> {
  const text = await readFile(file, 'utf8');
  let raw: unknown;
  try {
    raw = parse(text, { maxAliasCount: 200 });
  } catch (e) {
    return {
      file,
      raw: null,
      checksum: '',
      report: { ok: false, errors: [`YAML-Fehler: ${(e as Error).message}`], warnings: [], stats: { suspects: 0, characters: 0, evidence: 0, insights: 0, puzzles: 0, statements: 0, connections: 0, events: 0, redHerrings: 0, reachableInsights: 0 } },
    };
  }
  const { def, ...report } = validateCase(raw);
  return { file, raw, checksum: createHash('sha256').update(text).digest('hex'), report, def };
}

export async function loadAllCases(dir = CASES_DIR): Promise<LoadedCase[]> {
  const files = (await readdir(dir)).filter((f) => f.endsWith('.yaml') || f.endsWith('.yml')).sort();
  return Promise.all(files.map((f) => loadCaseFile(path.join(dir, f))));
}
