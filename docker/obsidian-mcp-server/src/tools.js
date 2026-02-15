import fs from 'fs-extra';
import path from 'path';
import matter from 'gray-matter';

const VAULT_PATH = process.env.VAULT_PATH || '/vault';

/**
 * Validate and sanitize path to prevent traversal attacks
 */
function validatePath(userPath, basePathOverride = null) {
  if (!userPath || typeof userPath !== 'string') {
    throw new Error('Invalid path: must be a non-empty string');
  }

  const basePath = basePathOverride || VAULT_PATH;
  const normalized = path.normalize(userPath);
  const resolved = path.resolve(basePath, normalized);
  const baseResolved = path.resolve(basePath);

  // Ensure resolved path is within vault
  if (!resolved.startsWith(baseResolved + path.sep) && resolved !== baseResolved) {
    throw new Error(`Access denied: path outside vault (${userPath})`);
  }

  return resolved;
}

/**
 * List notes in vault or folder
 */
export async function listNotes(args) {
  const folderPath = args?.folder || '';
  const targetPath = validatePath(folderPath);

  if (!await fs.pathExists(targetPath)) {
    throw new Error(`Folder not found: ${folderPath}`);
  }

  const files = await fs.readdir(targetPath, { withFileTypes: true });
  const notes = files
    .filter(f => f.isFile() && f.name.endsWith('.md'))
    .map(f => ({
      name: f.name,
      path: path.join(folderPath, f.name).replace(/\\/g, '/')
    }));

  return { notes, count: notes.length };
}

/**
 * Read note content with frontmatter
 */
export async function readNote(args) {
  if (!args?.path) {
    throw new Error('path argument is required');
  }

  const notePath = validatePath(args.path);

  if (!await fs.pathExists(notePath)) {
    throw new Error(`Note not found: ${args.path}`);
  }

  const content = await fs.readFile(notePath, 'utf-8');
  const parsed = matter(content);

  return {
    path: args.path,
    frontmatter: parsed.data,
    content: parsed.content,
    raw: content
  };
}

/**
 * Write/update note
 */
export async function writeNote(args) {
  if (!args?.path) {
    throw new Error('path argument is required');
  }
  if (!args?.content && args.content !== '') {
    throw new Error('content argument is required');
  }

  const notePath = validatePath(args.path);
  const created = !(await fs.pathExists(notePath)); // Check BEFORE writing

  const dir = path.dirname(notePath);
  await fs.ensureDir(dir);

  let content = args.content;
  if (args.frontmatter) {
    content = matter.stringify(args.content, args.frontmatter);
  }

  await fs.writeFile(notePath, content, 'utf-8');

  return {
    path: args.path,
    success: true,
    created
  };
}

const MAX_SEARCH_RESULTS = 100;
const MAX_FILE_SIZE = 1024 * 1024; // 1MB
const MAX_DEPTH = 10;

/**
 * Search vault by content
 */
export async function searchVault(args) {
  if (!args?.query) {
    throw new Error('query argument is required');
  }

  const query = args.query.toLowerCase();
  const results = [];

  async function searchDir(dir, depth = 0) {
    if (depth > MAX_DEPTH) return;
    if (results.length >= MAX_SEARCH_RESULTS) return;

    const files = await fs.readdir(dir, { withFileTypes: true });

    for (const file of files) {
      if (results.length >= MAX_SEARCH_RESULTS) break;

      const fullPath = path.join(dir, file.name);

      // Skip symlinks to prevent cycles
      const stats = await fs.lstat(fullPath);
      if (stats.isSymbolicLink()) continue;

      if (file.isDirectory()) {
        await searchDir(fullPath, depth + 1);
      } else if (file.name.endsWith('.md')) {
        // Check file size before reading
        if (stats.size > MAX_FILE_SIZE) continue;

        const content = await fs.readFile(fullPath, 'utf-8');
        if (content.toLowerCase().includes(query)) {
          const relativePath = path.relative(VAULT_PATH, fullPath).replace(/\\/g, '/');
          const lines = content.split('\n');
          const matchingLines = lines
            .map((line, idx) => ({ line, num: idx + 1 }))
            .filter(({ line }) => line.toLowerCase().includes(query))
            .slice(0, 3);

          results.push({
            path: relativePath,
            matches: matchingLines.length,
            preview: matchingLines
          });
        }
      }
    }
  }

  await searchDir(VAULT_PATH);

  return {
    query: args.query,
    results,
    count: results.length
  };
}

export const tools = [
  {
    name: 'obsidian_list_notes',
    description: 'List all notes in the vault or a specific folder',
    inputSchema: {
      type: 'object',
      properties: {
        folder: {
          type: 'string',
          description: 'Optional folder path (relative to vault root)'
        }
      }
    }
  },
  {
    name: 'obsidian_read_note',
    description: 'Read a note and parse its frontmatter',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the note (relative to vault root)'
        }
      },
      required: ['path']
    }
  },
  {
    name: 'obsidian_write_note',
    description: 'Create or update a note',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the note (relative to vault root)'
        },
        content: {
          type: 'string',
          description: 'Note content (markdown)'
        },
        frontmatter: {
          type: 'object',
          description: 'Optional frontmatter metadata'
        }
      },
      required: ['path', 'content']
    }
  },
  {
    name: 'obsidian_search',
    description: 'Search vault content',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query'
        }
      },
      required: ['query']
    }
  }
];

export const handlers = {
  obsidian_list_notes: listNotes,
  obsidian_read_note: readNote,
  obsidian_write_note: writeNote,
  obsidian_search: searchVault
};
