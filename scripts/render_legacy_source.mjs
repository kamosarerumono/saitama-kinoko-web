// Reuse the Markdown/frontmatter processor already used by Astro.
import { createMarkdownProcessor, parseFrontmatter } from '@astrojs/markdown-remark';
import fs from 'node:fs';
const parsed = parseFrontmatter(fs.readFileSync(0, 'utf8'));
const processor = await createMarkdownProcessor({ syntaxHighlight: false });
const result = await processor.render(parsed.content);
process.stdout.write(JSON.stringify({ metadata: parsed.frontmatter, html: result.code }));
